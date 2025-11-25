from typing import Optional, List, Dict, Any

#rm
from time import sleep
##your imports
import requests
from gigachat import GigaChat
from parser_functions import *
from sentence_transformers import SentenceTransformer, util
from prompts import *


from typing import List, Dict, Any
import nltk
from nltk.tokenize import word_tokenize
from nltk.translate.bleu_score import SmoothingFunction, corpus_bleu
from sklearn.metrics import f1_score, precision_score, recall_score
from openai import OpenAI
from mistralai import Mistral

# Один раз в инициализации проекта (НЕ в каждой функции!)



##imports end

def calculate_global_metrics(
    references: List[str],
    predictions: List[str],
) -> Dict[str, float]:

    from nltk.tokenize import word_tokenize
    from nltk.translate.bleu_score import SmoothingFunction, corpus_bleu
    from sklearn.metrics import f1_score, precision_score, recall_score

    # токенизация
    refs_tok = [word_tokenize(r.lower()) for r in references]
    preds_tok = [word_tokenize(p.lower()) for p in predictions]

    # ---------- BLEU (корпусный — глобальный) ----------
    smoothing = SmoothingFunction().method4
    bleu = corpus_bleu(
        [[ref] for ref in refs_tok],
        preds_tok,
        smoothing_function=smoothing,
    )

    # ---------- Глобальные F1 / precision / recall ----------
    # объединяем всё в один большой массив
    refs_flat = [t for seq in refs_tok for t in seq]
    preds_flat = [t for seq in preds_tok for t in seq]

    # длины должны совпадать
    min_len = min(len(refs_flat), len(preds_flat))
    refs_flat = refs_flat[:min_len]
    preds_flat = preds_flat[:min_len]

    if min_len == 0:
        return {
            "bleu": 0.0,
            "f1": 0.0,
            "precision": 0.0,
            "recall": 0.0,
        }

    f1 = f1_score(refs_flat, preds_flat, average='weighted', zero_division=0)
    precision = precision_score(refs_flat, preds_flat, average='micro', zero_division=0)
    recall = recall_score(refs_flat, preds_flat, average='micro', zero_division=0)

    return {
        "bleu": float(bleu),
        "f1": float(f1),
        "precision": float(precision),
        "recall": float(recall),
    }



def calculate_pairwise_metrics(
    references: List[str],
    predictions: List[str]
) -> List[Dict[str, Any]]:
    """
    Метрики отдельно по каждой паре (для отладки/анализа).
    """
    assert len(references) == len(predictions)

    results = []
    smoothing = SmoothingFunction().method4

    for ref, pred in zip(references, predictions):
        ref_tok = word_tokenize(ref.lower())
        pred_tok = word_tokenize(pred.lower())

        # BLEU для одной пары
        if len(ref_tok) == 0 or len(pred_tok) == 0:
            bleu = 0.0
        else:
            bleu = corpus_bleu(
                [[ref_tok]],
                [pred_tok],
                smoothing_function=smoothing
            )

        refs_flat = ref_tok
        preds_flat = pred_tok

        min_len = min(len(refs_flat), len(preds_flat))
        refs_flat = refs_flat[:min_len]
        preds_flat = preds_flat[:min_len]

        if min_len == 0:
            f1 = precision = recall = 0.0
        else:
            f1 = f1_score(refs_flat, preds_flat, average='weighted', zero_division=0)
            precision = precision_score(refs_flat, preds_flat, average='micro', zero_division=0)
            recall = recall_score(refs_flat, preds_flat, average='micro', zero_division=0)

        results.append({
            "reference": ref,
            "prediction": pred,
            "bleu": bleu,
            "f1": f1,
            "precision": precision,
            "recall": recall,
        })

    return results





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
        nltk.download("punkt")
        nltk.download("punkt_tab")


        parser_contract = ContractParser(doc2_path)
        paragraphs_contract = parser_contract.extract_clean_text(chunk_size = 40)
        tables_contract = parser_contract.extract_table_kv_from_docx()
        contract_chunks = paragraphs_contract + tables_contract
        if not contract_chunks:
            raise ValueError("Не удалось извлечь данные из контракта: contract_chunks пуст")

        parser_plan = PlanParser(doc1_path)
        plan_points = parser_plan.extract_table_kv_from_docx()
        if not plan_points:
            raise ValueError("Не удалось извлечь данные из плана-графика: plan_points пуст")
        
        # КОРОЧЕ ВЫКИДЫВАЕМ ВСЁ ЧЕГО В КОНТРАКТЕ НЕТ РУКАМИ
        key_words = [
            "Наименование объекта закупки",
            "Код позиции КТРУ",
            "Количество",
            "Сроки поставки товара",
            "Место поставки товара"
            ]
        plan_points_use = [
            plan_point
            for plan_point in plan_points
            if any(kw.lower() in plan_point.lower() for kw in key_words)
        ]
        if not plan_points_use:
            raise ValueError(f"Не найдено пунктов в план-графике, соответствующих ключевым словам, \n plan_points:\n{plan_points}")


        print("Plan at:", doc1_path)
        print("Contract at:", doc2_path)

        closest_k = find_similar_k(plan_points_use, contract_chunks, k=6, use_vectorization=False)
        if not closest_k:
            return {'ai_response': "Не удалось найти соответствия между пунктами. closest_k пуст!"}
        
        AUTH_KEY  = "MDE5YTg4NmItNzkyZS03MjQzLTgxMTAtYTdmOGQ2ZDRhYjdiOmM4ZDQ2YTBkLWZhMjEtNDdkYi04Y2M5LThkNTcyYmY0NWJjOQ=="
        print("Generating answer...")
        giga = GigaChat(verify_ssl_certs=False, credentials=AUTH_KEY, model="GigaChat-2")   
        all_responses = []    

        # ДЛЯ МЕТРИК
        references_for_metrics: List[str] = []   # эталонные пункты (план)
        model_outputs_for_metrics: List[str] = []  # ответы модели
        best_chunks_for_metrics: List[str] = []  # top-1 фрагмент контракта как baseline


        # Параметры OpenAI
        # OPENAI_API_KEY="sk-uNPNElzXmM4gtuLf1Gjst1MPNxPqoPke"
        # OPENAI_BASE_URL="https://api.proxyapi.ru/openai/v1"
        # OPENAI_MODEL="gpt-4o-mini"

        # client = OpenAI(
        #     api_key=OPENAI_API_KEY,
        #     base_url=OPENAI_BASE_URL,
        # )


        # Параметры Mistral
        OPENAI_BASE_URL = "https://api.mistral.ai/v1"
        MISTRAL_MODEL = "mistral-small-2503"   # или mistral-medium-latest / mistral-small-latest и т.п.
        OPENAI_API_KEY = "ftp39yrYmtWCvksEKjLU0iVVvrkFGSqp"

        mistral_client = Mistral(api_key=OPENAI_API_KEY)




        system_prompt = SYSTEM_PROMPT

        for reference_text, chunks in closest_k.items():
            closest_text = "<" + ">; <".join(chunks)

            user_prompt = f"""
            Эталонный пункт:
            {reference_text}

            Фрагменты проекта (несколько вариантов, могут содержать как корректные, так и ошибочные формулировки):
            {closest_text}

            Задача:

            1) Проанализируй все предложенные фрагменты проекта и определи, какие из них относятся к тому же смысловому полю, что и эталонный пункт
            (например: предмет закупки, количество, сроки, место поставки, НДС, характеристики, цена, КТРУ и т.п.).
            Релевантными могут быть даже те фрагменты, которые содержат ошибки или отличаются от эталона по числам, срокам, единицам измерения и т.п.

            2) ВСЕ релевантные фрагменты ОБЯЗАТЕЛЬНО должны оказаться в итоговом списке под заголовком:
            «Соответствующие фрагменты текста проекта:»
            Формат списка — один на весь ответ:
            нумерация «1) …».

            3) В список нужно включить КАЖДЫЙ отдельный фрагмент:
            - цитировать точно, без сокращений и изменений,
            - не объединять несколько фрагментов в один,
            - не пропускать ни один релевантный фрагмент.

            4) Проведи сравнение эталона со всеми релевантными фрагментами ТОЛЬКО по следующим параметрам:
            - числа, суммы, ставки НДС,
            - даты и сроки,
            - виды дней (рабочие / календарные),
            - единицы измерения,
            - количество,
            - место оказания услуг,
            - периоды и объёмы.

            ОТДЕЛЬНОЕ ПРАВИЛО ДЛЯ НАИМЕНОВАНИЯ ОБЪЕКТА ЗАКУПКИ:

            4.1. Если эталонный пункт содержит «Наименование объекта закупки: Поставка носков»,
            а во фрагменте встречается любое из слов:
            «носок», «носки», «носков» (в любых сочетаниях: «Наименование товара: Носок», «Поставка носков» и т.п.),
            ТО:
            - это ВСЕГДА считается ПОЛНЫМ СОВПАДЕНИЕМ по наименованию объекта закупки,
            - ЭТО НЕ ОШИБКА,
            - НЕЛЬЗЯ выводить ошибку, связанную с использованием слова «носок/носки/носков».

            4.2. Считай ошибкой наименование объекта закупки ТОЛЬКО если меняется сам товар по смыслу.
            Примеры ошибок:
            «Поставка носков» → «поставка текстильной продукции»
            «Поставка носков» → «поставка автомобильных шин»
            «Носок» → «перчатки» и т.п.

            4.3. Даже если тебе кажется, что форма слова «носок/носки/носков» выбрана неудачно или звучит плохо,
            ВСЁ РАВНО НЕЛЬЗЯ считать это ошибкой и НЕЛЬЗЯ выводить ошибку, связанную с этим отличием.

            5) Проверь на наличие внутренних противоречий между фрагментами:
            Если один фрагмент совпадает с эталоном по важному параметру,
            а другой указывает иное значение по тому же параметру,
            это является ошибкой несогласованности, которую необходимо вывести как отдельную ошибку.

            6) Определи степень соответствия:
            - «полное совпадение» — если все важные параметры совпадают и между фрагментами нет противоречий;
            - «частичное совпадение» — если есть ошибки или противоречия;
            - «не соответствует» — если релевантных фрагментов нет или расхождения критичны.

            7) Если есть ошибки — перечисли их строго в формате:
            Поле: <название поля>
            Ошибка: <краткое описание>

            8) Строго соблюдай структуру ответа и допустимые начала строк, заданные в system_prompt.
            Формат ответа должен включать:
            - один заголовок «Соответствующие фрагменты текста проекта:»
            - список всех релевантных фрагментов
            - строку «Степень соответствия: …»
            - (при наличии ошибок) строки «Поле: …» и «Ошибка: …»
            - строку «Заключение: Количество ошибок: <число>»

            9) Никаких дополнительных пояснений, рассуждений или текста вне формата system_prompt не допускается.
            """.strip()



            # Mistral API call
            chat_completion = mistral_client.chat.complete(
                model=MISTRAL_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                # по желанию:
                # temperature=0.2,
                # max_tokens=...
            )

            # извлекаем текст ответа
            msg = chat_completion.choices[0].message
            content = msg.content

            if isinstance(content, str):
                ai_response = content
            else:
                # на будущее: если Mistral вернёт список чанков (text, citations и т.п.)
                ai_response = "".join(
                    part.text for part in content
                    if getattr(part, "type", None) == "text"
                )

            all_responses.append(
                f"Эталонный пункт:\n{reference_text}\n\n"
                f"Ответ модели:\n{ai_response}\n\n{'-'*20}\n"
            )


            # OpenAI API call
            # chat_completion = client.chat.completions.create(
            #     model=OPENAI_MODEL,
            #     messages=[
            #         {"role": "system", "content": system_prompt},
            #         {"role": "user", "content": user_prompt},
            #     ]
            # )

            # ai_response = chat_completion.choices[0].message.content

            # all_responses.append(
            #     f"Эталонный пункт:\n{reference_text}\n\n"
            #     f"Ответ модели:\n{ai_response}\n\n{'-'*20}\n"
            # )


            # GigaChat API call
            # response = giga.chat(f"{system_prompt}\n\n{user_prompt}")
            # ai_response = response.choices[0].message.content

            # all_responses.append(
            #     f"Эталонный пункт:\n{reference_text}\n\n"
            #     f"Ответ модели:\n{ai_response}\n\n{'-'*20}\n"
            # )

            # ---------- СБОР ДАННЫХ ДЛЯ МЕТРИК ----------
            references_for_metrics.append(str(reference_text))
            model_outputs_for_metrics.append(str(ai_response))

            # Берём top-1 фрагмент контракта как "модель без LLM" (baseline)
            if chunks:
                best_chunks_for_metrics.append(str(chunks[0]))
            else:
                best_chunks_for_metrics.append("")

        merged_response = "\n".join(all_responses)

        # ---------- СЧИТАЕМ МЕТРИКИ ДЛЯ LLM ----------
        llm_overall_metrics = calculate_global_metrics(
            references_for_metrics,
            model_outputs_for_metrics
        )


        # ---------- СЧИТАЕМ МЕТРИКИ ДЛЯ СЫРОГО КОНТРАКТА (baseline) ----------
        contract_overall_metrics = calculate_global_metrics(
            references_for_metrics,
            best_chunks_for_metrics
        )


        print("\n==================== ГЛОБАЛЬНЫЕ МЕТРИКИ LLM ====================\n")

        print("Сравнение:")
        print("  - references: все эталонные пункты подряд")
        print("  - predictions: все ответы модели подряд\n")

        print(f"BLEU:      {llm_overall_metrics['bleu']:.4f}")
        print(f"F1:        {llm_overall_metrics['f1']:.4f}")
        print(f"Precision: {llm_overall_metrics['precision']:.4f}")
        print(f"Recall:    {llm_overall_metrics['recall']:.4f}")

        print("\n===============================================================\n")


        print("\n============== ГЛОБАЛЬНЫЕ МЕТРИКИ BASELINE (контракт) ==============\n")

        print("Сравнение:")
        print("  - references: все эталонные пункты подряд")
        print("  - predictions: все top-1 фрагменты контракта подряд\n")

        print(f"BLEU:      {contract_overall_metrics['bleu']:.4f}")
        print(f"F1:        {contract_overall_metrics['f1']:.4f}")
        print(f"Precision: {contract_overall_metrics['precision']:.4f}")
        print(f"Recall:    {contract_overall_metrics['recall']:.4f}")

        print("\n===================================================================\n")



        return {
            'ai_response': merged_response,
            'metrics': {
                'llm': {
                    'overall': llm_overall_metrics,
                },
                'contract_baseline': {
                    'overall': contract_overall_metrics,
                },
            },
        }


_ai_service_instance: Optional[AIService] = None

def get_ai_service() -> AIService:
    global _ai_service_instance
    if _ai_service_instance is None:
        _ai_service_instance = AIService()
    return _ai_service_instance