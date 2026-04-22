from collections import defaultdict
import re
from typing import Dict, List

from docx import Document


SPACE_CHARS = [
    "\u00a0",
    "\u202f",
    "\u2009",
    "\u2002",
    "\u2003",
    "\u2004",
    "\u2005",
    "\u3000",
    "\ufeff",
    "\xa0",
]
QUOTES_MAP = {
    "\u00ab": '"',
    "\u00bb": '"',
    "\u201c": '"',
    "\u201d": '"',
    "\u201e": '"',
    "\u201f": '"',
    "\u2033": '"',
    "\u2018": "'",
    "\u2019": "'",
    "\u201a": "'",
    "\u201b": "'",
    "\u2032": "'",
    "В«": '"',
    "В»": '"',
    "вЂњ": '"',
    "вЂќ": '"',
    "вЂћ": '"',
    "вЂџ": '"',
    "вЂ™": "'",
    "вЂ": "'",
    "Р’В«": '"',
    "Р’В»": '"',
    "РІР‚Сљ": '"',
    "РІР‚Сњ": '"',
    "РІР‚С›": '"',
    "РІР‚Сџ": '"',
    "РІР‚в„ў": "'",
    "РІР‚В": "'",
}
DASH_CHARS = [
    "\u2010",
    "\u2011",
    "\u2012",
    "\u2013",
    "\u2014",
    "\u2015",
    "\u2212",
    "\ufe58",
    "\ufe63",
    "\uff0d",
]


def normalize_text(text: str) -> str:
    """
    Нормализует текст: чистит пробелы, кавычки, тире и переносы строк.
    """
    if text is None:
        return ""
    out = text
    out = out.replace("\n", "; ")
    for sp in SPACE_CHARS:
        out = out.replace(sp, " ")
    for k, v in QUOTES_MAP.items():
        out = out.replace(k, v)
    for dash in DASH_CHARS:
        out = out.replace(dash, "-")
    out = re.sub(r"[ \t\f\v]*\n[ \t\f\v]*", "\n", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\s*,\s*(?:,\s*)+", ", ", out)
    return out.strip()


def dedupe_merged_cells(row):
    """
    Убирает соседние дубли ячеек в строке таблицы, которые появляются из-за merged cells.

    Пример:
        ["КТРУ 1", "КТРУ 1", "КТРУ 2"] -> ["КТРУ 1", "КТРУ 2"]
    """
    cleaned = []
    prev_text = None
    for cell in row.cells:
        text = cell.text.strip()
        if text != prev_text:
            cleaned.append(text)
        prev_text = text
    return cleaned


def parse_okpd_entries(text: str):
    """
    Парсит строку с ОКПД2 в список словарей `{"okpd2": ..., "name": ...}`.

    Пример:
        "ОКПД2: 31.01.12 - Стулья; 31.01.13 - Столы"
        -> [{"okpd2": "31.01.12", "name": "Стулья"}, ...]
    """
    result = []
    for item in text.split(":")[1].split(";"):
        item = item.strip()
        if not item:
            continue
        item = normalize_text(item)
        code, name = item.split(" - ", 1)
        result.append({
            "okpd2": code.strip(),
            "name": name.strip(),
        })
    return result


def parse_ktry_entries(text: str):
    """
    Парсит строку с КТРУ в список словарей `{"ktru_code": ..., "name": ...}`.

    Пример:
        "КТРУ: 31.01.12.150-00000003 - Тумба офисная"
        -> [{"ktru_code": "31.01.12.150-00000003", "name": "Тумба офисная"}]
    """
    result = []
    for item in text.split(":")[1].split(";"):
        item = item.strip()
        if not item:
            continue
        item = normalize_text(item)
        code, name = item.split(" - ", 1)
        result.append({
            "ktru_code": code.strip(),
            "name": name.strip(),
        })
    return result


def _clean_keyword_dict(items_by_key: Dict[str, list[str]]) -> str:
    """
    Склеивает словарь найденных значений в чистую строку без дублей и лишних `;`.

    Пример:
        {"ОКПД": ["ОКПД2: 31.01.12 - Стул;;", "ОКПД2: 31.01.12 - Стул"]}
        -> "ОКПД2: 31.01.12 - Стул"
    """
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
    """
    Ищет в тексте фрагменты от ключевого слова и захватывает ещё `window` символов вправо.

    Пример:
        _extract_keyword_windows("блабла... КТРУ 31.01.12.150-00000003 тумба офисная", ["КТРУ"])
        -> "КТРУ 31.01.12.150-00000003 тумба офисная"
    """

    matches: list[str] = []
    for keyword in keywords:
        pattern = re.compile(rf"({re.escape(keyword)}[\s\S]{{0,{window}}})", re.IGNORECASE)
        for match in pattern.findall(text):
            clean_match = re.sub(r"\s+", " ", match).strip(" ;,\n\t")
            if clean_match:
                matches.append(clean_match)

    return "\n".join(dict.fromkeys(matches))

def extract_ktru_block(text: str, tail_chars: int = 30, fallback_chars: int = 150) -> str:
    start_match = re.search(r"КТРУ\s*:", text, flags=re.IGNORECASE)
    if not start_match:
        return ""

    start = start_match.start()
    fragment = text[start:]

    ktru_pattern = r"\d+(?:\.\d+){3}-\d+"
    matches = list(re.finditer(ktru_pattern, fragment))

    if not matches:
        return fragment[:fallback_chars].strip()

    last_match = matches[-1]
    end = last_match.end() + tail_chars

    return fragment[:end].strip()

class PlanParser:
    """
    #### Парсер для документа "Заявка в план-график", где данные обычно лежат в таблице.
    """

    def __init__(self, path: str):
        self.path = path
        self.doc = Document(path)

    def extract_table_kv_from_docx(self) -> List[str]:
        """
        Извлекает первую таблицу документа как список строк формата `"ключ: значение"`.

        Пример:
            ["ОКПД2: 31.01.12 - Стулья", "Количество: 10"]
        """
        kv = defaultdict(list)
        if not self.doc.tables:
            return []

        table = self.doc.tables[0]

        for row in table.rows:
            cells = []
            for c in row.cells:
                txt = normalize_text(c.text)
                if txt == "-":
                    txt = "отсутствует"
                cells.append(txt)

            if not cells[0]:
                cells = cells[1:]

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
        Возвращает весь текст документа из параграфов одной строкой с разделением через пустую строку.
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
    #### Универсальный парсер Word-документов: умеет вытаскивать текст, таблицы и фрагменты по ключевым словам.
    """

    def __init__(self, path: str):
        self.path = path
        self.doc = Document(path)

    def extract_clean_text(self) -> str:
        """
        Возвращает весь текст документа из параграфов.
        """
        full_text = []
        for para in self.doc.paragraphs:
            text = normalize_text(para.text)
            if text:
                full_text.append(text)
        return "\n\n".join(full_text)

    def extract_table_data(self) -> str:
        """
        Извлекает все строки всех таблиц в виде `"первая ячейка: остальные ячейки"`.

        Пример:
            "ОКПД2: 31.01.12 - Стулья\nКоличество: 10"
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
        """
        Преобразует все таблицы документа в markdown-таблицы.

        Пример:
            "| Поле | Значение |\n| --- | --- |\n| ОКПД2 | 31.01.12 |"
        """
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

    def extract_tables_columns(self, keywords: List[str]) -> str:
        """
        Находит в таблицах колонки, чьи заголовки содержат ключевые слова, и возвращает их построчно.

        Пример:
            "| КТРУ: 31.01.12.150-00000003 | ОКПД2: 31.01.12 |"
        """
        extracted_rows = []
        keyword_lower = [kw.lower() for kw in keywords]

        for table in self.doc.tables:
            rows = [dedupe_merged_cells(row) for row in table.rows]
            if not rows:
                continue

            header = [normalize_text(cell) for cell in rows[0]]
            selected_indexes = [
                idx for idx, cell in enumerate(header)
                if any(kw in cell.lower() for kw in keyword_lower)
            ]
            if not selected_indexes:
                continue

            for row in rows:
                normalized_row = [normalize_text(cell) for cell in row]
                selected_cells = [
                    f"{header[idx]}: {normalized_row[idx]}"
                    for idx in selected_indexes
                    if idx < len(normalized_row) and normalized_row[idx]
                ]

                if any(selected_cells):
                    extracted_rows.append("| " + " | ".join(selected_cells) + " |")

        return "\n".join(dict.fromkeys(extracted_rows))

    def extract_rows_region(self, keyword: str, left_range: int = 1, right_range: int = 1) -> str:
        """
        Ищет строки таблиц с ключевым словом и возвращает найденную ячейку вместе с соседними.

        Пример:
            "| Наименование | КТРУ | 31.01.12.150-00000003 |"
        """
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
        Ищет в таблицах ячейки, содержащие ключевые слова, и группирует найденное по каждому ключу.

        Пример:     
            {"ОКПД": ["ОКПД2: 31.01.12 - Стулья"]}
        """
        results = defaultdict(list)
        for table in self.doc.tables:
            for row in table.rows:
                for kw in keywords:
                    cells = [normalize_text(c.text) for c in row.cells if kw.lower() in normalize_text(c.text).lower()]
                    if cells:
                        results[kw].append(", ".join(cells))
        return dict(results)
