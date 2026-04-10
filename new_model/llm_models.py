from gigachat import GigaChat
from openai import OpenAI
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

AUTH_KEY = "MDE5YTYzYWMtOTI1OS03MjgzLTgxODctNzhlYjIzMGI4MGIzOmYxNTNkNGVlLTNjOWEtNGQ3ZS1hMGNhLWE0NDJhYTZhMDJjNw=="

def get_gigachat_client() -> GigaChat:
    return GigaChat(verify_ssl_certs=False, credentials=AUTH_KEY, model="GigaChat-2-Max")



OPENAI_API_KEY="sk-uNPNElzXmM4gtuLf1Gjst1MPNxPqoPke"
OPENAI_BASE_URL="https://api.proxyapi.ru/openai/v1"
OPENAI_MODEL="gpt-5.3-chat-latest"

def get_chatGPT_client() -> OpenAI:
    client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
        )
    return client


def get_langchain_chat_model() -> ChatOpenAI:
    return ChatOpenAI(
        api_key=SecretStr(OPENAI_API_KEY),
        base_url=OPENAI_BASE_URL,
        model=OPENAI_MODEL,
    )
