"""Unified registry for procurement reference data.

Today it supports PP RF No. 1875 extracted tables.
Later it can be extended with KTRU loaders while keeping the same public API.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional


# Строгая проверка полного кода:
# 13.2
# 14.20
# 20.59.1
# 22.29.29
# 22.29.29.190
OKPD_RE = re.compile(r"^\d{2}(?:\.\d{1,3}){1,4}$")
SPACE_RE = re.compile(r"\s+")


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


class ProcurementReferenceRegistry:
    """Load local reference datasets and perform validation lookups.

    Suggested use:
        registry = ProcurementReferenceRegistry(base_dir=Path("data/parsed_tables"))
        result = registry.check_okpd2(
            "31.09.11",
            "Мебель металлическая, не включенная в другие группировки"
        )
    """

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
    def normalize_okpd2(value: str) -> str:
        value = value.strip()
        if not OKPD_RE.fullmatch(value):
            raise ValueError(f"Некорректный ОКПД2: {value!r}")
        return value

    @staticmethod
    def build_okpd_candidates(code: str) -> list[str]:
        """Build lookup chain from most specific to less specific.

        Example:
            31.01.12.190 -> ['31.01.12.190', '31.01.12', '31.01']
        """
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
        """Find exact code or nearest parent code.

        Returns:
            matched_code, rows, checked_candidates
        """
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
                    f"Код {query_code} не найден в локальном справочнике ПП РФ № 1875. "
                    f"Проверены префиксы: {checked_str}."
                ),
            )

        best, exact_name_match, normalized_name_match, similarity = self._pick_best_candidate(
            candidates=candidates,
            query_name=name,
        )

        reference_name = best.get("name") or best.get("reference_name")
        exact_okpd_match = matched_code == query_code
        is_parent_match = not exact_okpd_match

        if not name:
            if exact_okpd_match:
                message = (
                    f"Код {query_code} найден в таблице '{best.get('table_title')}'. "
                    f"Эталонное наименование: {reference_name}."
                )
            else:
                message = (
                    f"Код {query_code} напрямую не найден. "
                    f"Найден родительский код {matched_code} в таблице '{best.get('table_title')}'. "
                    f"Эталонное наименование: {reference_name}."
                )
        else:
            if exact_okpd_match and (exact_name_match or normalized_name_match):
                message = (
                    f"Код {query_code} найден. Наименование совпадает с эталонной записью "
                    f"из таблицы '{best.get('table_title')}'."
                )
            elif exact_okpd_match:
                message = (
                    f"Код {query_code} найден в таблице '{best.get('table_title')}', "
                    f"но наименование отличается от эталонного. "
                    f"Эталонное наименование: {reference_name}. "
                    f"Проверьте соответствует ли ваше наименование '{name}'. "
                    #f"Сходство: {similarity:.3f}."
                )
            else:
                message = (
                    f"Код {query_code} напрямую не найден. "
                    f"Найден родительский код {matched_code} в таблице '{best.get('table_title')}'. "
                    f"Эталонное наименование: {reference_name}. "
                    f"Проверьте соответствует ли ваше наименование '{name}'. "
                    #f"Сходство: {similarity:.3f}."
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

    # Future extension point for KTRU support.
    def register_ktru_provider(self, provider: Any) -> None:
        self._ktru_provider = provider