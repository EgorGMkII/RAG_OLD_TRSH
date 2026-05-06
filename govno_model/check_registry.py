import re
from pathlib import Path
from typing import Any, List, Optional

from new_model.parser_functions import (
    parse_ktry_entries,
    parse_okpd_entries,
)
from govno_model.docs_parsing import  _parse_contract_characteristics
from services.procurement_reference_registry import ProcurementReferenceRegistry


def get_regestry_response_okpd_ktry(plan_points_use: List[str], REGISTRY_DIR: Path) -> List[str]:
    try:
        registry = ProcurementReferenceRegistry(REGISTRY_DIR)
    except Exception as e:
        print(f"Ошибка при чтении registry: {e}")
        registry = None

    try:
        parsed_okpd = parse_okpd_entries(plan_points_use[0])
    except Exception as e:
        print(f"Ошибка при парсинге ОКПД plan_points_use[0]: {e}")
        parsed_okpd = []

    try:
        parsed_ktry = parse_ktry_entries(plan_points_use[1])
    except Exception as e:
        print(f"Ошибка при парсинге КТРУ plan_points_use[1]: {e}")
        parsed_ktry = []

    res_ktry = []
    res_okpd = []

    if parsed_ktry:
        for entry in parsed_ktry:
            try:
                res = registry.check_ktru(entry["ktru_code"], entry["name"])
                res_ktry.append(res.message)
            except Exception:
                res_ktry.append(
                    f"Возникли проблемы с доступом к сайту при проверке КТРУ {entry['ktru_code']}."
                )
    else:
        res_ktry = ["Не удалось распарсить КТРУ в Плане-графике"]

    if parsed_okpd and registry:
        for entry in parsed_okpd:
            try:
                res = registry.check_okpd2(entry["okpd2"], entry["name"])
                res_okpd.append(res.message)
            except Exception:
                res_okpd.append(
                    f"Возникли проблемы с доступом к сайту при проверке ОКПД2 {entry['okpd2']}."
                )
    else:
        res_okpd = ["Не удалось распарсить ОКПД в Плане-графике или инициализировать registry"]

    return res_ktry, res_okpd


def compare_characteristics(contract_path: str, REGISTRY_DIR: Path) -> dict[str, Any]:
    LOOKALIKE_LATIN_TO_CYRILLIC = str.maketrans(
        {
            "A": "А",
            "a": "а",
            "B": "В",
            "C": "С",
            "c": "с",
            "E": "Е",
            "e": "е",
            "H": "Н",
            "K": "К",
            "k": "к",
            "M": "М",
            "O": "О",
            "o": "о",
            "P": "Р",
            "p": "р",
            "T": "Т",
            "X": "Х",
            "x": "х",
            "Y": "У",
            "y": "у",
        }
    )

    def _clean_text(value: Any) -> str:
        if value is None:
            return ""
        return " ".join(str(value).replace("\xa0", " ").split()).strip()

    def _normalize_text(value: Any) -> str:
        return _clean_text(value).lower()

    def _normalize_visual_aliases(value: Any) -> str:
        return _clean_text(value).translate(LOOKALIKE_LATIN_TO_CYRILLIC).lower()

    def _normalize_number_text(value: str) -> str:
        cleaned = _normalize_text(value).replace(",", ".")
        return re.sub(r"[^\d.\-]+", "", cleaned)

    def _try_parse_float(value: Any) -> Optional[float]:
        normalized = _normalize_number_text(str(value))
        if not normalized:
            return None
        try:
            return float(normalized)
        except ValueError:
            return None

    def _split_contract_value(value: Any) -> list[str]:
        text = _clean_text(value)
        if not text:
            return []
        parts = [part.strip() for part in re.split(r"\s*[;\n\r]+\s*", text) if part.strip()]
        return parts or [text]

    def _compare_with_range(contract_value: str, legal_value: str) -> bool:
        contract_number = _try_parse_float(contract_value)
        if contract_number is None:
            return False

        normalized_range = _normalize_text(legal_value).replace(",", ".")
        normalized_range = normalized_range.replace("≤", "<=").replace("≥", ">=")
        matches = re.findall(r"(<=|>=|<|>)\s*(-?\d+(?:\.\d+)?)", normalized_range)
        if not matches:
            return False

        for operator, raw_number in matches:
            border = float(raw_number)
            if operator == "<" and not (contract_number < border):
                return False
            if operator == "<=" and not (contract_number <= border):
                return False
            if operator == ">" and not (contract_number > border):
                return False
            if operator == ">=" and not (contract_number >= border):
                return False

        return True

    def _is_value_allowed(contract_value: str, legal_values: list[str]) -> bool:
        normalized_contract = _normalize_text(contract_value)
        normalized_contract_alias = _normalize_visual_aliases(contract_value)
        if not normalized_contract:
            return False

        contract_number = _try_parse_float(contract_value)

        for legal_value in legal_values:
            normalized_legal = _normalize_text(legal_value)
            normalized_legal_alias = _normalize_visual_aliases(legal_value)
            if not normalized_legal:
                continue

            if normalized_contract == normalized_legal:
                return True
            if normalized_contract_alias == normalized_legal_alias:
                return True

            if _compare_with_range(contract_value, legal_value):
                return True

            legal_number = _try_parse_float(legal_value)
            if contract_number is not None and legal_number is not None and contract_number == legal_number:
                return True

        return False

    def _build_legal_lookup(legal_characteristics: dict[str, list[str]]) -> dict[str, tuple[str, list[str]]]:
        lookup: dict[str, tuple[str, list[str]]] = {}
        for name, values in legal_characteristics.items():
            lookup[_normalize_text(name)] = (name, values)
        return lookup

    try:
        registry = ProcurementReferenceRegistry(REGISTRY_DIR)
    except Exception as e:
        print(f"Ошибка при чтении registry: {e}")
        return {
            "error": f"Не удалось инициализировать registry. Ошибка: {e}"
        }

    try:
        _, table_characteristics, ktry_codes = _parse_contract_characteristics(contract_path)
    except Exception as e:
        return {
            "error": f"Не удалось распарсить характеристики из контракта. Ошибка: {e}"
        }

    result: dict[str, Any] = {}

    for code in ktry_codes:
        try:
            clean_code = code.split()[1]
        except Exception:
            return {
                "error": f"Не удалось распарсить характеристики КОДЫ. Ошибка: {e}"
            }

        try:
            legal_characteristics = registry.get_ktru_characteristics(clean_code)
        except Exception as e:
            result[code] = f"Не удалось получить характеристики КТРУ с сайта. Ошибка: {e}"
            continue

        our_characteristics = table_characteristics.get(code) or {}
        if not our_characteristics:
            result[code] = "В контракте не найдены характеристики для этого КТРУ"
            continue

        legal_lookup = _build_legal_lookup(legal_characteristics)
        field_errors: dict[str, str] = {}

        for our_name, our_raw_value in our_characteristics.items():
            legal_item = legal_lookup.get(_normalize_text(our_name))
            if legal_item is None:
                field_errors[our_name] = "Характеристика отсутствует в КТРУ на сайте"
                continue

            _, legal_values = legal_item
            our_values = _split_contract_value(our_raw_value)
            invalid_values = [value for value in our_values if not _is_value_allowed(value, legal_values)]

            if invalid_values:
                legal_preview = ", ".join(legal_values[:20])
                if len(legal_values) > 20:
                    legal_preview += ", ..."
                field_errors[our_name] = (
                    f"Недопустимое значение: {', '.join(invalid_values)}. "
                    f"Допустимые значения по КТРУ: {legal_preview}"
                )

        result[code] = field_errors if field_errors else "всё ок"

    return result
