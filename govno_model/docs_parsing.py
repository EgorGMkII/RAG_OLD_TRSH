# _parse_plan_points(...)
# _parse_contract_points(...)
# _parse_ooz_points(...)
# _parse_zapiska_text(...)
# _parse_onmck_text(...)
# _parse_obrasheniye_text(...)
from typing import List
from new_model.parser_functions import DocumentParser, PlanParser
from new_model.parser_functions import extract_ktru_block, _clean_keyword_dict, _extract_keyword_windows


def _parse_plan_points(plan_path: str) -> List[str]:
    parser_plan = PlanParser(plan_path)
    plan_points = parser_plan.extract_table_kv_from_docx()
    if not plan_points:
        raise ValueError("Не удалось извлечь данные из плана-графика: ТАБЛИЦЫ ПУСТЫ ИЛИ НЕ НАЙДЕНЫ")

    return plan_points

def _parse_contract_points(contract_path: str, window: int = 100) -> str:
    parser_contract = DocumentParser(contract_path)
    ktru_okpd = parser_contract.extract_table_cells_by_keyword(["ОКПД", "КТРУ"])
    contract_points = _clean_keyword_dict(ktru_okpd)
    if not contract_points:
        contract_plain_text = parser_contract.extract_clean_text().strip()
        contract_points = _extract_keyword_windows(
            contract_plain_text,
            keywords=["ОКПД"],
            window=window,
        )
        contract_points += extract_ktru_block(contract_plain_text, tail_chars=30, fallback_chars=150)

        table_contract_points = parser_contract.extract_tables_columns(keywords=["ОКПД", "КТРУ"])
        if table_contract_points:
            contract_points = contract_points + "\n" + table_contract_points
        if not contract_points:
            contract_points = "В контракте не найдены КТРУ и ОКПД"

    return contract_points

def _parse_ooz_points(ooz_path: str, window: int = 200) -> str:
    parser_ooz = DocumentParser(ooz_path)
    tables_ooz = parser_ooz.extract_table_cells_by_keyword(["ОКПД", "КТРУ"])
    ooz_points = _clean_keyword_dict(tables_ooz)
    if not ooz_points:
        ooz_plain_text = parser_ooz.extract_clean_text().strip()
        ooz_amounts = parser_ooz.extract_tables_columns(keywords=["наименование товара", "количество", "ОКПД", "КТРУ"])
        ooz_points = _extract_keyword_windows(
            ooz_plain_text,
            keywords=["ОКПД"],
            window=window,
        )
        ooz_points += extract_ktru_block(ooz_plain_text, tail_chars=30, fallback_chars=150)
        
        if ooz_amounts:
            ooz_points = ooz_points + "\n" + ooz_amounts
        
    if not ooz_points:
        ooz_points = "В ООЗ не найдены КТРУ или ОКПД"

    return ooz_points

def _parse_zapiska_text(zapiska_path: str) -> str:
    parser_zapiska = DocumentParser(zapiska_path)
    paragraphs_zapiska = parser_zapiska.extract_clean_text()
    tables_zapiska = parser_zapiska.table_to_markdown()
    zapiska_full_text = ("Название: " + paragraphs_zapiska + "\n\n" + tables_zapiska).strip()
    if not zapiska_full_text:
        zapiska_full_text = "Не удалось извлечь данные из записки"

    return zapiska_full_text


def _parse_onmck_text(ONMCK_path: str) -> str:
    parser_onmck = DocumentParser(ONMCK_path)
    table_onmck = parser_onmck.extract_rows_region(keyword="шт.")
    if not table_onmck:
        table_onmck = parser_onmck.extract_tables_columns(keywords=["наименование товара", "Ед.", "Единиц", "Кол-во", "Количество"])
    
    return table_onmck