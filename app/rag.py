import sys
import unicodedata

import pysqlite3

sys.modules["sqlite3"] = pysqlite3

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from chromadb.config import Settings

from app.config import RAG_K_FRAGMENTS, VECTOR_STORE_PATH

_embeddings = None
_vectorstore = None

# Apaga la telemetría de Chroma->PostHog. Sin esto, cada llamada intenta
# mandar un evento y falla ("capture() takes 1 positional argument but
# 3 were given") por incompatibilidad de versión entre chromadb y
# posthog — inofensivo pero ensucia los logs en cada consulta.
_CHROMA_SETTINGS = Settings(
    anonymized_telemetry=False,
    # CRÍTICO: sin is_persistent=True acá, pasar client_settings hace que
    # langchain_chroma arme un cliente EFÍMERO (en memoria) e ignore por
    # completo lo que hay en VECTOR_STORE_PATH — bug conocido de
    # langchain_chroma (github.com/langchain-ai/langchain/issues/16259).
    # Sin esto, cada consulta abre una colección vacía silenciosamente.
    is_persistent=True,
    persist_directory=VECTOR_STORE_PATH,
)


def obtener_metadata_cafes(nombres: list[str], tostado: str = None) -> list[dict]:
    if not nombres:
        return []

    vectorstore = get_vectorstore()
    nombres_normalizados = [eliminar_acentos(n).lower() for n in nombres]
    condicion_nombre = (
        {"nombre_normalizado": {"$in": nombres_normalizados}}
        if len(nombres_normalizados) > 1
        else {"nombre_normalizado": nombres_normalizados[0]}
    )
    where = {"$and": [{"tipo": "cafe"}, condicion_nombre]}

    coleccion = vectorstore.get(where=where, include=["metadatas"])
    metadatas = coleccion["metadatas"]

    if tostado:
        tostado_normalizado = METODO_A_TOSTADO.get(tostado.lower(), tostado.lower())
        tostado_normalizado = eliminar_acentos(tostado_normalizado).lower()
        filtrados = [
            m for m in metadatas
            if tostado_normalizado in eliminar_acentos(str(m.get("tostado", ""))).lower()
        ]
        if filtrados:
            metadatas = filtrados

    return metadatas


# ==================== VOCABULARIO AMIGABLE ====================
# Único criterio de afinamiento: PERFIL (exótico/tradicional/funky), la
# clasificación real de negocio — y, si hace falta, NIVEL de intensidad
# dentro de ese perfil. Emoji + resumen corto por línea en vez de una
# oración corrida: más fácil de escanear en el chat.
PERFIL_INFO = {
    "exotico": {"emoji": "🌸", "label": "Exótico", "resumen": "afrutado, floral, acidez brillante"},
    "tradicional": {"emoji": "🍫", "label": "Tradicional", "resumen": "achocolatado, cuerpo pronunciado, suave"},
    "funky": {"emoji": "🍷", "label": "Funky", "resumen": "vinoso, licoroso, para paladares aventureros"},
}

# Orden fijo de presentación (no depende del orden en que aparecen los
# candidatos en Chroma, que no está garantizado).
ORDEN_PERFILES = ["exotico", "tradicional", "funky"]

# Tu app maneja "espresso"/"filtro", pero la metadata TOSTADO usa
# "Expresso" (con x).
METODO_A_TOSTADO = {
    "espresso": "expresso",
    "filtro": "filtro",
}


def _construir_pregunta_perfil(metadatas: list[dict]) -> dict | None:
    """
    Primer (y principal) criterio de afinamiento: agrupa por
    perfil_categoria ("exotico" | "tradicional" | "funky"), la
    clasificación real del negocio. Las claves de las opciones quedan
    normalizadas (sin tilde) para que matcheen directo contra
    user_lower en chat.py. La pregunta se arma como lista (un perfil
    por línea) en vez de oración corrida — más fácil de leer.
    """
    grupos: dict[str, list[str]] = {}
    for meta in metadatas:
        categoria = meta.get("perfil_categoria", "")
        if categoria:
            grupos.setdefault(categoria, []).append(meta.get("nombre", ""))

    if len(grupos) < 2:
        return None

    categorias_presentes = [c for c in ORDEN_PERFILES if c in grupos]
    # Por si algún día aparece una categoria fuera de ORDEN_PERFILES
    # (typo en un .txt, perfil nuevo sin catalogar todavía): no la
    # perdemos, la agregamos al final en vez de que desaparezca la opción.
    categorias_presentes += [c for c in grupos if c not in categorias_presentes]

    lineas = []
    for categoria in categorias_presentes:
        info = PERFIL_INFO.get(categoria, {})
        emoji = info.get("emoji", "☕")
        label = info.get("label", categoria.capitalize())
        resumen = info.get("resumen", "")
        lineas.append(f"{emoji} **{label}** — {resumen}" if resumen else f"{emoji} **{label}**")

    pregunta = "¿Cuál te tienta más? ☕\n" + "\n".join(lineas)

    return {
        "pregunta": pregunta,
        "criterio": "perfil",
        "opciones": {c: grupos[c] for c in categorias_presentes},
    }


def _construir_pregunta_intensidad(metadatas: list[dict]) -> dict | None:
    """
    Segundo criterio, solo se dispara si dentro de un mismo perfil
    (ya filtrado por _construir_pregunta_perfil en la vuelta anterior)
    conviven cafés de nivel 1 (suave) con nivel 2/3 (intenso). Si el
    grupo no trae niveles mezclados (p.ej. todos nivel 0 por no tener
    el dato, o todos el mismo nivel), no discrimina y se deja pasar.
    """
    suave, intenso = [], []
    for meta in metadatas:
        nivel = meta.get("perfil_nivel", 0)
        if nivel == 1:
            suave.append(meta.get("nombre", ""))
        elif nivel in (2, 3):
            intenso.append(meta.get("nombre", ""))

    if not (suave and intenso):
        return None

    categorias = {meta.get("perfil_categoria", "") for meta in metadatas}
    etiqueta = categorias.pop() if len(categorias) == 1 else "este perfil"
    return {
        "pregunta": f"Dentro de lo {etiqueta}, ¿preferís algo más suave o algo más intenso?",
        "criterio": "intensidad",
        "opciones": {"suave": suave, "intenso": intenso},
    }


def candidatos_por_metodo(metodo: str, perfil: str = None) -> list[str]:
    """
    Primer filtro (duro): cafés cuyo TOSTADO corresponde al método y,
    si ya se conoce el perfil de antemano (identificar_perfil detectó
    "exotico"/"tradicional"/"funky" en el mensaje del usuario), también
    por perfil_categoria. Con esto el árbol de afinamiento se salta
    directo la pregunta de perfil y arranca en intensidad — o, si el
    cruce método+perfil ya da <=2, directo en la descripción final.
    """
    tostado = METODO_A_TOSTADO.get(metodo.lower(), metodo.lower())
    filtros = {"tostado": tostado}
    if perfil:
        filtros["perfil_categoria"] = perfil
    contexto = filtrar_por_metadata(**filtros)
    return [
        l.replace("NOMBRE:", "").strip()
        for l in contexto.split("\n")
        if l.strip().startswith("NOMBRE")
    ]


def elegir_criterio_discriminante(candidatos: list[str], metodo: str) -> dict | None:
    """
    Único árbol de afinamiento: perfil (exótico/tradicional/funky) y,
    si hace falta, intensidad (suave/intenso) dentro de ese perfil.
    No se pregunta nada más — si tras esto siguen quedando 3, 4 o 5
    candidatos, se describen todos y que el usuario elija (o pida
    "recomendame uno" para que se elija al azar, ver intencion_indiferencia
    en chat.py).

    Devuelve None si el grupo ya es chico (<=2 — con eso alcanza para
    describirlo directo, sin forzar la pregunta de intensidad) o si
    ningún criterio lo discrimina más. Con exactamente 3 candidatos
    igual se intenta perfil/intensidad: si el perfil ya viene resuelto
    (todos la misma categoría) y la intensidad no separa el grupo,
    esta misma función devuelve None un paso después y se describen
    los 3 igual.
    """
    if len(candidatos) <= 2:
        return None

    metadatas = obtener_metadata_cafes(candidatos, tostado=metodo)
    if not metadatas:
        return None

    secuencia = [
        ("perfil", _construir_pregunta_perfil),
        ("intensidad", _construir_pregunta_intensidad),
    ]

    for _criterio, constructor in secuencia:
        pregunta = constructor(metadatas)
        if pregunta:
            return pregunta

    return None


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = OpenAIEmbeddings()
    return _embeddings


def get_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        embeddings = get_embeddings()
        _vectorstore = Chroma(
            persist_directory=VECTOR_STORE_PATH,
            embedding_function=embeddings,
            client_settings=_CHROMA_SETTINGS,
        )
    return _vectorstore


def eliminar_acentos(texto: str) -> str:
    texto_normalizado = unicodedata.normalize("NFD", texto)
    return "".join([c for c in texto_normalizado if unicodedata.category(c) != "Mn"])


def _nombres_coincidentes(filtro_nombre: str) -> list[str]:
    vectorstore = get_vectorstore()
    filtro_limpio = eliminar_acentos(filtro_nombre).lower()

    coleccion = vectorstore.get(include=["metadatas"], where={"tipo": "cafe"})
    encontrados = []
    for meta in coleccion["metadatas"]:
        if filtro_limpio in meta.get("nombre_normalizado", ""):
            encontrados.append(meta.get("nombre", ""))

    return encontrados


def buscar_contexto(pregunta: str, filtro_nombre: str = None, tipo: str = None) -> str:
    vectorstore = get_vectorstore()

    condiciones = []
    k = RAG_K_FRAGMENTS

    if tipo:
        condiciones.append({"tipo": tipo})

    if filtro_nombre:
        nombres = _nombres_coincidentes(filtro_nombre)
        if not nombres:
            return ""
        condiciones.append(
            {"nombre": {"$in": nombres}} if len(nombres) > 1 else {"nombre": nombres[0]}
        )
        k = max(RAG_K_FRAGMENTS, len(nombres))

    if not condiciones:
        where = None
    elif len(condiciones) == 1:
        where = condiciones[0]
    else:
        where = {"$and": condiciones}

    docs = vectorstore.similarity_search(pregunta, k=k, filter=where)
    return "\n\n".join([doc.page_content for doc in docs])


def obtener_cafes_por_nombre(nombres: list[str], tostado: str = None) -> str:
    if not nombres:
        return ""

    vectorstore = get_vectorstore()
    nombres_normalizados = [eliminar_acentos(n).lower() for n in nombres]
    condicion_nombre = (
        {"nombre_normalizado": {"$in": nombres_normalizados}}
        if len(nombres_normalizados) > 1
        else {"nombre_normalizado": nombres_normalizados[0]}
    )
    where = {"$and": [{"tipo": "cafe"}, condicion_nombre]}

    coleccion = vectorstore.get(where=where, include=["documents", "metadatas"])
    documentos = coleccion["documents"]
    metadatas = coleccion["metadatas"]

    if tostado:
        tostado_normalizado = METODO_A_TOSTADO.get(tostado.lower(), tostado.lower())
        tostado_normalizado = eliminar_acentos(tostado_normalizado).lower()
        filtrados = [
            doc
            for doc, meta in zip(documentos, metadatas)
            if tostado_normalizado in eliminar_acentos(str(meta.get("tostado", ""))).lower()
        ]
        if filtrados:
            documentos = filtrados

    return "\n\n".join(documentos)


def _ranking_cafes(atributo_metadata: str, n: int, ascendente: bool, nombres: list[str] = None) -> str:
    vectorstore = get_vectorstore()
    where = {"tipo": "cafe"}

    if nombres:
        nombres_normalizados = [eliminar_acentos(n_).lower() for n_ in nombres]
        condicion_nombre = (
            {"nombre_normalizado": {"$in": nombres_normalizados}}
            if len(nombres_normalizados) > 1
            else {"nombre_normalizado": nombres_normalizados[0]}
        )
        where = {"$and": [{"tipo": "cafe"}, condicion_nombre]}

    coleccion = vectorstore.get(include=["metadatas", "documents"], where=where)
    items = list(zip(coleccion["metadatas"], coleccion["documents"]))
    items.sort(key=lambda item: item[0].get(atributo_metadata, 0), reverse=not ascendente)

    top = items[:n]
    return "\n\n".join([doc for _, doc in top])


def top_cafes_por_puntaje(n: int = 5, ascendente: bool = False, nombres: list[str] = None) -> str:
    return _ranking_cafes("puntaje_sca", n, ascendente, nombres)


def top_cafes_por_acidez(n: int = 5, ascendente: bool = False, nombres: list[str] = None) -> str:
    return _ranking_cafes("puntaje_acidez", n, ascendente, nombres)


def filtrar_por_metadata(tipo: str = "cafe", nombres: list[str] = None, **filtros) -> str:
    """
    Filtro exacto por campos de metadata (contains, no igualdad). Si se
    pasa `nombres`, primero restringe el universo a esos cafés — así
    faq_modo="filtro" puede combinarse con estado.ultimos_cafes (ej.
    "de esos, cuáles son de Colombia") igual que ya hace el ranking.
    """
    vectorstore = get_vectorstore()
    coleccion = vectorstore.get(include=["metadatas", "documents"], where={"tipo": tipo})

    nombres_normalizados = None
    if nombres:
        nombres_normalizados = {eliminar_acentos(n).lower() for n in nombres}

    resultados = []
    for meta, doc in zip(coleccion["metadatas"], coleccion["documents"]):
        if nombres_normalizados is not None and meta.get("nombre_normalizado", "") not in nombres_normalizados:
            continue
        coincide = True
        for clave, valor in filtros.items():
            valor_meta = eliminar_acentos(str(meta.get(clave, ""))).lower()
            valor_filtro = eliminar_acentos(str(valor)).lower()
            if valor_filtro not in valor_meta:
                coincide = False
                break
        if coincide:
            resultados.append(doc)

    return "\n\n".join(resultados)