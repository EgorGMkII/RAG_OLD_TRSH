from gigachat.models.chat import Chat
from gigachat.models.messages import Messages

from new_model.llm_models import get_gigachat_client
from new_model.parser_functions import DocumentParser
from new_model.prompts import SYSTEM_PROMPT


DOC2_PATH = r"C:\Users\egorg\Documents\RAG_минцифры\Правильно\Проект Контракта ЛОШ.docx"
PLAN_POINT = "Наименование объекта закупки: Поставка носков"
PLAIN_TEXT_SLICE = None


def main() -> None:
    doc_parser = DocumentParser(DOC2_PATH)
    table_data = doc_parser.table_to_markdown()
    plain_text = doc_parser.extract_clean_text()

    user_prompt = (
        f"Пункт плана:\n{PLAN_POINT}\n\n"
        f"Текст документа:\n{plain_text}\n\n"
        f"Таблицы документа:\n{table_data}\n\n"
        "Дай содержательный ответ по пункту, строго следуя правилам и формату из системного сообщения."
    )

    payload = Chat(
        messages=[
            Messages(role="system", content=SYSTEM_PROMPT),
            Messages(role="user", content=user_prompt),
        ]
    )

    client = get_gigachat_client()
    response = client.chat(payload)

    print("=== RESPONSE ===")
    print(response.choices[0].message.content)
    print()
    print("=== TOKEN USAGE ===")
    print(f"prompt_tokens: {response.usage.prompt_tokens}")
    print(f"completion_tokens: {response.usage.completion_tokens}")
    print(f"total_tokens: {response.usage.total_tokens}")
    print(f"precached_prompt_tokens: {response.usage.precached_prompt_tokens}")


if __name__ == "__main__":
    main()
