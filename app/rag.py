import sys

import pysqlite3

sys.modules["sqlite3"] = pysqlite3

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from app.config import RAG_K_FRAGMENTS, VECTOR_STORE_PATH

_embeddings = None
_vectorstore = None


def get_embeddings():
    """
    Retorna el objeto embeddings, inicializándolo solo cuando se necesita.
    """
    global _embeddings
    if _embeddings is None:
        _embeddings = OpenAIEmbeddings()
    return _embeddings


def get_vectorstore():
    """Retorna el vectorstore, inicializándolo solo cuando se necesita."""
    global _vectorstore
    if _vectorstore is None:
        embeddings = get_embeddings()
        _vectorstore = Chroma(
            persist_directory=VECTOR_STORE_PATH, embedding_function=embeddings
        )
    return _vectorstore


def buscar_contexto(pregunta: str, filtro_nombre: str = None) -> str:
    """Busca fragmentos relevantes en la base de conocimiento RAG."""
    vectorstore = get_vectorstore()
    docs = vectorstore.similarity_search(pregunta, k=RAG_K_FRAGMENTS)
    if filtro_nombre:
        docs = [
            doc for doc in docs if filtro_nombre.lower() in doc.page_content.lower()
        ]
    return "\n\n".join([doc.page_content for doc in docs])
