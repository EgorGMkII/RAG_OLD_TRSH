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
    def process_query(self, doc1_path: str, doc2_path: str, use_vectorization=True) -> Dict[str, Any]:
        ##processing
        parser_contract = ContractParser(doc2_path)
        paragraphs_contract = parser_contract.extract_clean_text(chunk_size = 40)
        tables_contract = parser_contract.extract_table_kv_from_docx()
        contract_chunks = paragraphs_contract + tables_contract

        parser_plan = PlanParser(doc1_path)
        plan_points = parser_plan.extract_table_kv_from_docx()
        # КОРОЧЕ НАХЕР ВЫКИДЫВАЕМ ВСЁ ЧЕГО В КОНТРАКТЕ НЕТ РУКАМИ
        plan_points_use = [plan_points[0], plan_points[1], plan_points[2], plan_points[3], plan_points[11], plan_points[12]]
        print("Plan at:", doc1_path)
        print("Contract at:", doc2_path)

        closest_k = find_similar_k(plan_points_use, contract_chunks, k=3, use_vectorization=True)
        if not closest_k:
            return {'ai_response': "Не удалось найти соответствия между пунктами."}
        
        AUTH_KEY  = "MDE5YTYzYWMtOTI1OS03MjgzLTgxODctNzhlYjIzMGI4MGIzOmVlOTY5ZGM4LWY1ODUtNGNjNC1hODA3LWNjMGU4N2U1ZmMyZA=="
        print("Generating answer...")
        giga = GigaChat(verify_ssl_certs=False,credentials=AUTH_KEY, model=None)   
        all_responses = []    

        system_prompt = """
        Ты — юридический помощник, специализирующийся на анализе договоров. 
        Твоя цель — проверять соответствие между эталонными пунктами плана-графика и фрагментами контракта. 
        Обрабатывай каждый эталонный пункт независимо. Не связывай его с другими пунктами или фрагментами.

        Фрагменты контракта подаются отдельно, через ';': <фрагмент1>; <фрагмент2>; <фрагмент3>; ...

        Обрабатывай каждый фрагмент отдельно. Отвечай максимально кратко и строго по формату.

        Правила обработки:
        - Если фрагмент полностью совпадает с эталоном, пиши "полное совпадение".
        - Если фрагмент НЕ имеет релевантных ключевых слов эталона, НЕ ВЫВОДИ НИЧЕГО. Ни одно слово. Ни "нерелевантен", ни пустая строка, ни символы. Полностью игнорируй этот фрагмент.
        - Особое внимание уделяй числам, их словесным представлениям, единицам измерения (рабочие/календарные дни, штуки, суммы, даты).
        - Выводи только фрагменты с расхождениями, строго в формате:
            Фрагмент: <текст фрагмента контракта>
            Степень соответствия: частичное совпадение
            Комментарий: <короткий анализ расхождений, максимум 40 слов, только по сути расхождений>

        Не добавляй заголовков, списков, Markdown, пустых строк, разделителей, заключений или пояснений формата.

        Типичные ошибки, встречающиеся в тексте:
        1. Срок поставки: 88 (восемьдесять восемь) календарных дней. [Эталон]  
        Поставка товара в срок 79 (восемьдесять восемь) рабочих дней. [Контракт]  
        Ошибка: несоответствие сроков (79 вместо 88), рабочих дней вместо календарных дней, число 79 не соответствует словам восемьдесять восемь.
        2. Наименование объекта закупки: Поставка носков. [Эталон]  
        Контракт № на поставку текстильной продукции. [Контракт]  
        Ошибка: несоответствие наименования объекта закупки (текстильной продукции вместо носков).

        Все пункты типа цены, наименования товаров и услуг, даты и сроки поставки, количество единиц должны полностью соответствовать эталону.
        """

        for reference_text, chunks in closest_k.items():
            closest_text = "<" + ">; <".join(chunks)
            user_prompt = f"""
                Эталонный пункт (из плана-графика):
                {reference_text}

                Фрагменты контракта (каждый отдельно, через ';'):
                {closest_text}

                Задача:
                1) Среди этих фрагментов для каждого проанализируй релевантность эталону. Выбери только те, которые имеют смысловую релевантность к эталонному пункту.
                (Фрагмент нерелевантен, если фрагмент не содержит ключевых слов эталона или явно с ним не связан).
                2) Для релевантных фрагментов сравни их с эталоном и оцени наличие расхождений. Если НЕРЕЛЕВАНТЕН пиши нерелевантен.
                3) Если фрагмент полностью совпадает, ВЫВЕДИ "полное совпадение".
                4) Выводи фрагменты с расхождениями строго в формате system_prompt:
                """
            response = giga.chat(f"{system_prompt}\n\n{user_prompt}")
            ai_response = response.choices[0].message.content

            all_responses.append(
                f"Эталонный пункт:\n{reference_text}\n\n"
                f"Ответ модели:\n{ai_response}\n\n{'-'*20}\n"
            )

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

