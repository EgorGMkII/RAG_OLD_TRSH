from docx import Document
import re
from typing import List, Dict
from collections import defaultdict

SPACE_CHARS = ["\u00a0", "\u202f", "\u2009", "\u2002", "\u2003", "\u2004", "\u2005", "\u3000", "\ufeff",
                "\xa0"]
QUOTES_MAP = {
    "«": '"', "»": '"',
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "’": "'", "‘": "'",
}

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
    out = re.sub(r"\s*,\s*(?:,\s*)+", ", ", out)
    return out.strip()

# дедуп для строк, образованных объединёнными ячейками в таблице 
# (когда текст повторяется в нескольких ячейках подряд)
def dedupe_merged_cells(row):
    cleaned = []
    prev_text = None
    for cell in row.cells:
        text = cell.text.strip()
        if text != prev_text:
            cleaned.append(text)
        prev_text = text
    return cleaned

# -------- ЗАЯВКА В ПЛАН ГРАФИК --------
class PlanParser:
    """
    Заявка в ПГ - чисто таблица, разбираю её на строки
    """
    def __init__(self, path: str):
        self.path = path
        self.doc = Document(path)

    def extract_table_kv_from_docx(self) -> List[str]:
        """
        Извлекаем таблицу ключ-значение как список строк "ключ: значение"
        """
        kv = defaultdict(list)
        if not self.doc.tables:
            return []

        table = self.doc.tables[0]

        for row in table.rows:
            cells = []
            for c in row.cells:
                txt = normalize_text(c.text)
                if txt == "-": txt = "отсутствует"
                cells.append(txt)

            if not cells[0]:
                cells = cells[1:]  # пропускаем первый столбец (если нужно)
                
            if len(cells) < 2:
                continue
            key = normalize_text(cells[0])
            val = ", ".join(dict.fromkeys(cells[1:]))
            if key:
                kv[key].append(val)

        plain_text_lines = [f"{k}: {', '.join(vals)}" for k, vals in kv.items()]
        return plain_text_lines

    def extract_clean_text(self, chunk_size: int = 50) -> str:
        """
        Извлекаем весь текст документа
        """
        full_text = []
        for para in self.doc.paragraphs:
            text = normalize_text(para.text)
            if text:
                full_text.append(text)
        full_text = "\n\n".join(full_text)

        return full_text

class DocumentParser:
    """
    Класс для извлечения и нормализации текста и таблиц из Word-документов.
    
    """

    def __init__(self, path: str):
        self.path = path
        self.doc = Document(path)

    def extract_clean_text(self) -> str:
        """
        Извлекаем весь текст документа
        """
        full_text = []
        for para in self.doc.paragraphs:
            text = normalize_text(para.text)
            if text:
                full_text.append(text)
        return "\n\n".join(full_text)
    
    def extract_table_data(self) -> str:
        """
        Извлекаем все таблицы документа в виде строк "ключ: значение"
        """
        tables_kv = []
        for table in self.doc.tables:
            for row in table.rows:
                cells = [normalize_text(c.text) for c in row.cells]
                if len(cells) >= 2:
                    key = cells[0]
                    val = ", ".join(cells[1:])
                    tables_kv.append(normalize_text(f"{key}: {val}"))
        return "\n".join(tables_kv)

    def table_to_markdown(self):
        md_tables = []
        for table in self.doc.tables:
            rows = []
            for row in table.rows:
                rows.append(dedupe_merged_cells(row))

            md = ""
            for i, row in enumerate(rows):
                md += "| " + " | ".join(row) + " |\n"
                if i == 0:
                    md += "| " + " | ".join(["---"] * len(row)) + " |\n"
            md_tables.append(md)

        return "\n\n".join(md_tables)


    def extract_rows_region(self, keyword: str, left_range: int = 1, right_range:int = 1) -> str:
        extracted_rows = []
        keyword_lower = keyword.lower()

        for table in self.doc.tables:
            for row in table.rows:
                cells = [normalize_text(cell) for cell in dedupe_merged_cells(row)]
                if not cells:
                    continue

                matching_indexes = [
                    idx for idx, cell in enumerate(cells)
                    if keyword_lower in cell.lower()
                ]
                if not matching_indexes:
                    continue

                used_indexes = set()
                selected_cells = []

                for idx in matching_indexes:
                    start = max(0, idx - left_range)
                    end = min(len(cells), idx + right_range + 1)

                    for cell_idx in range(start, end):
                        if cell_idx not in used_indexes:
                            selected_cells.append(cells[cell_idx])
                            used_indexes.add(cell_idx)

                extracted_rows.append("| " + " | ".join(selected_cells) + " |")

        return "\n".join(extracted_rows)

    def extract_table_cells_by_keyword(self, keywords: List[str]) -> Dict[str, List[str]]:
        """
        Ищем в таблицах строки, содержащие ключевые слова, и извлекаем их ячейки
        """
        results = defaultdict(list)
        for table in self.doc.tables:
            for row in table.rows:
                for kw in keywords:
                    cells = [normalize_text(c.text) for c in row.cells if kw.lower() in normalize_text(c.text).lower()]
                    if cells:
                        results[kw].append(", ".join(cells))
        return dict(results)
