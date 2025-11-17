from typing import Optional, List, Dict, Any

#rm
from time import sleep
##your imports
import requests
import openai
from gigachat import GigaChat
from parser_functions import *
from prompts import *
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
    def process_query(self, doc1_path: str, doc2_path: str, use_vectorization=True) -> Dict[str, Any]:
        ##processing
        parser_contract = ContractParser(doc2_path)
        paragraphs_contract = parser_contract.extract_clean_text(chunk_size = 40)
        tables_contract = parser_contract.extract_table_kv_from_docx()
        contract_chunks = paragraphs_contract + tables_contract

        parser_plan = PlanParser(doc1_path)
        plan_points = parser_plan.extract_table_kv_from_docx()

        plan_points_use = [plan_points[0], plan_points[2], plan_points[3], plan_points[11], plan_points[12]]
        print("Plan at:", doc1_path)
        print("Contract at:", doc2_path)

        closest_k = find_similar_k(plan_points_use, contract_chunks, k=4, use_vectorization=True)
        if not closest_k:
            return {'ai_response': "Не удалось найти соответствия между пунктами."}
        
        AUTH_KEY  = "MDE5YTYzYWMtOTI1OS03MjgzLTgxODctNzhlYjIzMGI4MGIzOmVlOTY5ZGM4LWY1ODUtNGNjNC1hODA3LWNjMGU4N2U1ZmMyZA=="
        print("Generating answer...")
        giga = GigaChat(verify_ssl_certs=False,credentials=AUTH_KEY, model=None)   
        all_responses = []    

        system_prompt = SYSTEM_PROMPT
        all_responses = []

        for reference_text, chunks in closest_k.items():
            closest_text = "<" + ">; <".join(chunks)
            user_prompt = f"""
            Эталонный пункт (из плана-графика):
            {reference_text}

            Список фрагментов контракта (каждый отдельно выделен в <...>). КАЖДЫЙ ИЗ ФРАГМЕНТОВ НА 100% РЕЛЕВАНТЕН И ПОДЛЕЖИТ АНАЛИЗУ!:
            {closest_text}

            Задача:
            1. Анализируй каждый фрагмент отдельно, не связывая его с другими.
            2. Фрагмент сравни с эталоном и ищи отличия:
            - различия в числах и их словесных формах,
            - различия в датах и периодах,
            - различия в сроках,
            - различия в единицах измерения,
            - различия в формулировках предмета закупки.
            НЕ считай ошибкой:
            - перестановку слов,
            - стандартные сокращения (шт./штук, руб./рублей, г./год и т.п.).
            - различные падежи (срока/срок, штуки/штук и т.п.)
            3. Если есть отличие — выведи строго в формате:
            Фрагмент: <точный текст фрагмента>
            Степень соответствия: частичное совпадение
            Комментарий: <краткий анализ расхождений, максимум 40 слов>
            4. Если фрагмент полностью совпадает с эталоном — выведи:
            Фрагмент: <точный текст фрагмента>
            Степень соответствия: полное совпадение
            5. Строго соблюдай порядок и формат:
            - Не добавляй списков, заголовков, пустых строк, Markdown или дополнительных слов.
            - Никаких комментариев вне указанного формата.

            Также:
            {POINT_SPECIFIC_PROMPTS(reference_text)}
            """.strip()

            response = giga.chat(f"{system_prompt}\n\n{user_prompt}")
            ai_response = response.choices[0].message.content

            all_responses.append(
                f"Эталонный пункт:\n{reference_text}\n\n"
                f"Ответ модели:\n{ai_response}\n\n{'-'*20}\n"
            )

        merged_response = "\n".join(all_responses)

        # for reference_text, chunks in closest_k.items():
        #     closest_text = "<" + ">; <".join(chunks)
        #     user_prompt = f"""
        #     Эталонный пункт (из плана-графика):
        #     {reference_text}

        #     Список фрагментов контракта (каждый отдельно выделен в <...>), подобран по семантической близости, но может содержать ошибки:
        #     {closest_text}

        #     Задача:
        #     1. Анализируй каждый фрагмент отдельно, не связывая его с другими.
        #     2. Определи, относится ли фрагмент к тому же вопросу, что и эталонный пункт 
        #     (предмет закупки, количество, единицы измерения, сроки, место, цена, НДС и т.п.).
        #     3. Если фрагмент НЕ относится к эталону — НИЧЕГО НЕ ВЫВОДИ (ни строк, ни комментариев).
        #     4. Если фрагмент относится — сравни с эталоном и ищи отличия:
        #     - различия в числах и их словесных формах,
        #     - различия в датах и периодах,
        #     - различия в сроках,
        #     - различия в единицах измерения,
        #     - различия в формулировках предмета закупки.
        #     НЕ считай ошибкой:
        #     - перестановку слов,
        #     - стандартные сокращения (шт./штук, руб./рублей, г./год и т.п.).
        #     5. Если есть отличие — выведи строго в формате:
        #     Фрагмент: <точный текст фрагмента>
        #     Степень соответствия: частичное совпадение
        #     Комментарий: <краткий анализ расхождений, максимум 40 слов>
        #     6. Если фрагмент полностью совпадает с эталоном — выведи:
        #     Фрагмент: <точный текст фрагмента>
        #     Степень соответствия: полное совпадение
        #     7. Строго соблюдай порядок и формат:
        #     - Не добавляй списков, заголовков, пустых строк, Markdown или дополнительных слов.
        #     - Никаких комментариев вне указанного формата.
        #     """.strip()
        #     from openai import OpenAI
        #     client = OpenAI(api_key="sk-uNPNElzXmM4gtuLf1Gjst1MPNxPqoPke")

        #     response = client.chat.completions.create(
        #         model="gpt-4o-mini",
        #         messages=[
        #             {"role": "system", "content": SYSTEM_PROMPT},
        #             {"role": "user", "content": user_prompt}
        #         ],
        #         temperature=0,
        #         max_tokens=4000
        #     )

        #     ai_response = response.choices[0].message.content
        #     all_responses.append(
        #         f"Эталонный пункт:\n{reference_text}\n\nОтвет модели:\n{ai_response}\n\n{'-'*20}\n"
        #     )

        # merged_response = "\n".join(all_responses)


        return {
            'ai_response': merged_response
        }

_ai_service_instance: Optional[AIService] = None

def get_ai_service() -> AIService:
    global _ai_service_instance
    if _ai_service_instance is None:
        _ai_service_instance = AIService()
    return _ai_service_instance

