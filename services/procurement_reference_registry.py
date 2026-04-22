"""Unified registry for procurement reference data.

Supports:
- PP RF No. 1875 local parsed tables
- KTRU live fetch and parsing from zakupki.gov.ru
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup


OKPD_RE = re.compile(r"^\d{2}(?:\.\d{1,3}){1,4}$")
KTRU_RE = re.compile(r"^\d{2}(?:\.\d{1,3}){1,4}-\d{8}$")
SPACE_RE = re.compile(r"\s+")


class KTRUNotFoundError(Exception):
    """Raised when KTRU card page does not exist."""


@dataclass
class MatchResult:
    found: bool
    source: str
    query_okpd2: str
    matched_okpd2: Optional[str]
    is_parent_match: bool
    checked_candidates: list[str]

    query_name: Optional[str]
    exact_okpd_match: bool
    exact_name_match: bool
    normalized_name_match: bool
    similarity: float

    table_id: Optional[str]
    table_title: Optional[str]
    reference_name: Optional[str]
    position: Optional[str]
    row: Optional[dict[str, Any]]

    message: str


@dataclass
class KTRUMatchResult:
    found: bool
    source: str
    query_ktru: str
    query_name: Optional[str]

    exact_ktru_match: bool
    exact_name_match: bool
    normalized_name_match: bool
    similarity: float

    ktru_code: Optional[str]
    okpd2_code: Optional[str]
    okpd2_name: Optional[str]
    reference_name: Optional[str]
    unit: Optional[str]
    short_description: list[str]

    common_info_url: Optional[str]
    payload: Optional[dict[str, Any]]
    message: str


class ProcurementReferenceRegistry:
    """Load local reference datasets and perform validation lookups."""

    KTRU_BASE_URL = "https://zakupki.gov.ru/epz/ktru/ktruCard"

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/135.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    def __init__(self, base_dir: Path, sqlite_file: str = "pp1875.sqlite") -> None:
        self.base_dir = Path(base_dir)
        self.sqlite_path = self.base_dir / sqlite_file
        self.index_json_path = self.base_dir / "okpd_index.json"
        self._ktru_provider: Any | None = None

    @staticmethod
    def normalize_text(value: Optional[str]) -> str:
        if not value:
            return ""
        value = value.replace("ё", "е").replace("Ё", "Е")
        value = value.replace("\xa0", " ")
        value = SPACE_RE.sub(" ", value)
        return value.strip().lower()

    @staticmethod
    def clean_text(value: Optional[str]) -> str:
        if not value:
            return ""
        return SPACE_RE.sub(" ", value.replace("\xa0", " ")).strip()

    @staticmethod
    def truncate_text(value: Optional[str], limit: int = 200) -> str:
        text = ProcurementReferenceRegistry.clean_text(value)
        if len(text) <= limit:
            return text
        return text[: limit - 3].rstrip() + "..."

    @staticmethod
    def normalize_okpd2(value: str) -> str:
        value = value.strip()
        if not OKPD_RE.fullmatch(value):
            raise ValueError(f"Некорректный ОКПД2: {value!r}")
        return value

    @staticmethod
    def normalize_ktru(value: str) -> str:
        value = value.strip()
        if not KTRU_RE.fullmatch(value):
            raise ValueError(f"Некорректный код КТРУ: {value!r}")
        return value

    @staticmethod
    def build_okpd_candidates(code: str) -> list[str]:
        parts = code.split(".")
        return [".".join(parts[:i]) for i in range(len(parts), 1, -1)]

    def _load_rows_from_sqlite(self, okpd2: str) -> list[dict[str, Any]]:
        if not self.sqlite_path.exists():
            return []

        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT
                    okpd2,
                    name,
                    table_id,
                    table_title,
                    appendix_title,
                    row_index,
                    position,
                    raw_code_text,
                    row_json
                FROM okpd_index
                WHERE okpd2 = ?
                ORDER BY table_id, row_index
                """,
                (okpd2,),
            )
            rows: list[dict[str, Any]] = []
            for row in cursor.fetchall():
                payload = dict(row)
                payload["row"] = json.loads(payload.pop("row_json"))
                rows.append(payload)
            return rows
        finally:
            connection.close()

    def _load_rows_from_json(self, okpd2: str) -> list[dict[str, Any]]:
        if not self.index_json_path.exists():
            return []

        payload = json.loads(self.index_json_path.read_text(encoding="utf-8"))
        return [row for row in payload if row.get("okpd2") == okpd2]

    def find_okpd2(self, okpd2: str) -> list[dict[str, Any]]:
        code = self.normalize_okpd2(okpd2)

        rows = self._load_rows_from_sqlite(code)
        if rows:
            return rows

        return self._load_rows_from_json(code)

    def find_okpd2_with_fallback(self, okpd2: str) -> tuple[Optional[str], list[dict[str, Any]], list[str]]:
        code = self.normalize_okpd2(okpd2)
        checked_candidates = self.build_okpd_candidates(code)

        for candidate in checked_candidates:
            rows = self.find_okpd2(candidate)
            if rows:
                return candidate, rows, checked_candidates

        return None, [], checked_candidates

    def _pick_best_candidate(
        self,
        candidates: list[dict[str, Any]],
        query_name: Optional[str],
    ) -> tuple[dict[str, Any], bool, bool, float]:
        normalized_query_name = self.normalize_text(query_name)

        best: Optional[dict[str, Any]] = None
        best_score = float("-inf")
        best_exact_name = False
        best_normalized_name = False
        best_similarity = 0.0

        for candidate in candidates:
            reference_name = candidate.get("name") or candidate.get("reference_name") or ""
            normalized_reference_name = self.normalize_text(reference_name)

            exact_name = bool(query_name and reference_name == query_name)
            normalized_name = bool(
                normalized_query_name and normalized_query_name == normalized_reference_name
            )
            similarity = (
                SequenceMatcher(None, normalized_query_name, normalized_reference_name).ratio()
                if normalized_query_name and normalized_reference_name
                else 0.0
            )

            score = similarity
            if normalized_name:
                score += 10
            if exact_name:
                score += 20

            if score > best_score:
                best = candidate
                best_score = score
                best_exact_name = exact_name
                best_normalized_name = normalized_name
                best_similarity = similarity

        assert best is not None
        return best, best_exact_name, best_normalized_name, best_similarity

    def check_okpd2(self, okpd2: str, name: Optional[str] = None) -> MatchResult:
        query_code = self.normalize_okpd2(okpd2)
        matched_code, candidates, checked_candidates = self.find_okpd2_with_fallback(query_code)

        if not candidates or matched_code is None:
            checked_str = ", ".join(checked_candidates)
            return MatchResult(
                found=False,
                source="pp_1875",
                query_okpd2=query_code,
                matched_okpd2=None,
                is_parent_match=False,
                checked_candidates=checked_candidates,
                query_name=name,
                exact_okpd_match=False,
                exact_name_match=False,
                normalized_name_match=False,
                similarity=0.0,
                table_id=None,
                table_title=None,
                reference_name=None,
                position=None,
                row=None,
                message=(
                    f"Код {query_code} не найден в локальном справочнике ПП РФ № 1875.\n "
                    f"Проверены префиксы: {checked_str}."
                ),
            )

        best, exact_name_match, normalized_name_match, similarity = self._pick_best_candidate(
            candidates=candidates,
            query_name=name,
        )

        reference_name = best.get("name") or best.get("reference_name")
        short_table_title = self.truncate_text(best.get("table_title"), limit=200)
        exact_okpd_match = matched_code == query_code
        is_parent_match = not exact_okpd_match

        if not name:
            if exact_okpd_match:
                message = (
                    f"<ins>Обратите внимание</ins> Код {query_code} <ins>Входит в перечень</ins> '{short_table_title}'.\n"
                    f"Эталонное наименование: {reference_name}.\n"
                    f"<ins>Необходимо учесть требования постановления при проведении закупки.</ins>"
                )
            else:
                message = (
                    f"<ins>Обратите внимание</ins> на Код {query_code}.\n"
                    f'Родительский код {matched_code} <ins>Входит в перечень</ins> "{short_table_title}".\n'
                    f"Эталонное наименование: {reference_name}.\n"
                    f"Проверьте соответствует ли ваше наименование '{name}'."
                    f"<ins>Необходимо учесть требования постановления при проведении закупки.</ins>"
                )
        else:
            if exact_okpd_match and (exact_name_match or normalized_name_match):
                message = (
                    f"<ins>Обратите внимание</ins> Код {query_code} <ins>Входит в перечень</ins> '{short_table_title}'.\n"
                    f"<ins>Необходимо учесть требования постановления при проведении закупки.</ins>"
                )
            elif exact_okpd_match:
                message = (
                    f"<ins>Обратите внимание</ins> Код {query_code} <ins>Входит в перечень</ins> \n"
                    f"'{short_table_title}',\n"
                    f"<ins>но наименование отличается от эталонного.</ins>\n"
                    f"<ins>Эталонное наименование:</ins> {reference_name}.\n"
                    f"Проверьте соответствует ли ваше наименование '{name}'.\n"
                    f"<ins>Необходимо учесть требования постановления при проведении закупки.</ins>"
                     
                )
            else:
                message = (
                    f"Код {query_code}\n"
                    f'<ins>Обратите внимание</ins>, родительский код {matched_code} <ins>Входит в перечень</ins> "{short_table_title}".\n'
                    f"Эталонное наименование: {reference_name}.\n"
                    f"Проверьте соответствует ли ваше наименование '{name}'."
                    f"<ins>Необходимо учесть требования постановления при проведении закупки.</ins>"
                )

        return MatchResult(
            found=True,
            source="pp_1875",
            query_okpd2=query_code,
            matched_okpd2=matched_code,
            is_parent_match=is_parent_match,
            checked_candidates=checked_candidates,
            query_name=name,
            exact_okpd_match=exact_okpd_match,
            exact_name_match=exact_name_match,
            normalized_name_match=normalized_name_match,
            similarity=similarity,
            table_id=best.get("table_id"),
            table_title=best.get("table_title"),
            reference_name=reference_name,
            position=best.get("position"),
            row=best.get("row"),
            message=message,
        )

    def _build_ktru_url(self, page_name: str, ktru_code: str) -> str:
        code = self.normalize_ktru(ktru_code)
        return f"{self.KTRU_BASE_URL}/{page_name}.html?itemId={code}"

    def _fetch_html(self, url: str, timeout: int = 60) -> str:
        try:
            response = requests.get(url, headers=self.DEFAULT_HEADERS, timeout=timeout)
            response.raise_for_status()
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code == 404:
                raise KTRUNotFoundError("Карточка КТРУ не найдена") from exc
            raise

        response.encoding = response.encoding or response.apparent_encoding or "utf-8"
        return response.text

    def _extract_main_name(self, soup: BeautifulSoup) -> Optional[str]:
        node = soup.select_one(".cardMainInfo__section .cardMainInfo__content")
        if node:
            text = self.clean_text(node.get_text(" ", strip=True))
            if text:
                return text

        for section in soup.select(".blockInfo__section.section"):
            title_node = section.select_one(".section__title")
            info_node = section.select_one(".section__info")
            if not title_node or not info_node:
                continue
            title = self.clean_text(title_node.get_text(" ", strip=True)).lower()
            if "наименование товара" in title:
                text = self.clean_text(info_node.get_text(" ", strip=True))
                if text:
                    return text

        return None

    def _extract_section_pairs(self, soup: BeautifulSoup) -> dict[str, str]:
        result: dict[str, str] = {}

        for section in soup.select(".blockInfo__section.section"):
            title_node = section.select_one(".section__title")
            info_node = section.select_one(".section__info")
            if not title_node or not info_node:
                continue

            title = self.clean_text(title_node.get_text(" ", strip=True))
            info = self.clean_text(info_node.get_text(" ", strip=True))

            if title and info:
                result[title] = info

        return result

    def _extract_summary_characteristics(self, soup: BeautifulSoup) -> dict[str, str]:
        result: dict[str, str] = {}

        nodes = soup.select(".sectionMainInfo__body .cardMainInfo__title")
        texts: list[str] = []
        for node in nodes:
            text = self.clean_text(node.get_text(" ", strip=True))
            if text:
                texts.append(text)

        combined = " ".join(texts)
        parts = [part.strip(" .;") for part in combined.split(";") if part.strip(" .;")]

        for part in parts:
            if ":" not in part:
                continue

            key, value = part.split(":", 1)
            key = self.clean_text(key)
            value = self.clean_text(value)

            if not key or not value:
                continue

            if key.lower().startswith("единица измерения"):
                continue

            result[key] = value

        return result

    def parse_ktru_common_info_html(self, html: str, ktru_code: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")

        section_pairs = self._extract_section_pairs(soup)
        summary_characteristics = self._extract_summary_characteristics(soup)
        name = self._extract_main_name(soup)

        okpd2_raw = section_pairs.get("Код по ОКПД2")
        okpd2_code = None
        okpd2_name = None

        if okpd2_raw:
            if ":" in okpd2_raw:
                left, right = okpd2_raw.split(":", 1)
                okpd2_code = self.clean_text(left)
                okpd2_name = self.clean_text(right)
            else:
                okpd2_code = self.clean_text(okpd2_raw)

        unit = section_pairs.get("Единицы измерения (количество товара, объем работы, услуги по ОКЕИ)")
        application_date_start = section_pairs.get("Дата начала обязательного применения позиции каталога")
        application_date_end = section_pairs.get("Дата окончания применения позиции каталога")

        short_description: list[str] = []

        if unit:
            short_description.append(f"Единица измерения: {unit}")

        for key, value in summary_characteristics.items():
            short_description.append(f"{key}: {value}")

        return {
            "ktru_code": ktru_code,
            "name": name,
            "okpd2_code": okpd2_code,
            "okpd2_name": okpd2_name,
            "unit": unit,
            "application_date_start": application_date_start,
            "application_date_end": application_date_end,
            "summary_characteristics": summary_characteristics,
            "short_description": short_description,
            "section_pairs": section_pairs,
        }

    def get_ktru_common_info(self, ktru_code: str) -> dict[str, Any]:
        code = self.normalize_ktru(ktru_code)
        url = self._build_ktru_url("commonInfo", code)
        html = self._fetch_html(url)

        parsed = self.parse_ktru_common_info_html(html, code)
        parsed["url"] = url
        parsed["html"] = html
        return parsed

    def get_ktru_short_description(self, ktru_code: str) -> str:
        payload = self.get_ktru_common_info(ktru_code)

        name = payload.get("name")
        short_description = payload.get("short_description") or []

        lines: list[str] = []
        if name:
            lines.append(f"Наименование: {name}")

        if short_description:
            lines.append("")
            lines.append("Краткое описание:")
            lines.extend(f"- {item}" for item in short_description)

        return "\n".join(lines)

    def _build_ktru_error_result(
        self,
        code: str,
        name: Optional[str],
        message: str,
    ) -> KTRUMatchResult:
        return KTRUMatchResult(
            found=False,
            source="ktru",
            query_ktru=code,
            query_name=name,
            exact_ktru_match=False,
            exact_name_match=False,
            normalized_name_match=False,
            similarity=0.0,
            ktru_code=None,
            okpd2_code=None,
            okpd2_name=None,
            reference_name=None,
            unit=None,
            short_description=[],
            common_info_url=self._build_ktru_url("commonInfo", code),
            payload=None,
            message=message,
        )

    def check_ktru(self, ktru_code: str, name: Optional[str] = None) -> KTRUMatchResult:
        code = self.normalize_ktru(ktru_code)

        try:
            common_info = self.get_ktru_common_info(code)
        except KTRUNotFoundError:
            return self._build_ktru_error_result(
                code=code,
                name=name,
                message=f"Не удалось найти карточку КТРУ {code}\n",
            )
        except requests.RequestException:
            return self._build_ktru_error_result(
                code=code,
                name=name,
                message=f"Не удалось получить карточку КТРУ {code}\n",
            )

        reference_name = common_info.get("name")
        short_description = common_info.get("short_description") or []

        normalized_query_name = self.normalize_text(name)
        normalized_reference_name = self.normalize_text(reference_name)

        exact_name_match = bool(name and reference_name == name)
        normalized_name_match = bool(
            normalized_query_name and normalized_query_name == normalized_reference_name
        )
        similarity = (
            SequenceMatcher(None, normalized_query_name, normalized_reference_name).ratio()
            if normalized_query_name and normalized_reference_name
            else 0.0
        )

        if not reference_name:
            message = f"КТРУ {code} найден, но наименование автоматически извлечь не удалось.\n"
            found = False
        elif not name:
            lines = [f"Наименование: {reference_name}"]
            if short_description:
                lines.append("")
                lines.append("Краткое описание:")
                lines.extend(f"- {item}" for item in short_description)

            message = "\n".join(lines)
            found = True
        elif exact_name_match or normalized_name_match:
            message = (
                f"КТРУ {code} найден.\n\n"
                f"Ссылка на карточку: {common_info.get('url')}\n\n"
                f"Наименование совпадает с эталонной записью КТРУ.\n"
                f"Наименование: {reference_name}"
            )
            found = True
        else:
            message = (
                f"КТРУ {code} найден, но наименование отличается от эталонного.\n\n"
                f"Ссылка на карточку: {common_info.get('url')}\n\n"
                f"Эталонное наименование: {reference_name}\n"
                f"Проверьте соответствует ли ваше наименование '{name}'."
            )
            found = True

        return KTRUMatchResult(
            found=found,
            source="ktru",
            query_ktru=code,
            query_name=name,
            exact_ktru_match=True,
            exact_name_match=exact_name_match,
            normalized_name_match=normalized_name_match,
            similarity=similarity,
            ktru_code=common_info.get("ktru_code"),
            okpd2_code=common_info.get("okpd2_code"),
            okpd2_name=common_info.get("okpd2_name"),
            reference_name=reference_name,
            unit=common_info.get("unit"),
            short_description=short_description,
            common_info_url=common_info.get("url"),
            payload=common_info,
            message=message,
        )

    def register_ktru_provider(self, provider: Any) -> None:
        self._ktru_provider = provider
