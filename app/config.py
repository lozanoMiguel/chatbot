import os
from dotenv import load_dotenv

load_dotenv()

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-3.5-turbo"

# Base de datos
DATABASE_URL = os.getenv("DATABASE_URL", "chat_history.db")

# RAG
VECTOR_STORE_PATH = "./chroma_db"
RAG_K_FRAGMENTS = 10