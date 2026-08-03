import sys
import os

print("🚀 INICIANDO INDEXACIÓN DE DOCUMENTOS...")
print(f"📁 Directorio actual: {os.getcwd()}")
print(f"📂 Archivos en el directorio: {os.listdir('.')}")

try:
    # Parche para SQLite
    print("📦 Parcheando SQLite...")
    import sys
    import pysqlite3
    sys.modules['sqlite3'] = pysqlite3
    print("✅ SQLite parcheado correctamente")
except Exception as e:
    print(f"❌ Error al parchear SQLite: {e}")
    sys.exit(1)

try:
    print("📚 Importando librerías...")
    import glob
    from dotenv import load_dotenv
    from langchain_community.document_loaders import TextLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_openai import OpenAIEmbeddings
    from langchain_community.vectorstores import Chroma
    from langchain_core.documents import Document
    print("✅ Librerías importadas correctamente")
except Exception as e:
    print(f"❌ Error al importar librerías: {e}")
    sys.exit(1)

try:
    print("📂 Cargando variables de entorno...")
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY no encontrada en variables de entorno")
        sys.exit(1)
    print(f"✅ OPENAI_API_KEY encontrada (primeros 10 caracteres: {api_key[:10]}...)")
except Exception as e:
    print(f"❌ Error al cargar variables de entorno: {e}")
    sys.exit(1)

try:
    print("📁 Buscando documentos en: documentos_cafeteria/")
    documents = []
    for filepath in glob.glob("documentos_cafeteria/**/*.txt", recursive=True):
        print(f"   📄 Procesando: {filepath}")
        loader = TextLoader(filepath, encoding="utf-8")
        documents.extend(loader.load())
    print(f"✅ Total documentos cargados: {len(documents)}")
except Exception as e:
    print(f"❌ Error al cargar documentos: {e}")
    sys.exit(1)

try:
    print("✂️ Dividiendo documentos en fragmentos...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        separators=["\n\n", "\n", " ", ""]
    )
    chunks = text_splitter.split_documents(documents)
    print(f"✅ Fragmentos generados: {len(chunks)}")
except Exception as e:
    print(f"❌ Error al dividir documentos: {e}")
    sys.exit(1)

try:
    print("🧠 Generando embeddings y guardando en Chroma...")
    embeddings = OpenAIEmbeddings()
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory="./chroma_db"
    )
    print("✅ Índice RAG guardado en ./chroma_db")
except Exception as e:
    print(f"❌ Error al generar embeddings: {e}")
    sys.exit(1)

print("🎉 INDEXACIÓN COMPLETADA CON ÉXITO")