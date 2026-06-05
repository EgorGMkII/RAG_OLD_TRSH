import re
from pathlib import Path
from typing import Any, List, Optional

from shared_modules.parser_functions import (
    parse_ktry_entries,
    parse_okpd_entries,
)
from latest_model.docs_parsing import  _parse_contract_characteristics
from services.procurement_reference_registry import ProcurementReferenceRegistry

KTRU_CODE_RE = re.compile(r"\d{2}(?:\.\d{1,3}){1,4}-\d{8}")
OKPD2_CODE_RE = re.compile(r"\d{2}(?:\.\d{1,3}){1,4}")


def get_regestry_response_okpd_ktry(plan_points_use: List[str], REGISTRY_DIR: Path) -> List[str]:
    try:
        registry = ProcurementReferenceRegistry(REGISTRY_DIR)
    except Exception as e:
        print(f"РћС€РёР±РєР° РїСЂРё С‡С‚РµРЅРёРё registry: {e}")
        registry = None

    try:
        parsed_okpd = parse_okpd_entries(plan_points_use[0])
    except Exception as e:
        print(f"РћС€РёР±РєР° РїСЂРё РїР°СЂСЃРёРЅРіРµ РћРљРџР” plan_points_use[0]: {e}")
        parsed_okpd = []

    try:
        parsed_ktry = parse_ktry_entries(plan_points_use[1])
    except Exception as e:
        print(f"РћС€РёР±РєР° РїСЂРё РїР°СЂСЃРёРЅРіРµ РљРўР РЈ plan_points_use[1]: {e}")
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
                    f"Р’РѕР·РЅРёРєР»Рё РїСЂРѕР±Р»РµРјС‹ СЃ РґРѕСЃС‚СѓРїРѕРј Рє СЃР°Р№С‚Сѓ РїСЂРё РїСЂРѕРІРµСЂРєРµ РљРўР РЈ {entry['ktru_code']}."
                )
    else:
        res_ktry = ["РќРµ СѓРґР°Р»РѕСЃСЊ СЂР°СЃРїР°СЂСЃРёС‚СЊ РљРўР РЈ РІ РџР»Р°РЅРµ-РіСЂР°С„РёРєРµ"]

    if parsed_okpd and registry:
        for entry in parsed_okpd:
            try:
                res = registry.check_okpd2(entry["okpd2"], entry["name"])
                res_okpd.append(res.message)
            except Exception:
                res_okpd.append(
                    f"Р’РѕР·РЅРёРєР»Рё РїСЂРѕР±Р»РµРјС‹ СЃ РґРѕСЃС‚СѓРїРѕРј Рє СЃР°Р№С‚Сѓ РїСЂРё РїСЂРѕРІРµСЂРєРµ РћРљРџР”2 {entry['okpd2']}."
                )
    else:
        res_okpd = ["РќРµ СѓРґР°Р»РѕСЃСЊ СЂР°СЃРїР°СЂСЃРёС‚СЊ РћРљРџР” РІ РџР»Р°РЅРµ-РіСЂР°С„РёРєРµ РёР»Рё РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°С‚СЊ registry"]

    return res_ktry, res_okpd


def compare_characteristics(
    ooz_path: str,
    procurement_method: str | list[str] | None,
    okpd_plan: str | None,
    REGISTRY_DIR: Path,
) -> dict[str, Any]:
    LOOKALIKE_LATIN_TO_CYRILLIC = str.maketrans(
        {
            "A": "Рђ",
            "a": "Р°",
            "B": "Р’",
            "C": "РЎ",
            "c": "СЃ",
            "E": "Р•",
            "e": "Рµ",
            "H": "Рќ",
            "K": "Рљ",
            "k": "Рє",
            "M": "Рњ",
            "O": "Рћ",
            "o": "Рѕ",
            "P": "Р ",
            "p": "СЂ",
            "T": "Рў",
            "X": "РҐ",
            "x": "С…",
            "Y": "РЈ",
            "y": "Сѓ",
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
        normalized_range = normalized_range.replace("в‰¤", "<=").replace("в‰Ґ", ">=")
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

    def _build_legal_lookup(
        legal_characteristics: dict[str, dict[str, Any]],
    ) -> dict[str, tuple[str, list[str], bool]]:
        lookup: dict[str, tuple[str, list[str], bool]] = {}
        for name, payload in legal_characteristics.items():
            values = list(payload.get("values") or [])
            required = bool(payload.get("required"))
            lookup[_normalize_text(name)] = (name, values, required)
        return lookup

    def _extract_site_ktru_code(raw_code: str) -> Optional[str]:
        match = KTRU_CODE_RE.search(raw_code or "")
        return match.group(0) if match else None

    def _normalize_procurement_method_label(value: str | list[str] | None) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            return "\n".join(str(item) for item in value if str(item).strip())
        return str(value)

    def _resolve_procurement_method(value: str | list[str] | None) -> tuple[str, str]:
        label = _clean_text(_normalize_procurement_method_label(value))
        normalized = _normalize_text(label)

        if "С‡Р°СЃС‚СЊ 12 СЃС‚Р°С‚СЊРё 93" in normalized or "С‡. 12 СЃС‚. 93" in normalized:
            return "part_12_article_93", label
        if "РµРґРёРЅСЃС‚РІРµРЅРЅС‹Р№ РїРѕСЃС‚Р°РІС‰РёРє" in normalized:
            return "single_supplier", label
        if (
            "СЌР»РµРєС‚СЂРѕРЅРЅС‹Р№ Р°СѓРєС†РёРѕРЅ" in normalized
            or "Р·Р°РїСЂРѕСЃ РєРѕС‚РёСЂРѕРІ" in normalized
            or "РєРѕРЅРєСѓСЂСЃ" in normalized
        ):
            return "competitive", label
        return "unknown", label

    def _extract_okpd2_candidates(common_info: dict[str, Any]) -> list[str]:
        candidates: list[str] = []

        for raw_value in (
            common_info.get("okpd2_code"),
            common_info.get("section_pairs", {}).get("РљРѕРґ РїРѕ РћРљРџР”2"),
        ):
            if not raw_value:
                continue
            for match in OKPD2_CODE_RE.findall(str(raw_value)):
                if match not in candidates:
                    candidates.append(match)

        return candidates

    def _parse_position_number(okpd_result: Any) -> Optional[int]:
        position_value = getattr(okpd_result, "position", None)
        if position_value is None and getattr(okpd_result, "row", None):
            position_value = okpd_result.row.get("position")
        if position_value is None:
            return None

        match = re.search(r"\d+", str(position_value))
        if not match:
            return None
        return int(match.group(0))

    def _detect_appendix(okpd_result: Any) -> Optional[str]:
        table_id = getattr(okpd_result, "table_id", None)
        if table_id == "table_01":
            return "appendix_1"
        if table_id == "table_02":
            return "appendix_2"
        return None

    def _is_special_pp1875_position(okpd_result: Any) -> bool:
        appendix = _detect_appendix(okpd_result)
        position_number = _parse_position_number(okpd_result)
        if appendix == "appendix_1":
            return position_number in {25, 26, 32}
        if appendix == "appendix_2" and position_number is not None:
            return 191 <= position_number <= 361
        return False

    def _evaluate_extra_characteristics_rule(
        method_kind: str,
        method_label: str,
        okpd_candidates: list[str],
        okpd_result: Any | None,
        has_ktru_characteristics: bool,
    ) -> dict[str, Any]:
        if method_kind == "part_12_article_93":
            return {
                "can_add_extra_characteristics": False,
                "reason": (
                    f"РЎРїРѕСЃРѕР± Р·Р°РєСѓРїРєРё: {method_label or 'С‡. 12 СЃС‚. 93 44-Р¤Р—'}. "
                    "Р”Р»СЏ Р·Р°РєСѓРїРєРё РїРѕ С‡. 12 СЃС‚. 93 РґРѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹Рµ С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРєРё РЅРµ РґРѕРїСѓСЃРєР°СЋС‚СЃСЏ."
                ),
            }

        if method_kind == "single_supplier":
            return {
                "can_add_extra_characteristics": True,
                "reason": (
                    f"РЎРїРѕСЃРѕР± Р·Р°РєСѓРїРєРё: {method_label or 'Р•РґРёРЅСЃС‚РІРµРЅРЅС‹Р№ РїРѕСЃС‚Р°РІС‰РёРє'}. "
                    "Р”Р»СЏ Р·Р°РєСѓРїРєРё Сѓ РµРґРёРЅСЃС‚РІРµРЅРЅРѕРіРѕ РїРѕСЃС‚Р°РІС‰РёРєР° РґРѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹Рµ С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРєРё РґРѕРїСѓСЃС‚РёРјС‹."
                ),
            }

        if method_kind == "unknown":
            return {
                "can_add_extra_characteristics": None,
                "reason": (
                    "РЎРїРѕСЃРѕР± Р·Р°РєСѓРїРєРё РЅРµ СѓРґР°Р»РѕСЃСЊ РѕРїСЂРµРґРµР»РёС‚СЊ РѕРґРЅРѕР·РЅР°С‡РЅРѕ. "
                    "Р’С‹РїРѕР»РЅРµРЅР° Р±Р°Р·РѕРІР°СЏ СЃС‚СЂРѕРіР°СЏ РїСЂРѕРІРµСЂРєР° С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРє."
                ),
            }

        if not has_ktru_characteristics:
            return {
                "can_add_extra_characteristics": True,
                "reason": (
                    "Р’ РєР°СЂС‚РѕС‡РєРµ РљРўР РЈ РѕС‚СЃСѓС‚СЃС‚РІСѓСЋС‚ С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРєРё. "
                    "Р’ СЌС‚РѕРј СЃР»СѓС‡Р°Рµ РґРѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹Рµ С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРєРё РјРѕР¶РЅРѕ СѓРєР°Р·С‹РІР°С‚СЊ СЃР°РјРѕСЃС‚РѕСЏС‚РµР»СЊРЅРѕ."
                ),
            }

        if len(okpd_candidates) > 1:
            return {
                "can_add_extra_characteristics": None,
                "reason": (
                    "Р’ РєР°СЂС‚РѕС‡РєРµ РљРўР РЈ РЅР°Р№РґРµРЅРѕ РЅРµСЃРєРѕР»СЊРєРѕ РєРѕРґРѕРІ РћРљРџР”2. "
                    "РђРІС‚РѕРјР°С‚РёС‡РµСЃРєРёР№ РІС‹Р±РѕСЂ РїРѕРґС…РѕРґСЏС‰РµРіРѕ РћРљРџР”2 РЅРµРѕРґРЅРѕР·РЅР°С‡РµРЅ, РїРѕСЌС‚РѕРјСѓ РІС‹РїРѕР»РЅРµРЅР° Р±Р°Р·РѕРІР°СЏ СЃС‚СЂРѕРіР°СЏ РїСЂРѕРІРµСЂРєР° С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРє."
                ),
            }

        if okpd_result is None:
            return {
                "can_add_extra_characteristics": None,
                "reason": (
                    "РќРµ СѓРґР°Р»РѕСЃСЊ РѕРїСЂРµРґРµР»РёС‚СЊ РћРљРџР”2 РґР»СЏ РїРѕР·РёС†РёРё РљРўР РЈ. "
                    "Р’С‹РїРѕР»РЅРµРЅР° Р±Р°Р·РѕРІР°СЏ СЃС‚СЂРѕРіР°СЏ РїСЂРѕРІРµСЂРєР° С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРє."
                ),
            }

        if not getattr(okpd_result, "found", False):
            return {
                "can_add_extra_characteristics": True,
                "reason": (
                    "РћРљРџР”2 РЅРµ РЅР°Р№РґРµРЅ РІ РїСЂРёР»РѕР¶РµРЅРёСЏС… 1 Рё 2 РџРџ в„–1875. "
                    "Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹Рµ С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРєРё РґРѕРїСѓСЃС‚РёРјС‹."
                ),
            }

        if _is_special_pp1875_position(okpd_result):
            return {
                "can_add_extra_characteristics": False,
                "reason": (
                    "РљРўР РЈ СЃРѕРґРµСЂР¶РёС‚ С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРєРё, Р° СЃРІСЏР·Р°РЅРЅС‹Р№ РћРљРџР”2 РїРѕРїР°РґР°РµС‚ РІ СЃРїРµС†РёР°Р»СЊРЅСѓСЋ РїРѕР·РёС†РёСЋ РџРџ в„–1875. "
                    "Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹Рµ С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРєРё РЅРµ РґРѕРїСѓСЃРєР°СЋС‚СЃСЏ."
                ),
            }

        return {
            "can_add_extra_characteristics": True,
            "reason": (
                "РЎРІСЏР·Р°РЅРЅС‹Р№ РћРљРџР”2 РЅРµ РїРѕРїР°РґР°РµС‚ РІ СЃРїРµС†РёР°Р»СЊРЅС‹Рµ РїРѕР·РёС†РёРё РџРџ в„–1875. "
                "Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹Рµ С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРєРё РґРѕРїСѓСЃС‚РёРјС‹."
            ),
        }

    try:
        registry = ProcurementReferenceRegistry(REGISTRY_DIR)
    except Exception as e:
        print(f"РћС€РёР±РєР° РїСЂРё С‡С‚РµРЅРёРё registry: {e}")
        return {
            "error": f"РќРµ СѓРґР°Р»РѕСЃСЊ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°С‚СЊ registry. РћС€РёР±РєР°: {e}"
        }

    try:
        _, table_characteristics, ktry_codes = _parse_contract_characteristics(ooz_path)
    except Exception as e:
        return {
            "error": f"РќРµ СѓРґР°Р»РѕСЃСЊ СЂР°СЃРїР°СЂСЃРёС‚СЊ С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРєРё РёР· РћРћР—. РћС€РёР±РєР°: {e}"
        }

    result: dict[str, Any] = {}
    method_kind, method_label = _resolve_procurement_method(procurement_method)

    for code in ktry_codes:
        clean_code = _extract_site_ktru_code(code)
        if not clean_code:
            result[code] = "РќРµ СѓРґР°Р»РѕСЃСЊ РІС‹РґРµР»РёС‚СЊ РєРѕРґ РљРўР РЈ РґР»СЏ РїСЂРѕРІРµСЂРєРё РЅР° СЃР°Р№С‚Рµ"
            continue

        common_info: dict[str, Any] | None = None
        okpd_candidates: list[str] = []
        okpd_result: Any | None = None
        appendix: Optional[str] = None
        position_number: Optional[int] = None

        try:
            legal_characteristics = registry.get_ktru_characteristics_detailed(clean_code)
        except Exception as e:
            result[code] = f"РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРєРё РљРўР РЈ СЃ СЃР°Р№С‚Р°. РћС€РёР±РєР°: {e}"
            continue

        try:
            common_info = registry.get_ktru_common_info(clean_code)
            okpd_candidates = _extract_okpd2_candidates(common_info)
            if len(okpd_candidates) == 1:
                okpd_result = registry.check_okpd2(okpd_candidates[0])
                appendix = _detect_appendix(okpd_result)
                position_number = _parse_position_number(okpd_result)
        except Exception:
            common_info = None
            okpd_candidates = []
            okpd_result = None

        our_characteristics = table_characteristics.get(code) or {}
        if not our_characteristics:
            result[code] = "Р’ РћРћР— РЅРµ РЅР°Р№РґРµРЅС‹ С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРєРё РґР»СЏ СЌС‚РѕРіРѕ РљРўР РЈ"
            continue

        legal_lookup = _build_legal_lookup(legal_characteristics)
        field_errors: dict[str, str] = {}
        present_names = {_normalize_text(name) for name in our_characteristics}
        has_ktru_characteristics = bool(legal_lookup)
        rule_decision = _evaluate_extra_characteristics_rule(
            method_kind=method_kind,
            method_label=method_label,
            okpd_candidates=okpd_candidates,
            okpd_result=okpd_result,
            has_ktru_characteristics=has_ktru_characteristics,
        )
        can_add_extra_characteristics = rule_decision["can_add_extra_characteristics"]
        strict_extra_check = can_add_extra_characteristics is not True

        for our_name, our_raw_value in our_characteristics.items():
            legal_item = legal_lookup.get(_normalize_text(our_name))
            if legal_item is None:
                if strict_extra_check:
                    field_errors[our_name] = "РҐР°СЂР°РєС‚РµСЂРёСЃС‚РёРєР° РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚ РІ РљРўР РЈ РЅР° СЃР°Р№С‚Рµ"
                continue

            _, legal_values, _ = legal_item
            our_values = _split_contract_value(our_raw_value)
            invalid_values = [value for value in our_values if not _is_value_allowed(value, legal_values)]

            if invalid_values:
                legal_preview = ", ".join(legal_values[:20])
                if len(legal_values) > 20:
                    legal_preview += ", ..."
                field_errors[our_name] = (
                    f"РќРµРґРѕРїСѓСЃС‚РёРјРѕРµ Р·РЅР°С‡РµРЅРёРµ: {', '.join(invalid_values)}. "
                    f"Р”РѕРїСѓСЃС‚РёРјС‹Рµ Р·РЅР°С‡РµРЅРёСЏ РїРѕ РљРўР РЈ: {legal_preview}"
                )

        for normalized_name, (legal_name, _, required) in legal_lookup.items():
            if required and normalized_name not in present_names:
                field_errors[legal_name] = "РћС‚СЃСѓС‚СЃС‚РІСѓРµС‚ РѕР±СЏР·Р°С‚РµР»СЊРЅР°СЏ С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРєР° РљРўР РЈ"

        result[code] = {
            "procurement_method": method_label or None,
            "selected_okpd2": okpd_candidates[0] if len(okpd_candidates) == 1 else None,
            "matched_okpd2": getattr(okpd_result, "matched_okpd2", None),
            "okpd2_candidates": okpd_candidates,
            "has_ktru_characteristics": has_ktru_characteristics,
            "pp1875_appendix": appendix,
            "pp1875_position_number": position_number,
            "can_add_extra_characteristics": can_add_extra_characteristics,
            "reason": rule_decision["reason"],
            "field_errors": field_errors,
        }

    return result


