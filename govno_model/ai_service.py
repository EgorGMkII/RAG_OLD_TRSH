import re
from pathlib import Path
from typing import Any, Dict, Optional, List

from new_model.parser_functions import DocumentParser, PlanParser, parse_okpd_entries, parse_ktry_entries, _clean_keyword_dict, _extract_keyword_windows
from new_model.retriever import Retriever, BM25TextRetriever

from govno_model.docs_parsing import _parse_plan_points, _parse_contract_points, _parse_ooz_points, _parse_zapiska_text, _parse_onmck_text
from govno_model.rag_processing import process_rag_points
from govno_model.smart_processing import process_smart_points
from govno_model.check_registry import get_regestry_response_okpd_ktry

BASE_DIR = Path(__file__).resolve().parent.parent
REGISTRY_DIR = BASE_DIR / "data" / "parsed_tables"

def filter_plan_points(plan_points: List[str], keywords: List[str]) -> List[str]:
    plan_points_use = [
        plan_point
        for plan_point in plan_points
        if any(keyword.lower() in plan_point.lower() for keyword in keywords)
    ]
    return plan_points_use


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
        try:
            plan_points = _parse_plan_points(plan_path)
        except Exception as e:
            plan_points = [f"Ошибка при парсинге плана-графика: {str(e)}"]

        smart_keywords = [
            "Код ОКПД",
            "Код позиции КТРУ",
            "Количество",
        ]
        rag_keywords = [
            "Сроки поставки",
            "цена контракта",
        ]

        plan_points_use = filter_plan_points(plan_points, smart_keywords)
        plan_points_str = "\n".join(plan_points_use).strip()

        if not plan_points_str:
            plan_points_str = "В плане-графике отсутствуют ОКПД, КТРУ или количество"

        plan_points_rag = filter_plan_points(plan_points, rag_keywords)
        # -----------------------------------------------------------------------
        #            ПУНКТЫ КОНТРАКТА, ООЗ, ЗАПИСКИ, ОНМЦК
        # -----------------------------------------------------------------------
        try:
            contract_points = _parse_contract_points(contract_path)
        except Exception as e:
            contract_points = [f"Ошибка при парсинге контракта: {str(e)}"]

        try:
            ooz_points = _parse_ooz_points(ooz_path)
        except Exception as e:
            ooz_points = [f"Ошибка при парсинге ООЗ: {str(e)}"]

        try:
            zapiska_points = _parse_zapiska_text(zapiska_path)
        except Exception as e:
            zapiska_points = [f"Ошибка при парсинге пояснительной записки: {str(e)}"]

        try:
            ONMCK_points = _parse_onmck_text(ONMCK_path)
        except Exception as e:
            ONMCK_points = [f"Ошибка при парсинге ОНМЦК: {str(e)}"]

        

# -----------------------------------------------------------------------
#                         ПРОВЕРКА КТРУ ОКПД НА САЙТЕ
# -----------------------------------------------------------------------
        res_ktry, res_okpd = get_regestry_response_okpd_ktry(plan_points_use, REGISTRY_DIR)
        # res_ktry, res_okpd = "бе", "ме"
        ktry_check_result = "\n-----------------------------------------------------------------------\n".join(res_ktry)
        okpd_check_result = "\n-----------------------------------------------------------------------\n".join(res_okpd)   
# -----------------------------------------------------------------------
#                              КТРУ ОКПД часть
# -----------------------------------------------------------------------
        smart_answer = process_smart_points(
            plan_points=plan_points_str,
            contract_points=contract_points,
            OOZ_points=ooz_points,
            zapiska_points=zapiska_points,
            ONMCK_points=ONMCK_points,
        )

# -----------------------------------------------------------------------
#                                 RAG часть
# -----------------------------------------------------------------------
        parser_contract = DocumentParser(contract_path)
        parser_ooz = DocumentParser(ooz_path)
        parser_onmck = DocumentParser(ONMCK_path)
        parser_Obrasheniye = DocumentParser(Obrasheniye_path)

        Obrasheniye_full_text = parser_Obrasheniye.extract_clean_text().strip()
        if not Obrasheniye_full_text:
            Obrasheniye_full_text = "Не удалось извлечь данные из обращения о проведении закупки"
        
        contract_full_text = parser_contract.extract_clean_text().strip()
        if not contract_full_text:
            contract_full_text = "Не удалось извлечь данные из текста контракта"
        
        ooz_plain_text = parser_ooz.extract_clean_text().strip()
        if not ooz_plain_text:
            ooz_plain_text = "Не удалось извлечь данные из документа ООЗ"
        
        onmck_plain_text = parser_onmck.extract_clean_text().strip()
        if not onmck_plain_text:
            onmck_plain_text = "Не удалось извлечь данные из ОНМЦК"

        rag_answer = ""
        if plan_points_rag:
            bm25 = BM25TextRetriever()
            retriever = bm25.create_retriever(
                texts=[contract_full_text, zapiska_points, ooz_plain_text, onmck_plain_text, Obrasheniye_full_text],
                n=7,
                sources = ["Проект контракта", "Пояснительная записка", "ООЗ", "ОНМЦК", "Обращение о проведении закупки"]
            )
            rag_answer = process_rag_points(retriever, plan_points_rag)

# -----------------------------------------------------------------------
#                 Ответ: Проверка КТРУ и ОКПД + SMART + RAG
# -----------------------------------------------------------------------
        final_parts = [part for part in [smart_answer, rag_answer] if part]
        final_response = "\n\n".join(final_parts)

        final_response = (
            "<b>1) Проверка КТРУ через сервис zakupki.gov.ru:</b>\n\n"
            + ktry_check_result
            + "\n\n"
            + "\n<b>2) Проверка ОКПД на вхождение в постановление 1875:</b>\n\n"
            + okpd_check_result
            + "\n\n"
            + "\n<b>3) Внутренний анализ перечня документов:</b>\n"
            + final_response
        )

        return {"ai_response": final_response}


_ai_service_instance: Optional[AIService] = None


def get_ai_service() -> AIService:
    global _ai_service_instance
    if _ai_service_instance is None:
        _ai_service_instance = AIService()
    return _ai_service_instance
