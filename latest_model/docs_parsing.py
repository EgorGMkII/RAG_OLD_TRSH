import numpy as np
from typing import List
from shared_modules.parser_functions import DocumentParser, PlanParser
from shared_modules.parser_functions import extract_ktru_block, _clean_keyword_dict, _extract_keyword_windows
from shared_modules.parser_functions import parse_contracters_onmck_by_row_number


def _parse_plan_points(plan_path: str) -> List[str]:
    parser_plan = PlanParser(plan_path)
    plan_points = parser_plan.extract_table_kv_from_docx()
    if not plan_points:
        raise ValueError("РќРµ СѓРґР°Р»РѕСЃСЊ РёР·РІР»РµС‡СЊ РґР°РЅРЅС‹Рµ РёР· РїР»Р°РЅР°-РіСЂР°С„РёРєР°: РўРђР‘Р›РР¦Р« РџРЈРЎРўР« РР›Р РќР• РќРђР™Р”Р•РќР«")

    return plan_points

def _parse_contract_characteristics(contract_path: str) -> str:
    """
    Р”РѕСЃС‚Р°С‘С‚ РҐР°СЂР°РєС‚СЂРµСЂРёСЃС‚РёРєРё С‚РѕРІР°СЂРѕРІ РёР· РљРѕРЅС‚СЂР°РєС‚Р°
    """
    parser_contract = DocumentParser(contract_path)

    table_ktry_names = parser_contract.extract_tables_columns(keywords=["в„–", "РћРљРџР”", "РљРўР РЈ"])

    table_characteristics, ktry_codes = parser_contract.extract_tables_characteristics(keywords=["в„–", "РљРўР РЈ", "РќР°РёРјРµРЅРѕРІР°РЅРёРµ С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРєРё", "Р—РЅР°С‡РµРЅРёРµ С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРєРё"])

    ktry_codes = {code for code in ktry_codes if len(code.split("-"))>1}
    table_characteristics = {ktry_code: table_characteristics[ktry_code] for ktry_code in ktry_codes}
    
    return table_ktry_names, table_characteristics, ktry_codes

def _parse_contract_points(contract_path: str, window: int = 100) -> str:
    """
    Р”РѕСЃС‚Р°С‘С‚ РљРўР РЈ, РћРљРџР” Рё РєРѕР»РёС‡РµСЃРІС‚Рѕ С‚РѕРІР°СЂРѕРІ РёР· РєРѕРЅС‚СЂР°РєС‚Р°
    РЇ С…Р· РЅР°РґРѕ Р±С‹ РІРёРєСЃРёС‚СЊ Р»РѕРіРёРєСѓ
    """
    parser_contract = DocumentParser(contract_path)
    # СЃРЅР°С‡Р°Р»Р° РїРѕРїС‹С‚РєР° - РІС‚СѓРїСѓСЋ СЏС‡РµР№РєРё РєС‚СЂСѓ РЅР°Р№С‚Рё
    ktru_okpd = parser_contract.extract_table_cells_by_keyword(["РћРљРџР”", "РљРўР РЈ"])
    contract_points = _clean_keyword_dict(ktru_okpd)
    # Р•СЃР»Рё РЅРµС‚, РёС‰С‘Рј РґСЂСѓРіРёРµ СЃРїРѕСЃРѕР±С‹
    if not contract_points or len(contract_points) < 20:
        print(contract_points)
        contract_plain_text = parser_contract.extract_clean_text().strip()
        contract_points = _extract_keyword_windows(
            contract_plain_text,
            keywords=["РћРљРџР”"],
            window=window,
        )
        contract_points += extract_ktru_block(contract_plain_text, tail_chars=60, fallback_chars=150)

        table_contract_points = parser_contract.extract_tables_columns(keywords=["в„–", "РћРљРџР”", "РљРўР РЈ"])
        table_contract_points_amount = parser_contract.extract_tables_columns(keywords=["в„–", "РќР°РёРјРµРЅРѕРІР°РЅРёРµ С‚РѕРІР°СЂР°", "РљРѕР»РёС‡РµСЃС‚РІРѕ"])

        table_contract_points_amount_2 = parser_contract.extract_tables_columns(keywords=["РќР°РёРјРµРЅРѕРІР°РЅРёРµ РїСЂРѕРґСѓРєС†РёРё", "РљРѕР»-РІРѕ"])
        table_contract_points_amount_3 = parser_contract.extract_tables_columns(keywords=["РќР°РёРјРµРЅРѕРІР°РЅРёРµ,", "РљРѕР»РёС‡РµСЃС‚РІРѕ"])

        if table_contract_points:
            contract_points = contract_points + "\n" + table_contract_points
        if table_contract_points_amount:
            contract_points = contract_points + "\n" + table_contract_points_amount
        if table_contract_points_amount_2:
            contract_points = contract_points + "\n" + table_contract_points_amount_2
        if table_contract_points_amount_3:
            contract_points = contract_points + "\n" + table_contract_points_amount_3
        if not contract_points:
            contract_points = "Р’ РєРѕРЅС‚СЂР°РєС‚Рµ РЅРµ РЅР°Р№РґРµРЅС‹ РљРўР РЈ Рё РћРљРџР”"

    else: # Р‘Р Р•Р”
        table_contract_points_amount_3 = parser_contract.extract_tables_columns(keywords=["РќР°РёРјРµРЅРѕРІР°РЅРёРµ,", "РљРѕР»РёС‡РµСЃС‚РІРѕ"])
        contract_points = contract_points + "\n" + table_contract_points_amount_3

    return contract_points


def _parse_ooz_points(ooz_path: str, window: int = 200) -> str:
    parser_ooz = DocumentParser(ooz_path)
    tables_ooz = parser_ooz.extract_table_cells_by_keyword(["РћРљРџР”", "РљРўР РЈ"])
    ooz_points = _clean_keyword_dict(tables_ooz)
    if not ooz_points or len(ooz_points) < 20:
        # print("BLYAD")
        ooz_plain_text = parser_ooz.extract_clean_text().strip()
        ooz_ktry_okpd_table = parser_ooz.extract_tables_columns(keywords=["в„–", "РћРљРџР”", "РљРўР РЈ"])

        ooz_amounts = parser_ooz.extract_tables_columns(keywords=["в„–", "РЅР°РёРјРµРЅРѕРІР°РЅРёРµ С‚РѕРІР°СЂР°", "РєРѕР»РёС‡РµСЃС‚РІРѕ"])
        if not ooz_amounts:
            ooz_amounts = parser_ooz.extract_tables_columns(keywords=["РЅР°РёРјРµРЅРѕРІР°РЅРёРµ", "РєРѕР»РёС‡РµСЃС‚РІРѕ"])

        ooz_points = _extract_keyword_windows(
            ooz_plain_text,
            keywords=["РћРљРџР”"],
            window=window,
        )
        ooz_points = ooz_points + "\n" + extract_ktru_block(ooz_plain_text, tail_chars=30, fallback_chars=150)

        if ooz_ktry_okpd_table:
            ooz_points = ooz_points + "\n" + ooz_ktry_okpd_table

        if ooz_amounts:
            ooz_points = ooz_points + "\n" + ooz_amounts

    else: # GOVNO
        ooz_amounts = parser_ooz.extract_tables_columns(keywords=["РќР°РёРјРµРЅРѕРІР°РЅРёРµ,", "РљРѕР»РёС‡РµСЃС‚РІРѕ"])
        ooz_points = ooz_points + "\n" + ooz_amounts

    if not ooz_points:
        ooz_points = "Р’ РћРћР— РЅРµ РЅР°Р№РґРµРЅС‹ РљРўР РЈ РёР»Рё РћРљРџР”"

    return ooz_points


def _parse_zapiska_text(zapiska_path: str) -> str:
    parser_zapiska = DocumentParser(zapiska_path)
    paragraphs_zapiska = parser_zapiska.extract_clean_text()
    tables_zapiska = parser_zapiska.table_to_markdown()
    zapiska_full_text = ("РќР°Р·РІР°РЅРёРµ: " + paragraphs_zapiska + "\n\n" + tables_zapiska).strip()
    if not zapiska_full_text:
        zapiska_full_text = "РќРµ СѓРґР°Р»РѕСЃСЊ РёР·РІР»РµС‡СЊ РґР°РЅРЅС‹Рµ РёР· Р·Р°РїРёСЃРєРё"

    return zapiska_full_text


def _parse_onmck_text(ONMCK_path: str) -> str:
    parser_onmck = DocumentParser(ONMCK_path)
    table_onmck = parser_onmck.extract_rows_region(keyword="С€С‚")
    if not table_onmck:
        table_onmck = parser_onmck.extract_tables_columns(
            keywords=["РЅР°РёРјРµРЅРѕРІР°РЅРёРµ С‚РѕРІР°СЂР°", "Р•Рґ.", "Р•РґРёРЅРёС†", "РљРѕР»-РІРѕ", "РљРѕР»РёС‡РµСЃС‚РІРѕ"]
        )

    return table_onmck


def _parse_onmck_pricies(ONMCK_path: str) -> str:
    pricies = parse_contracters_onmck_by_row_number(ONMCK_path)
    result_lines = []
    error_lines = []

    name_width = max(len(k) for k in pricies)
    var_width = 5
    for k, v in pricies.items():
        mu, std = np.mean(v), np.std(v)
        std = np.sqrt(np.sum(np.square(v-mu)/(len(v)-1)))

        var_coeff = (100 * std / (mu + 1e-7))
        var_coeff = np.round(var_coeff, 2)

        if var_coeff >= 33:
            result = (
                f"{k:<{name_width}} | "
                + "<error>"
                + f"РєРѕСЌС„С„РёС†РёРµРЅС‚ РІР°СЂРёР°С†РёРё: {var_coeff:>{var_width}}% | "
                + "</error>"
                + f"Р¦РµРЅС‹: {v}"
            )
            error_lines.append(
                "<error>"
                + "Р’РЅРёРјР°РЅРёРµ! РљРѕСЌС„С„РёС†РёРµРЅС‚ РІР°СЂРёР°С†РёРё РІ 33% РїСЂРµРІС‹С€РµРЅ | "
                + f"{k:<{name_width}} | Р’Р°СЂРёР°С†РёСЏ С†РµРЅ РїРѕСЃС‚Р°РІС‰РёРєРѕРІ: {var_coeff}%"
                + "</error>"
            )
        else:
            result = (
                
                f"{k:<{name_width}} | "
                + "<ok>"
                + f"РєРѕСЌС„С„РёС†РёРµРЅС‚ РІР°СЂРёР°С†РёРё: {var_coeff:>{var_width}}%"
                + "</ok>" + " | "
                + f"Р¦РµРЅС‹: {v}"
            )

        result_lines.append(result)


    return "\n".join(result_lines + error_lines)

