import re
from pathlib import Path
from typing import Any, Dict, Optional

from new_model.embeddings import get_embeddings
from new_model.parser_functions import DocumentParser, PlanParser
from new_model.retriever import Retriever, BM25TextRetriever

from govno_model.rag_processing import process_rag_points
from govno_model.smart_processing import process_smart_points
from services.procurement_reference_registry import ProcurementReferenceRegistry

BASE_DIR = Path(__file__).resolve().parent.parent
REGISTRY_DIR = BASE_DIR / "data" / "parsed_tables"

def parse_okpd_entries(text: str):
    result = []
    for item in text.split(":")[1].split(";"):
        item = item.strip()
        if not item:
            continue

        code, name = item.split(" - ", 1)
        result.append({
            "okpd2": code.strip(),
            "name": name.strip(),
        })
    return result

def parse_ktry_entries(text: str):
    result = []
    for item in text.split(":")[1].split(";"):
        item = item.strip()
        if not item:
            continue

        code, name = item.split(" - ", 1)
        result.append({
            "ktru_code": code.strip(),
            "name": name.strip(),
        })
    return result

def _clean_keyword_dict(items_by_key: Dict[str, list[str]]) -> str:
    clean_items = []
    for key in items_by_key:
        for item in items_by_key[key]:
            item = item.strip()
            item = re.sub(r"\s*;\s*", "; ", item)
            item = re.sub(r"(;\s*){2,}", "; ", item)
            item = item.rstrip("; ").strip()
            if item:
                clean_items.append(item)

    return "\n".join(dict.fromkeys(clean_items))


def _extract_keyword_windows(text: str, keywords: list[str], window: int = 90) -> str:
    matches: list[str] = []
    for keyword in keywords:
        pattern = re.compile(rf"({re.escape(keyword)}[\s\S]{{0,{window}}})", re.IGNORECASE)
        for match in pattern.findall(text):
            clean_match = re.sub(r"\s+", " ", match).strip(" ;,\n\t")
            if clean_match:
                matches.append(clean_match)

    return "\n".join(dict.fromkeys(matches))


class AIService:
    def process_query(
        self,
        plan_path: str,
        contract_path: str,
        ooz_path: str,
        zapiska_path: str,
        ONMCK_path: str,
        Obrasheniye_path: str,
    ) -> Dict[str, Any]:
        
        # -----------------------------------------------------------------------
        #                               ПЛАН-ГРАФИК
        # -----------------------------------------------------------------------
        parser_plan = PlanParser(plan_path)
        plan_points = parser_plan.extract_table_kv_from_docx()
        if not plan_points:
            raise ValueError("Не удалось извлечь данные из плана-графика: ТАБЛИЦЫ ПУСТЫ ИЛИ НЕ НАЙДЕНЫ")

        smart_keywords = [
            "Код ОКПД",
            "Код позиции КТРУ",
            "Количество",
        ]
        rag_keywords = [
            "Сроки поставки",
            "цена контракта",
        ]

        plan_points_use = [
            plan_point
            for plan_point in plan_points
            if any(keyword.lower() in plan_point.lower() for keyword in smart_keywords)
        ]

        plan_points_str = "\n".join(plan_points_use).strip()
        if not plan_points_str:
            plan_points_str = "В плане-графике отсутствуют ОКПД, КТРУ или количество"

        plan_points_rag = [
            plan_point
            for plan_point in plan_points
            if any(keyword.lower() in plan_point.lower() for keyword in rag_keywords)
        ]
        # -----------------------------------------------------------------------
        #                               КОНТРАКТ
        # -----------------------------------------------------------------------
        parser_contract = DocumentParser(contract_path)
        ktru_okpd = parser_contract.extract_table_cells_by_keyword(["ОКПД", "КТРУ"])
        contract_points = _clean_keyword_dict(ktru_okpd)
        if not contract_points:
            contract_plain_text = parser_contract.extract_clean_text().strip()
            contract_points = _extract_keyword_windows(
                contract_plain_text,
                keywords=["КТРУ", "ОКПД"],
                window=90,
            )
        if not contract_points:
            contract_points = "В контракте не найдены КТРУ и ОКПД"


        # -----------------------------------------------------------------------
        #                                   ООЗ
        # -----------------------------------------------------------------------
        parser_ooz = DocumentParser(ooz_path)
        tables_ooz = parser_ooz.extract_table_cells_by_keyword(["ОКПД", "КТРУ"])
        ooz_points = _clean_keyword_dict(tables_ooz)
        if not ooz_points:
            ooz_plain_text = parser_ooz.extract_clean_text().strip()
            ooz_amounts = parser_ooz.extract_tables_columns(keywords=["наименование товара", "количество"])

            ooz_points = _extract_keyword_windows(
                ooz_plain_text,
                keywords=["КТРУ", "ОКПД"],
                window=90,
            )
            if ooz_amounts:
                ooz_points = ooz_points + "\n" + ooz_amounts
            
        if not ooz_points:
            ooz_points = "В ООЗ не найдены КТРУ или ОКПД"

        # -----------------------------------------------------------------------
        #                          ПОЯСНИТЕЛЬНАЯ ЗАПИСКА
        # -----------------------------------------------------------------------
        parser_zapiska = DocumentParser(zapiska_path)
        paragraphs_zapiska = parser_zapiska.extract_clean_text()
        tables_zapiska = parser_zapiska.table_to_markdown()
        zapiska_full_text = ("Название: " + paragraphs_zapiska + "\n\n" + tables_zapiska).strip()
        if not zapiska_full_text:
            zapiska_full_text = "Не удалось извлечь данные из записки"

        # -----------------------------------------------------------------------
        #                               ОНМЦК
        # -----------------------------------------------------------------------
        parser_onmck = DocumentParser(ONMCK_path)
        table_onmck = parser_onmck.extract_rows_region(keyword="шт.")

# -----------------------------------------------------------------------
#                         ПРОВЕРКА КТРУ ОКПД НА САЙТЕ
# -----------------------------------------------------------------------
        registry = ProcurementReferenceRegistry(REGISTRY_DIR)
        parsed_okpd = parse_okpd_entries(plan_points_use[0])
        parsed_ktry = parse_ktry_entries(plan_points_use[1])

        res_ktry = []
        res_okpd = []

        for entry in parsed_ktry:
            try:
                res = registry.check_ktru(entry["ktru_code"], entry["name"])
                res_ktry.append(res.message)
            except Exception:
                res_ktry.append(
                    f"Возникли проблемы с доступом к сайту при проверке КТРУ {entry['ktru_code']}."
                )

        for entry in parsed_okpd:
            try:
                res = registry.check_okpd2(entry["okpd2"], entry["name"])
                res_okpd.append(res.message)
            except Exception:
                res_okpd.append(
                    f"Возникли проблемы с доступом к сайту при проверке ОКПД2 {entry['okpd2']}."
                )

        ktry_check_result = "\n---\n".join(res_ktry)
        okpd_check_result = "\n---\n".join(res_okpd)   
# -----------------------------------------------------------------------
#                              КТРУ ОКПД часть
# -----------------------------------------------------------------------
        smart_answer = process_smart_points(
            plan_points=plan_points_str,
            contract_points=contract_points,
            OOZ_points=ooz_points,
            zapiska_points=zapiska_full_text,
            ONMCK_points=table_onmck,
        )

# -----------------------------------------------------------------------
#                                    RAG часть
# -----------------------------------------------------------------------
        parser_Obrasheniye = DocumentParser(Obrasheniye_path)
        Obrasheniye_full_text = parser_Obrasheniye.extract_clean_text().strip()
        if not Obrasheniye_full_text:
            Obrasheniye_full_text = "Не удалось извлечь данные из обращения о проведении закупки"
        contract_full_text = parser_contract.extract_clean_text().strip()
        ooz_plain_text = parser_ooz.extract_clean_text()
        onmck_plain_text = parser_onmck.extract_clean_text()
        rag_answer = ""
        if plan_points_rag:
            # faiss = Retriever(embeddings=get_embeddings())
            # retriever = faiss.create_retriever(
            #     texts=[contract_full_text, zapiska_full_text, ooz_plain_text, onmck_plain_text],
            #     n=17,
            #     sources = ["Контракт", "Пояснительная записка", "ООЗ", "ОНМЦК"]
            #     )
            bm25 = BM25TextRetriever()
            retriever = bm25.create_retriever(
                texts=[contract_full_text, zapiska_full_text, ooz_plain_text, onmck_plain_text, Obrasheniye_full_text],
                n=7,
                sources = ["Контракт", "Пояснительная записка", "ООЗ", "ОНМЦК", "Обращение о проведении закупки"]
            )
            rag_answer = process_rag_points(retriever, plan_points_rag)


# -----------------------------------------------------------------------
#                            Ответ
# -----------------------------------------------------------------------
        final_parts = [part for part in [smart_answer, rag_answer] if part]
        final_response = "\n\n".join(final_parts)

        final_response = (
            "<b>===== ПРОВЕРКА КТРУ НА САЙТАХ =====</b>\n\n"
            + ktry_check_result
            + "\n----------------------------------------------------------------------------------\n"
            + "\n----------------------------------------------------------------------------------\n"
            + "<b>===== ПРОВЕРКА ОКПД НА САЙТАХ =====</b>\n\n"
            + okpd_check_result
            + "\n----------------------------------------------------------------------------------\n"
            + "\n----------------------------------------------------------------------------------\n"
            + "\n<b>===== АНАЛИЗ ДОКУМЕНТОВ МОДЕЛЬЮ =====</b>\n"
            + final_response
        )

        return {"ai_response": final_response}


_ai_service_instance: Optional[AIService] = None


def get_ai_service() -> AIService:
    global _ai_service_instance
    if _ai_service_instance is None:
        _ai_service_instance = AIService()
    return _ai_service_instance
