import os
import re
import sys
 
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
    import shutil
 
    from dotenv import load_dotenv
    from langchain_core.documents import Document
    from langchain_chroma import Chroma
    from langchain_openai import OpenAIEmbeddings
    from chromadb.config import Settings
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
 
 
import unicodedata
 
 
def normalizar_texto(texto: str) -> str:
    """Quita tildes/diéresis y pasa a minúsculas, para poder comparar
    nombres de forma consistente sin importar cómo se escribieron."""
    texto_normalizado = unicodedata.normalize("NFD", texto)
    sin_acentos = "".join(c for c in texto_normalizado if unicodedata.category(c) != "Mn")
    return sin_acentos.lower()


def parse_perfil(valor_crudo: str) -> tuple[str, int]:
    """
    Separa el campo PERFIL en categoria + nivel de intensidad.

    'Exótico (nivel 1/3)' -> ('exotico', 1)
    'Funky (nivel 3/3)'   -> ('funky', 3)
    'Exotico'             -> ('exotico', 0)   # sin nivel declarado en el .txt
    ''                    -> ('', 0)

    El nivel ausente se guarda como 0 (no None) para que Chroma pueda
    filtrar/ordenar sobre metadata numérica sin problemas de tipo mixto.
    """
    valor_crudo = (valor_crudo or "").strip()
    if not valor_crudo:
        return "", 0

    match = re.match(r"([A-Za-zÁÉÍÓÚáéíóúÑñ]+)\s*(?:\(nivel\s*(\d)\s*/\s*3\))?", valor_crudo)
    if not match:
        return normalizar_texto(valor_crudo), 0

    categoria = normalizar_texto(match.group(1))
    nivel = int(match.group(2)) if match.group(2) else 0
    return categoria, nivel
 
 
def parse_cafe_file(filepath: str) -> Document:
    """
    Lee un archivo .txt con campos tipo 'CLAVE: valor' (uno por café)
    y lo convierte en un Document con:
      - page_content: el texto completo, íntegro (esto es lo que se embebe)
      - metadata: campos estructurados, útiles para filtrar y ordenar
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
 
    campos = {}
    for linea in content.strip().split("\n"):
        if ":" in linea:
            clave, valor = linea.split(":", 1)
            campos[clave.strip().upper()] = valor.strip()
 
    # Intentamos convertir los puntajes numéricos; si fallan, quedan en 0
    try:
        puntaje_sca = float(campos.get("PUNTAJE_SCA", 0) or 0)
    except ValueError:
        puntaje_sca = 0.0
 
    try:
        puntaje_acidez = float(campos.get("PUNTAJE_ACIDEZ", 0) or 0)
    except ValueError:
        puntaje_acidez = 0.0

    perfil_categoria, perfil_nivel = parse_perfil(campos.get("PERFIL", ""))
    if not perfil_categoria:
        print(f"   ⚠️ {filepath}: PERFIL vacío o no reconocido ('{campos.get('PERFIL', '')}')")
    elif perfil_nivel == 0:
        print(f"   ⚠️ {filepath}: PERFIL '{campos.get('PERFIL', '')}' sin nivel declarado, se guarda perfil_nivel=0")
 
    metadata = {
        "tipo": "cafe",
        "nombre": campos.get("NOMBRE", ""),
        "nombre_normalizado": normalizar_texto(campos.get("NOMBRE", "")),
        "pais": campos.get("PAIS", ""),
        "region": campos.get("REGION", ""),
        "proceso": campos.get("PROCESO", ""),
        "variedad": campos.get("VARIEDAD", ""),
        "tostado": campos.get("TOSTADO", ""),
        "perfil": campos.get("PERFIL", ""),
        "perfil_categoria": perfil_categoria,  # "exotico" | "tradicional" | "funky"
        "perfil_nivel": perfil_nivel,          # 1-3, o 0 si no está declarado
        "sabor": campos.get("SABOR", ""),
        "acidez": campos.get("ACIDEZ", ""),
        "puntaje_acidez": puntaje_acidez,
        "cuerpo": campos.get("CUERPO", ""),
        "puntaje_sca": puntaje_sca,
        "source": filepath,
    }
 
    return Document(page_content=content.strip(), metadata=metadata)
 
 
def parse_faq_file(filepath: str) -> list[Document]:
    """
    Lee un archivo .txt con varios pares PREGUNTA:/RESPUESTA: separados por
    línea en blanco, y devuelve un Document por cada par.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
 
    bloques = [b.strip() for b in content.strip().split("\n\n") if b.strip()]
    documents = []
 
    for bloque in bloques:
        pregunta = ""
        respuesta_lineas = []
        modo = None
 
        for linea in bloque.split("\n"):
            if linea.upper().startswith("PREGUNTA:"):
                pregunta = linea.split(":", 1)[1].strip()
                modo = "pregunta"
            elif linea.upper().startswith("RESPUESTA:"):
                respuesta_lineas.append(linea.split(":", 1)[1].strip())
                modo = "respuesta"
            elif modo == "respuesta":
                # por si la respuesta continúa en una línea siguiente
                respuesta_lineas.append(linea.strip())
 
        respuesta = " ".join(respuesta_lineas).strip()
        if not pregunta or not respuesta:
            continue
 
        page_content = f"Pregunta: {pregunta}\nRespuesta: {respuesta}"
        metadata = {
            "tipo": "faq",
            "pregunta": pregunta,
            "source": filepath,
        }
        documents.append(Document(page_content=page_content, metadata=metadata))
 
    return documents
 
 
try:
    print("📁 Buscando cafés en: documentos_cafeteria/cafes/")
    documents = []
    for filepath in glob.glob("documentos_cafeteria/cafes/**/*.txt", recursive=True):
        print(f"   📄 Procesando: {filepath}")
        documents.append(parse_cafe_file(filepath))
    print(f"✅ Total cafés cargados: {len(documents)}")
 
    print("📁 Buscando FAQs en: documentos_cafeteria/faq/")
    faq_count = 0
    for filepath in glob.glob("documentos_cafeteria/faq/**/*.txt", recursive=True):
        print(f"   📄 Procesando: {filepath}")
        faqs = parse_faq_file(filepath)
        documents.extend(faqs)
        faq_count += len(faqs)
    print(f"✅ Total preguntas de FAQ cargadas: {faq_count}")
 
    print(f"✅ Total documentos a indexar: {len(documents)}")
except Exception as e:
    print(f"❌ Error al cargar documentos: {e}")
    sys.exit(1)
 
# Nota: ya no usamos RecursiveCharacterTextSplitter.
# Cada archivo .txt representa un solo café y ya es un chunk completo y
# autocontenido. Partirlo con un splitter genérico podía cortar un café
# a la mitad (dejando, por ejemplo, el PUNTAJE_SCA en un chunk distinto
# a la DESCRIPCION_CORTA), lo cual degradaba la calidad de las búsquedas.
 
try:
    print("🧠 Generando embeddings y guardando en Chroma...")
    persist_directory = "./chroma_db"
 
    # Chroma.from_documents() AGREGA documentos, no reemplaza los existentes.
    # Sin este paso, cada vez que se re-corre este script (por ejemplo, tras
    # agregar un campo nuevo de metadata) se duplican todos los cafés/FAQs
    # ya indexados en vez de reemplazarlos. Borrar el índice previo garantiza
    # que cada corrida sea un reindex completo y limpio.
    if os.path.exists(persist_directory):
        print(f"🧹 Eliminando índice anterior en {persist_directory} para evitar duplicados...")
        shutil.rmtree(persist_directory)
 
    embeddings = OpenAIEmbeddings()
    # anonymized_telemetry=False evita el warning "Failed to send telemetry
    # event... capture() takes 1 positional argument but 3 were given"
    # (incompatibilidad de versión chromadb/posthog, inofensivo pero ruidoso).
    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=persist_directory,
        client_settings=Settings(
            anonymized_telemetry=False,
            is_persistent=True,
            persist_directory=persist_directory,
        ),
    )
    print("✅ Índice RAG guardado en ./chroma_db")
 
    # Verificación DENTRO del mismo proceso, antes de salir
    conteo_inmediato = vectorstore._collection.count()
    print(f"🔬 DEBUG: conteo inmediato tras indexar (mismo proceso): {conteo_inmediato}")
    print(f"🔬 DEBUG: nombre de colección (escritura): {vectorstore._collection.name}")
    print(f"🔬 DEBUG: persist_directory absoluto (escritura): {os.path.abspath(persist_directory)}")
except Exception as e:
    print(f"❌ Error al generar embeddings: {e}")
    sys.exit(1)
 
print("🎉 INDEXACIÓN COMPLETADA CON ÉXITO")