from docx import Document
import re
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from sentence_transformers import SentenceTransformer, util

SPACE_CHARS = ["\u00a0", "\u202f", "\u2009", "\u2002", "\u2003", "\u2004", "\u2005", "\u3000", "\ufeff",
                "\xa0"]
QUOTES_MAP = {
    "«": '"', "»": '"',
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "’": "'", "‘": "'",
}



# -------- ЗАЯВКА В ПЛАН ГРАФИК --------
class PlanParser:
    """
    Заявка в ПГ - чисто таблица, разбираю её на строки
    """
    def __init__(self, path: str):
        self.path = path
        self.doc = Document(path)

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Нормализуем текст: пробелы, кавычки, тире, переносы
        """
        if text is None:
            return ""
        out = text
        out = out.replace("\n", "; ")
        for sp in SPACE_CHARS:
            out = out.replace(sp, " ")
        for k, v in QUOTES_MAP.items():
            out = out.replace(k, v)
        out = out.replace("–", "-").replace("—", "-").replace("−", "-")
        out = re.sub(r"[ \t\f\v]*\n[ \t\f\v]*", "\n", out)  # переносы оставляем как \n
        out = re.sub(r"[ \t]{2,}", " ", out)
        return out.strip()

    def extract_table_kv_from_docx(self) -> List[str]:
        """
        Извлекаем таблицу ключ-значение как список строк "ключ: значение"
        """
        kv = defaultdict(list)
        if not self.doc.tables:
            return []

        table = self.doc.tables[0]

        for row in table.rows:
            cells = [self.normalize_text(c.text) for c in row.cells]
            cells = cells[1:]  # пропускаем первый столбец (если нужно)
            if len(cells) < 2:
                continue
            key = self.normalize_text(cells[0])
            val = ", ".join(dict.fromkeys(cells[1:]))
            if key:
                kv[key].append(val)

        plain_text_lines = [f"{k}: {', '.join(vals)}" for k, vals in kv.items()]
        return plain_text_lines

    def extract_clean_text(self, chunk_size: int = 50) -> List[str]:
        """
        Извлекаем весь текст документа, делим на куски по chunk_size слов
        """
        full_text = []
        for para in self.doc.paragraphs:
            text = self.normalize_text(para.text)
            if text:
                full_text.append(text)

        # Разбиваем на куски по chunk_size слов
        chunks = []
        current_chunk = []
        for line in full_text:
            words = line.split()
            for w in words:
                current_chunk.append(w)
                if len(current_chunk) >= chunk_size:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        return chunks
    

# -------- ПРОЕКТ КОНТРАКТА --------
class ContractParser:
    """ 
    Класс для извлечения и нормализации текста и таблиц из Word-документов.
    Тексть делю на чанки. Таблицу представляю в виде строк
    """

    def __init__(self, path: str):
        self.path = path
        self.doc = Document(path)

    @staticmethod
    def table_has_header(table) -> bool:
        """
        Проверка наличия заголовка у таблицы. Если есть, соединяю название колонки со значением в plain тексте
        """
        texts: List[str] = [c.text.strip() for c in table.rows[0].cells]
        had_full_digit_col: bool = any(all(ch.isdigit() for ch in t.replace('.', '')) for t in texts)
        #has_digits = any(any(ch.isdigit() for ch in t) for t in texts)
        return not had_full_digit_col and len(table.rows) > 1

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Вспомогательная функция нормализации текста
        """
        if text is None:
            return ""
        out = text
        for sp in SPACE_CHARS:
            out = out.replace(sp, " ")
        for k, v in QUOTES_MAP.items():
            out = out.replace(k, v)
        out = out.replace("–", "-").replace("—", "-").replace("−", "-")
        out = re.sub(r"[ \t\f\v]*\n[ \t\f\v]*", "\n", out)  # переносы оставляем как \n
        out = re.sub(r"[ \t]{2,}", " ", out)
        return out.strip()
    
    @staticmethod
    def chunk_text_words(text: str, chunk_size: int = 30, overlap: int = 10) -> List[str]:
        """
        Разбивает текст на куски по словам с пересечением
        Добавил, тк поиск ближайших векторов плохо работает с большими абзацами
        """
        words = text.split()
        if len(words) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(words):
            end = start + chunk_size
            chunk = " ".join(words[start:end])
            chunks.append(chunk)
            start += chunk_size - overlap
        return chunks
    
    def extract_clean_text(self, chunk_size: int = 30, overlap: int = 10) -> List[str]:
        """
        Извлчение всех абзацев
        """
        paragraphs: List[str] = []
        for p in self.doc.paragraphs:
            text: str = self.normalize_text(p.text)
            if not text:
                continue
            # разбиваем слишком длинные абзацы на чанки
            # Ну просто поиск по схожести плохо работает на больших
            chunks = self.chunk_text_words(text, chunk_size=chunk_size, overlap=overlap)
            paragraphs.extend(chunks)
        return paragraphs

    def extract_table_kv_from_docx(self) -> Dict[str, List[str]]:
        """
        Превращаю таблицы в plain-текст
        """
        doc = self.doc
        tables_kv: Dict[str, List[str]] = defaultdict(list)

        for i, table in enumerate(doc.tables):
            has_header: bool = self.table_has_header(table)
            if has_header:
                table_header: List[str] = [self.normalize_text(c.text) for c in table.rows[0].cells]

            for j, row in enumerate(table.rows):
                cells: List[str] = [self.normalize_text(c.text) for c in row.cells]
                if len(cells) < 2:
                    continue
                row_as_str: List[str] = []
                # Случай с хедером. Для удобсва добавляю колонку хедера к значению через ':' (Значение характеристики: Full HD)
                if has_header:
                    if j == 0:
                        continue
                    for head, val in zip(table_header, cells):
                        row_as_str.append("".join([head, ": ", val]))
                # Случай без хедера. Полагаю, первая колонка - ключ
                else:
                    key: str = cells[0]
                    val: str = " ".join(cells[1:])
                    row_as_str.append(f"{key}: {val}")

                row_as_str_joined: str = "; ".join(row_as_str)
                tables_kv[f"table_{i}"].append(row_as_str_joined)
        tables_lines = [val for key, val in tables_kv.items()]
        
        return np.concatenate(tables_lines)
    

def find_similar_k(plan_points: List[str], contract_chunks: List[str], use_vectorization: bool) -> Dict[str, List[str]]:
    if  use_vectorization:
            model = SentenceTransformer("sberbank-ai/sbert_large_nlu_ru")

            reference_embeddings = model.encode(plan_points, convert_to_tensor=True)
            document_embeddings = model.encode(contract_chunks, convert_to_tensor=True)

            top_k = 15
            closest_k = defaultdict(list) # {Пункт плана: k ближайших чанков из контракта}
            # Поиск ближайших по смыслу чанков 
            for i, ref_emb in enumerate(reference_embeddings):
                cos_scores = util.cos_sim(ref_emb, document_embeddings)[0]
                top_results = cos_scores.topk(k=top_k)

                for idx in top_results.indices:
                    closest_k[plan_points[i]].append(contract_chunks[idx])
    else:
        pass
    return closest_k