from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from typing import List, Optional

splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=100
)

class Retriever:
    def __init__(self, embeddings):
        self.embeddings = embeddings

    def create_retriever(self, texts: List[str], n: int = 5, sources: Optional[List[str]] = None):
        # разбиваем документы на чанки
        all_chunks = []
        all_metadatas = []
        if sources is None:
            sources = [f"source_{i}" for i in range(len(texts))]

        for text, source in zip(texts, sources):
            chunks = splitter.split_text(text)
            all_chunks.extend(chunks)
            all_metadatas.extend(
                {"source": source} for _ in chunks
            )

        # эмбеддинги для всех чанков
        embeddings = self.embeddings

        # FAISS индекс
        faiss_index = FAISS.from_texts(all_chunks, embeddings, metadatas=all_metadatas)

        return faiss_index.as_retriever(search_kwargs={"k": n})
