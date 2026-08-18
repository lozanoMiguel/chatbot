import sys

import pysqlite3
import unicodedata
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

def eliminar_acentos(texto: str) -> str:
    """Elimina las tildes y diéresis de una cadena de texto."""
    # Descompone los caracteres con acento en su letra base + el acento suelto
    texto_normalizado = unicodedata.normalize('NFD', texto)
    # Filtra y conserva solo las letras base, eliminando los acentos
    return "".join([c for c in texto_normalizado if unicodedata.category(c) != 'Mn'])

def buscar_contexto(pregunta: str, filtro_nombre: str = None) -> str:
    """Busca fragmentos relevantes en la base de conocimiento RAG."""
    vectorstore = get_vectorstore()
    docs = vectorstore.similarity_search(pregunta, k=RAG_K_FRAGMENTS)
    if filtro_nombre:
        filtro_limpio = eliminar_acentos(filtro_nombre).lower()
        docs = [
            doc for doc in docs if filtro_limpio in eliminar_acentos(doc.page_content).lower()
        ]
    return "\n\n".join([doc.page_content for doc in docs])
