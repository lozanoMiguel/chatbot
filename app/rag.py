import sys
import unicodedata
 
import pysqlite3
 
sys.modules["sqlite3"] = pysqlite3
 
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
 
from app.config import RAG_K_FRAGMENTS, VECTOR_STORE_PATH
 
_embeddings = None
_vectorstore = None
 
 
def obtener_metadata_cafes(nombres: list[str]) -> list[dict]:
    """
    Devuelve SOLO la metadata (no el texto completo) de los cafés cuyo
    nombre coincide con `nombres`. Se usa para inspeccionar atributos
    (sabor, cuerpo, acidez) de un grupo de candidatos y decidir cómo
    afinar una recomendación, sin necesitar el contenido completo.
    """
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
    return coleccion["metadatas"]
 
 
def construir_pregunta_afinamiento(nombres_candidatos: list[str]) -> dict | None:
    """
    Dado un grupo de cafés candidatos (ej. resultado de la matriz
    método+perfil), busca un atributo que los diferencie y arma una
    pregunta de afinamiento con las opciones REALES presentes en ese
    grupo (no opciones fijas de antemano, para que siga funcionando
    aunque cambie el catálogo).
 
    Devuelve None si no hay forma de diferenciar (ej. todos comparten
    el mismo sabor), o un dict:
    {
        "pregunta": "...",
        "criterio": "sabor",
        "opciones": {"achocolatado": ["Alacran", "Lince", "Condor"], "afrutado": ["Yurumi"]}
    }
    """
    metadatas = obtener_metadata_cafes(nombres_candidatos)
    if not metadatas:
        return None
 
    # Priorizamos "sabor" porque es el campo más categórico/consistente
    # de tu catálogo (achocolatado, afrutado, etc.), a diferencia de
    # "cuerpo" o "acidez" que suelen ser descripciones más libres.
    for criterio, etiqueta in [("sabor", "sabor"), ("cuerpo", "cuerpo")]:
        opciones: dict[str, list[str]] = {}
        for meta in metadatas:
            valor = meta.get(criterio, "").strip().lower()
            if not valor:
                continue
            opciones.setdefault(valor, []).append(meta.get("nombre", ""))
 
        # Solo sirve como pregunta de afinamiento si realmente separa
        # el grupo en 2+ subconjuntos distintos
        if len(opciones) >= 2:
            opciones_texto = " o ".join(f"algo {v}" for v in opciones.keys())
            return {
                "pregunta": f"Tenemos varias opciones — ¿preferís {opciones_texto}?",
                "criterio": criterio,
                "opciones": opciones,
            }
 
    return None
 
 
# Vocabulario amigable: traduce los valores técnicos de metadata a
# palabras simples que alguien sin conocimientos de café entendería.
# Si un valor nuevo aparece en el catálogo y no está mapeado, se usa
# el valor crudo tal cual (mejor mostrar algo que fallar).
SABOR_AMIGABLE = {
    "achocolatado": "dulce",
    "afrutado": "frutal",
    "licoroso": "intenso",
}
 
EMOJIS_SABOR = {
    "dulce": "🍫🍬",
    "frutal": "🍓🌸",
    "intenso": "🍷🔥",
}
 
CUERPO_AMIGABLE = {
    "meloso": "suave",
    "jugoso": "equilibrado",
    "cremoso": "cremoso",
    "pronunciado y mantequilloso": "con mucho cuerpo",
}
 
# Tu app maneja "espresso"/"filtro" (como lo escribe el usuario), pero la
# metadata TOSTADO usa la grafía "Expresso" (con x). Sin este mapeo, el
# filtro por método no encontraría ningún café.
METODO_A_TOSTADO = {
    "espresso": "expresso",
    "filtro": "filtro",
}
 
 
def _valor_amigable(campo: str, valor_crudo: str) -> str:
    mapeos = {"sabor": SABOR_AMIGABLE, "cuerpo": CUERPO_AMIGABLE}
    return mapeos.get(campo, {}).get(valor_crudo, valor_crudo)
 
 
def candidatos_por_metodo(metodo: str) -> list[str]:
    """
    Primer filtro (duro, no negociable): cafés cuyo TOSTADO corresponde
    al método del usuario. Devuelve solo los nombres.
    """
    tostado = METODO_A_TOSTADO.get(metodo.lower(), metodo.lower())
    contexto = filtrar_por_metadata(tostado=tostado)
    return [
        l.replace("NOMBRE:", "").strip()
        for l in contexto.split("\n")
        if l.strip().startswith("NOMBRE")
    ]
 
 
def _unir_natural(items: list[str]) -> str:
    """Une una lista en español con gramática natural: 'A', 'A o B',
    'A, B o C' — evita el 'A o B o C o D' que suena robótico."""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} o {items[1]}"
    return f"{', '.join(items[:-1])} o {items[-1]}"
 
 
def _construir_pregunta_sabor(metadatas: list[dict]) -> dict | None:
    """
    Primer criterio, siempre el primero en probarse: sabor, con
    vocabulario simple y emojis. Normalmente es binario (dulce / frutal),
    pero si hay cafés licorosos/fermentados en el grupo, se agrega un
    tercer bucket "intenso" en vez de forzarlos a encajar en los otros
    dos (evitaría recomendar un café funky a quien pidió "algo frutal").
    """
    grupos_crudos: dict[str, list[str]] = {}
    for meta in metadatas:
        valor = meta.get("sabor", "").strip().lower()
        if valor:
            grupos_crudos.setdefault(valor, []).append(meta.get("nombre", ""))
 
    grupos_amigables: dict[str, list[str]] = {}
    for valor_crudo, nombres in grupos_crudos.items():
        clave = _valor_amigable("sabor", valor_crudo)
        grupos_amigables.setdefault(clave, []).extend(nombres)
 
    if len(grupos_amigables) < 2:
        return None
 
    opciones_texto = _unir_natural(
        [f"algo {clave} {EMOJIS_SABOR.get(clave, '')}".strip() for clave in grupos_amigables.keys()]
    )
    return {
        "pregunta": f"¿Preferís {opciones_texto}?",
        "criterio": "sabor",
        "opciones": grupos_amigables,
    }
 
 
def _construir_pregunta_acidez(metadatas: list[dict]) -> dict | None:
    """Segundo criterio: acidez, dividida por la mediana del grupo actual."""
    valores_acidez = sorted(m.get("puntaje_acidez", 0) for m in metadatas)
    mediana = valores_acidez[len(valores_acidez) // 2]
    altos = [m.get("nombre", "") for m in metadatas if m.get("puntaje_acidez", 0) >= mediana]
    bajos = [m.get("nombre", "") for m in metadatas if m.get("puntaje_acidez", 0) < mediana]
    if not (altos and bajos):
        return None
    return {
        "pregunta": "¿Preferís algo más vivo y ácido, o algo más suave?",
        "criterio": "acidez",
        "opciones": {"vivo": altos, "suave": bajos},
    }
 
 
def _construir_pregunta_cuerpo(metadatas: list[dict]) -> dict | None:
    """
    Tercer criterio, de respaldo: cuerpo. Solo se usa si sabor y acidez
    ya se agotaron y el grupo sigue siendo grande.
    """
    grupos_crudos: dict[str, list[str]] = {}
    for meta in metadatas:
        valor = meta.get("cuerpo", "").strip().lower()
        if valor:
            grupos_crudos.setdefault(valor, []).append(meta.get("nombre", ""))
 
    grupos_amigables: dict[str, list[str]] = {}
    for valor_crudo, nombres in grupos_crudos.items():
        clave = _valor_amigable("cuerpo", valor_crudo)
        grupos_amigables.setdefault(clave, []).extend(nombres)
 
    if len(grupos_amigables) < 2 or len(grupos_amigables) > 3:
        return None
 
    opciones_texto = _unir_natural([f"algo {v}" for v in grupos_amigables.keys()])
    return {
        "pregunta": f"¿Preferís {opciones_texto}?",
        "criterio": "cuerpo",
        "opciones": grupos_amigables,
    }
 
 
def elegir_criterio_discriminante(candidatos: list[str], excluir: list[str] = None) -> dict | None:
    """
    Dado un grupo de cafés candidatos, decide la siguiente pregunta de
    afinamiento en un ORDEN FIJO: primero sabor (más intuitivo), después
    acidez, y como último respaldo cuerpo — en vez de competir
    dinámicamente por "el más balanceado", para que el flujo de preguntas
    sea predecible y siempre empiece por lo más fácil de responder.
 
    `excluir`: criterios ya usados en rondas anteriores (ej. ["sabor"]) —
    se saltan para no repetir la misma pregunta.
 
    Devuelve None si el grupo ya es chico (<=2), o si ningún criterio
    disponible logra discriminarlo más.
    """
    if len(candidatos) <= 2:
        return None
 
    excluir = excluir or []
    metadatas = obtener_metadata_cafes(candidatos)
    if not metadatas:
        return None
 
    for criterio, constructor in [
        ("sabor", _construir_pregunta_sabor),
        ("acidez", _construir_pregunta_acidez),
        ("cuerpo", _construir_pregunta_cuerpo),
    ]:
        if criterio in excluir:
            continue
        pregunta = constructor(metadatas)
        if pregunta:
            return pregunta
 
    return None
 
 
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
    texto_normalizado = unicodedata.normalize("NFD", texto)
    # Filtra y conserva solo las letras base, eliminando los acentos
    return "".join([c for c in texto_normalizado if unicodedata.category(c) != "Mn"])
 
 
def _nombres_coincidentes(filtro_nombre: str) -> list[str]:
    """
    Busca en la metadata de TODA la colección los nombres de café que
    contienen `filtro_nombre` (sin importar acentos/mayúsculas), comparando
    contra el campo `nombre_normalizado`.
    Devuelve la lista de nombres exactos tal como están guardados en
    metadata (`nombre`), para poder usarlos luego en un filtro nativo de
    Chroma.
    """
    vectorstore = get_vectorstore()
    filtro_limpio = eliminar_acentos(filtro_nombre).lower()
 
    coleccion = vectorstore.get(include=["metadatas"], where={"tipo": "cafe"})
    encontrados = []
    for meta in coleccion["metadatas"]:
        if filtro_limpio in meta.get("nombre_normalizado", ""):
            encontrados.append(meta.get("nombre", ""))
 
    return encontrados
 
 
def buscar_contexto(pregunta: str, filtro_nombre: str = None, tipo: str = None) -> str:
    """
    Busca fragmentos relevantes en la base de conocimiento RAG.
 
    `tipo` restringe la búsqueda a "cafe" o "faq" (o None para buscar en
    toda la colección). Úsalo siempre que sepas la intención de la
    pregunta, para que una intención "faq" nunca traiga documentos de
    café y viceversa.
 
    Si se pasa `filtro_nombre`, el filtro se aplica ANTES de la búsqueda
    semántica (usando metadata nativa de Chroma), no después. Esto evita
    perder el café buscado si no cayera dentro del top-k de similitud.
    """
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
        # Si el filtro ya acotó el universo a N cafés, no queremos que el
        # k por defecto recorte esa lista: pedimos al menos todos los que
        # matchearon el filtro (nunca menos que RAG_K_FRAGMENTS).
        k = max(RAG_K_FRAGMENTS, len(nombres))
 
    if not condiciones:
        where = None
    elif len(condiciones) == 1:
        where = condiciones[0]
    else:
        where = {"$and": condiciones}
 
    docs = vectorstore.similarity_search(pregunta, k=k, filter=where)
    return "\n\n".join([doc.page_content for doc in docs])
 
 
def obtener_cafes_por_nombre(nombres: list[str]) -> str:
    """
    Devuelve el contenido completo de los cafés cuyo nombre coincide con
    alguno de `nombres`, sin importar tildes/mayúsculas (ej. "Delfin Rosado"
    encuentra "Delfín Rosado").
 
    A diferencia de buscar_contexto, esto no usa similarity_search: cuando
    ya sabes el nombre exacto de los cafés que quieres (por ejemplo, porque
    vienen de describir_cafe() o recomendar_cafe()), no hace falta gastar
    una llamada de embeddings por cada uno ni arriesgarse a que el
    ranking semántico deje alguno afuera. Es un fetch directo por metadata.
    """
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
 
    coleccion = vectorstore.get(where=where, include=["documents"])
    return "\n\n".join(coleccion["documents"])
 
 
def _ranking_cafes(atributo_metadata: str, n: int, ascendente: bool, nombres: list[str] = None) -> str:
    """
    Ordena cafés por un atributo numérico de metadata (ej. puntaje_sca,
    puntaje_acidez) y devuelve los `n` primeros.
 
    Si se pasa `nombres`, el ranking se restringe SOLO a esos cafés (ej.
    los últimos recomendados en la conversación) en vez de todo el
    catálogo — para resolver preguntas tipo "¿cuál de esos es más ácido?".
    """
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
    """
    Devuelve los `n` cafés con mayor (o menor) PUNTAJE_SCA.
 
    Este tipo de pregunta ("¿cuáles son los mejores/peores cafés?") es una
    consulta de ranking/agregación, no de similitud semántica: recorre TODA
    la colección (o solo `nombres`, si se pasa) y ordena por metadata, en
    lugar de usar similarity_search.
    """
    return _ranking_cafes("puntaje_sca", n, ascendente, nombres)
 
 
def top_cafes_por_acidez(n: int = 5, ascendente: bool = False, nombres: list[str] = None) -> str:
    """
    Devuelve los `n` cafés con mayor (o menor) PUNTAJE_ACIDEZ.
 
    Al igual que top_cafes_por_puntaje, esto es una consulta de
    ranking/agregación. Si se pasa `nombres`, el ranking se restringe a
    esos cafés en vez de todo el catálogo (ej. "¿cuál de esos es más
    ácido?" sobre los últimos recomendados).
 
    Por defecto (ascendente=False) devuelve los MÁS ácidos primero.
    Usa ascendente=True para los MENOS ácidos primero.
    """
    return _ranking_cafes("puntaje_acidez", n, ascendente, nombres)
 
 
def filtrar_por_metadata(tipo: str = "cafe", **filtros) -> str:
    """
    Devuelve todos los documentos de metadata `tipo` que coinciden
    exactamente con los filtros dados, por ejemplo:
 
        filtrar_por_metadata(pais="Colombia", proceso="Lavado")
 
    Útil para preguntas tipo "¿qué cafés tienen de Colombia?" donde no hace
    falta ranking ni búsqueda semántica, solo un filtro exacto.
 
    Por defecto restringe a tipo="cafe" para no mezclar con FAQs.
    """
    vectorstore = get_vectorstore()
    coleccion = vectorstore.get(include=["metadatas", "documents"], where={"tipo": tipo})
 
    resultados = []
    for meta, doc in zip(coleccion["metadatas"], coleccion["documents"]):
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
 