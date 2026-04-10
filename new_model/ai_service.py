
from .parser_functions import PlanParser, DocumentParser
from .retriever import Retriever
from .embeddings import get_embeddings
from langchain_core.runnables import RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from operator import itemgetter
from .prompts import prompt
from .llm_models import get_langchain_chat_model
from typing import Dict, Any, Optional

class AIService:    

    def process_query(self, doc1_path: str, doc2_path: str) -> Dict[str, Any]:
        """ 
        doc1 - Заявка на внесение в план-график \n
        doc2 - Контракт
        """
        parser_contract = DocumentParser(doc2_path)
        paragraphs_contract = parser_contract.extract_clean_text()
        tables_contract = parser_contract.table_to_markdown()
        contract_full_text = ("Название: " + paragraphs_contract + "\n\n" + tables_contract).strip()

        if not contract_full_text:
            raise ValueError("Не удалось извлечь данные из контракта: contract_full_text пуст")

        parser_plan = PlanParser(doc1_path)
        plan_points = parser_plan.extract_table_kv_from_docx()
        if not plan_points:
            raise ValueError("Не удалось извлечь данные из плана-графика: plan_points пуст")
        
        key_words = [
            "Наименование объекта закупки",
            "Код позиции КТРУ",
            "Количество",
            "Сроки поставки товара",
            "Место поставки товара"
            ]
        
        # оставлю только адекватные
        plan_points = [
            plan_point
            for plan_point in plan_points
            if any(kw.lower() in plan_point.lower() for kw in key_words)
        ]
        if not plan_points:
            raise ValueError("После фильтрации не осталось подходящих пунктов плана-графика")

        faiss = Retriever(embeddings=get_embeddings())
        retriever = faiss.create_retriever(texts=[contract_full_text], n=10)

        def format_chunks(docs):
            return "\n\n".join(
                f"[chunk_id={i}]\n{d.page_content}"
                for i, d in enumerate(docs)
            )
        
        llm = get_langchain_chat_model()

        rag_chain = (
            {
                "point_index": itemgetter("point_index"),
                "plan_point": itemgetter("plan_point"),
                "context": itemgetter("plan_point") | retriever | RunnableLambda(format_chunks),
            }
            | prompt
            | llm
            | StrOutputParser()
        )

        answers = []
        for index, point in enumerate(plan_points, start=1):
            answer = rag_chain.invoke({"point_index": index, "plan_point": point})
            answers.append(answer.strip())

        merged_answers = "\n\n".join(answers)
        return {"ai_response": merged_answers}


_ai_service_instance: Optional[AIService] = None

def get_ai_service() -> AIService:
    global _ai_service_instance
    if _ai_service_instance is None:
        _ai_service_instance = AIService()
    return _ai_service_instance
