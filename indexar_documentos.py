import sys

import pysqlite3

from app.rag import get_embeddings

sys.modules["sqlite3"] = pysqlite3
import glob

from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

print("🚀 Iniciando indexación de documentos...")
# 1. Cargar todos los archivos .txt desde la carpeta 'documentos_cafeteria'
documents = []
for filepath in glob.glob("documentos_cafeteria/**/*.txt", recursive=True):
    print(f"Procesando: {filepath}")
    loader = TextLoader(filepath, encoding="utf-8")
    # Cada archivo se convierte en uno o más documentos (si es muy grande, se divide)
    documents.extend(loader.load())

print(f"Total documentos cargados: {len(documents)}")

# 2. Dividir en fragmentos (chunks) para una búsqueda más precisa
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800, chunk_overlap=100, separators=["\n\n", "\n", " ", ""]
)
chunks = text_splitter.split_documents(documents)
print(f"Fragmentos generados: {len(chunks)}")

# 3. Generar embeddings y guardar en Chroma
embeddings = get_embeddings()
vectorstore = Chroma.from_documents(
    documents=chunks, embedding=embeddings, persist_directory="./chroma_db"
)
print("✅ Índice RAG guardado en ./chroma_db")
