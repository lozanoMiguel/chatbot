import sys
import pysqlite3
sys.modules['sqlite3'] = pysqlite3
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from app.config import VECTOR_STORE_PATH, RAG_K_FRAGMENTS

embeddings = OpenAIEmbeddings()
vectorstore = Chroma(persist_directory=VECTOR_STORE_PATH, embedding_function=embeddings)

def buscar_contexto(pregunta: str) -> str:
    """Busca fragmentos relevantes en la base de conocimiento RAG."""
    docs = vectorstore.similarity_search(pregunta, k=RAG_K_FRAGMENTS)
    return "\n\n".join([doc.page_content for doc in docs])