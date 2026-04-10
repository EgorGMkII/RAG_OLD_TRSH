import re
from typing import Any, Dict, Optional

from new_model.embeddings import get_embeddings
from new_model.parser_functions import DocumentParser, PlanParser
from new_model.retriever import Retriever

from govno_model.rag_processing import process_rag_points
from govno_model.smart_processing import process_smart_points


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


class AIService:
    def process_query(
        self,
        plan_path: str,
        contract_path: str,
        ooz_path: str,
        zapiska_path: str,
        ONMCK_path: str,
    ) -> Dict[str, Any]:
        parser_contract = DocumentParser(contract_path)
        ktru_okpd = parser_contract.extract_table_cells_by_keyword(["ОКПД", "КТРУ"])
        contract_points = _clean_keyword_dict(ktru_okpd)
        if not contract_points:
            raise ValueError("Не удалось извлечь КТРУ/ОКПД из контракта")

        parser_plan = PlanParser(plan_path)
        plan_points = parser_plan.extract_table_kv_from_docx()
        if not plan_points:
            raise ValueError("Не удалось извлечь данные из плана-графика: plan_points пуст")

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
        plan_points_rag = [
            plan_point
            for plan_point in plan_points
            if any(keyword.lower() in plan_point.lower() for keyword in rag_keywords)
        ]

        plan_points_str = "\n".join(plan_points_use).strip()
        if not plan_points_str:
            raise ValueError("После фильтрации не осталось smart-пунктов плана-графика")

        parser_ooz = DocumentParser(ooz_path)
        tables_ooz = parser_ooz.extract_table_cells_by_keyword(["ОКПД", "КТРУ"])
        ooz_points = _clean_keyword_dict(tables_ooz)
        if not ooz_points:
            raise ValueError("Не удалось извлечь КТРУ/ОКПД из ООЗ")

        parser_zapiska = DocumentParser(zapiska_path)
        paragraphs_zapiska = parser_zapiska.extract_clean_text()
        tables_zapiska = parser_zapiska.table_to_markdown()
        zapiska_full_text = ("Название: " + paragraphs_zapiska + "\n\n" + tables_zapiska).strip()
        if not zapiska_full_text:
            raise ValueError("Не удалось извлечь данные из записки")

        parser_onmck = DocumentParser(ONMCK_path)
        table_onmck = parser_onmck.extract_rows_region(keyword="шт.")

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
        paragraphs_contract = parser_contract.extract_clean_text()
        contract_full_text = paragraphs_contract.strip()
        ooz_plain_text = parser_ooz.extract_clean_text()
        onmck_plain_text = parser_onmck.extract_clean_text()
        rag_answer = ""
        if plan_points_rag:
            faiss = Retriever(embeddings=get_embeddings())
            retriever = faiss.create_retriever(
                texts=[contract_full_text, zapiska_full_text, ooz_plain_text, onmck_plain_text],
                n=17,
                sources = ["Контракт", "Пояснительная записка", "ООЗ", "ОНМЦК"]
                )
            rag_answer = process_rag_points(retriever, plan_points_rag)


# -----------------------------------------------------------------------
#                            Ответ
# -----------------------------------------------------------------------
        final_parts = [part for part in [smart_answer, rag_answer] if part]
        return {"ai_response": "\n\n".join(final_parts)}


_ai_service_instance: Optional[AIService] = None


def get_ai_service() -> AIService:
    global _ai_service_instance
    if _ai_service_instance is None:
        _ai_service_instance = AIService()
    return _ai_service_instance
