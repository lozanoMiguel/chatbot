import sys

import pysqlite3

sys.modules["sqlite3"] = pysqlite3

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from app.config import RAG_K_FRAGMENTS, VECTOR_STORE_PATH

embeddings = OpenAIEmbeddings()
vectorstore = Chroma(persist_directory=VECTOR_STORE_PATH, embedding_function=embeddings)


def buscar_contexto(pregunta: str, filtro_nombre: str = None) -> str:
    """
    Busca fragmentos relevantes en la base de conocimiento RAG.

    Args:
        pregunta: Texto de búsqueda (puede ser el nombre de un café)
        filtro_nombre: Si se proporciona, solo devuelve fragmentos que contengan este texto exacto
    """
    docs = vectorstore.similarity_search(pregunta, k=RAG_K_FRAGMENTS)

    # Si hay filtro por nombre, filtrar los resultados
    if filtro_nombre:
        docs = [doc for doc in docs if filtro_nombre.lower() in doc.page_content.lower()]
        print(f"📄 Documentos encontrados: {len(docs)}")
    return "\n\n".join([doc.page_content for doc in docs])
