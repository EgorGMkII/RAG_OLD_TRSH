from typing import Optional, List, Dict, Any

#rm
from time import sleep
##your imports
import requests
from gigachat import GigaChat
from parser_functions import *
from sentence_transformers import SentenceTransformer, util

##imports end

class AIService:    
    ready = False

    def __init__(self):
        self._initialize()
    
    def _initialize(self) -> None:
        # fill in initialization if needed

        #
        self.ready = True


    def is_ready(self) -> bool:
        return self.ready
    
    #doc1 - Заявка на внесение в план-график
    #doc2 - Контракт
    def process_query(self, doc1_path: str, doc2_path: str, use_vectorization: bool) -> Dict[str, Any]:
        ##processing
        parser_contract = ContractParser(doc1_path)
        paragraphs_contract = parser_contract.extract_clean_text(chunk_size = 40)
        tables_contract = parser_contract.extract_table_kv_from_docx()
        contract_chunks = paragraphs_contract + tables_contract

        parser_plan = PlanParser(doc2_path)
        plan_points = parser_plan.extract_table_kv_from_docx()

        closest_k = find_similar_k(plan_points, contract_chunks, use_vectorization=True)
        if not closest_k:
            return {'ai_response': "Не удалось найти соответствия между пунктами."}
        
        AUTH_KEY  = "MDE5YTYzYWMtOTI1OS03MjgzLTgxODctNzhlYjIzMGI4MGIzOmVlOTY5ZGM4LWY1ODUtNGNjNC1hODA3LWNjMGU4N2U1ZmMyZA=="

        giga = GigaChat(verify_ssl_certs=False,credentials=AUTH_KEY, model=None)   
        all_responses = []    

        system_prompt = (
            "Ты — юридический помощник, специализирующийся на анализе договоров. "
            "Твоя цель — проверять соответствие между пунктами плана-графика и разделами контракта. "
            "Обращай внимание даже на неявные совпадения (например, когда пункт контракта выражен другими словами). "
            "При анализе учитывай числовые и текстовые значения, включая дубли вроде '49 (сорок пять)'. "
            "В ответе сначала приведи эталонный пункт, затем наиболее близкий пункт контракта, и подробно опиши расхождения."
        )

        for reference_text, chunks in closest_k.items():
            closest_text = "; ".join(chunks)

            user_prompt = (
                f"Эталонный пункт:\n{reference_text}\n\n"
                f"Фрагменты контракта:\n{closest_text}\n\n"
                "Сравни эти тексты. Укажи, есть ли расхождения, ошибки или несоответствия. "
                "Особое внимание обрати на даты, суммы, коды, формулировки и числа, "
                "Вначале напечатай эталонный пункт. А для соотвутвующих фрагментов с ошибкой,"
                "предварительно печатай сам фрагмент и после приводи анализ"
            )

            response = giga.chat(f"{system_prompt}\n\n{user_prompt}")
            ai_response = response.choices[0].message.content

            all_responses.append(
                f"Эталонный пункт:\n{reference_text}\n\n"
                f"Ответ модели:\n{ai_response}\n\n{'-'*20}\n"
            )
        ##
        merged_response = "\n".join(all_responses)
        return {
            'ai_response': merged_response
        }

_ai_service_instance: Optional[AIService] = None

def get_ai_service() -> AIService:
    global _ai_service_instance
    if _ai_service_instance is None:
        _ai_service_instance = AIService()
    return _ai_service_instance

