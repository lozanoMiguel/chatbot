import json
import re
import unicodedata
from typing import Optional

from openai import OpenAI

from app.config import OPENAI_API_KEY
from app.database import (
    intencion_recomendacion,
    intencion_descripcion,
    intencion_faq,
    intencion_metodo,
    intencion_saludo,
    lista_cafes,
    lista_metodos,
    palabras_espresso,
    palabras_filtro,
    seniales_listado,
    seniales_ranking,
    lista_perfiles
)
from app.models.preferencias_usuario import estado_usuario

# Cliente OpenAI (reutilizamos el mismo)
_openai_client = None


def get_openai_client():
    """
    Retorna el cliente de OpenAI, inicializándolo solo cuando se llama por primera vez.
    Esto evita errores de importación cuando no hay API key (ej. en el CI).
    """
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client

def identificar_perfil(mensaje: str, session_id: str):
    if any(per in mensaje for per in lista_perfiles):
        estado_usuario[session_id].perfil = get_perfil(mensaje)
    
        
def identificar_metodo(mensaje: str, session_id: str):
    if any(met in mensaje for met in lista_metodos):
        estado_usuario[session_id].metodo = get_metodo(mensaje)
    elif any(phrase in mensaje for phrase in intencion_metodo):
        nuevo_metodo = get_metodo(mensaje, True)
        if nuevo_metodo is not None:
            estado_usuario[session_id].metodo = nuevo_metodo

def get_metodo(mensaje: str, flag_ia: bool = False) -> Optional[str]:
    respuesta = ""
    if flag_ia:
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                        {
                            "role": "system",
                            "content": """
                                Eres un clasificador de intenciones experto en café de especialidad.
                                Analiza el mensaje del usuario y clasifícalo en una de las siguientes categorías:
                                - espresso: Si en el mensaje el usuario hace alusion a una maquina de espresso o si solo menciona alguna marca de cafetera:(ej:"De'Longhi", "Nespresso", "Breville", "La Marzocco", "Rocket", "Ninja", etc)
                                - filtro: si el mensaje hace alusion a un metodo de filtrado(ej: "V60", "Chemex", "Prensa francesa", "AeroPress", "Clever Dripper") o marca de metodo de filtrado: (ej: "hario", "cafec", etc)
                                Si no encaja en ninguna de las categorias devuelve NONE
                            """,
                        },
                        {"role": "user", "content": mensaje}],
            temperature=0.5,
            max_tokens=20,
        )
        respuesta = response.choices[0].message.content
        print(f"Utilizando IA para detectar METODO! {respuesta}")
        if respuesta == "NONE":
            respuesta = None
        return respuesta
    if any(palabra in mensaje for palabra in palabras_espresso):
        respuesta = "espresso"
        return respuesta
    elif any(palabra in mensaje for palabra in palabras_filtro):
        respuesta = "filtro"
        return respuesta

def get_perfil(mensaje: str) -> str:
    respuesta = ""
    
    if any(palabra in mensaje for palabra in ["tradicional", "chocolat", "poca acidez", "clasico", "dulce"]):
        respuesta = "tradicional"
    elif any(palabra in mensaje for palabra in [ "exotic", "citrico", "floral", "citri", "frutal"]):
        respuesta = "exotico"
    elif any(palabra in mensaje for palabra in ["funky", "fanky", "fonky", "fermen","mucha acidez", "licor"]):
        respuesta = "funky"
    return respuesta

def cafes_mencionados(mensaje: str, ultimos_cafes:Optional[list])-> list:
    cafes_mencionados = []
    
    for cafe in lista_cafes:
        cafe_normalizado = normalizar_texto(cafe)  # normaliza el cafe que coincidió para buscarlo en el mensaje pero agrega el cafe sin normalizar para la busqueda en el indice rag
        if cafe_normalizado in mensaje:
            cafes_mencionados.append(cafe)

    if cafes_mencionados:
        print(f"Usuario menciono especificamente{cafes_mencionados}")

    elif ultimos_cafes:
        cafes_mencionados = ultimos_cafes
        print("Usando ultimos cafes mencionados en la conversacion")

    # PRIORIDAD 2: Si no hay cafés guardados, usar la matriz según método+perfil
    #elif metodo and perfil:
        #cafes_mencionados = recomendar_cafe(metodo, perfil)
        #print(f"   📌 Usando matriz de funcion recomendar_Cafe: {cafes_mencionados}")

    return cafes_mencionados

def normalizar_texto(texto: str) -> str:
    """
    Normaliza el texto: minúsculas, sin acentos, sin caracteres especiales.

    Ejemplos:
        "¿Cómo tomas tu café?" → "como tomas tu cafe"
        "¡Hola! ¿Qué tal?" → "hola que tal"
        "Té o café?" → "te o cafe"
    """
    # 1. Convertir a minúsculas
    texto = texto.lower()

    # 2. Eliminar acentos (normalizar a forma ASCII)
    #    'café' → 'cafe', 'té' → 'te', 'más' → 'mas'
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ASCII", "ignore").decode("ASCII")

    # 3. Eliminar signos de puntuación y caracteres especiales
    #    Solo mantenemos letras, números y espacios
    texto = re.sub(r"[^a-z0-9\s]", "", texto)

    # 4. Eliminar espacios múltiples y trim
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto

def resolver_respuesta_afinamiento(user_lower: str, pregunta_afinando: dict) -> list[str] | None:
    """
    Resuelve qué opción eligió el usuario para la pregunta de afinamiento
    activa.

    Para 'leche' no alcanza con el match genérico (clave in user_lower):
    las claves internas son 'con_leche'/'sin_leche' con guión bajo, y el
    usuario nunca escribe eso — escribe "con leche", "sin leche", "solo",
    etc. Además hay que priorizar 'sin' explícitamente, porque "sin
    leche" también contiene la palabra "leche" y si se chequea "leche"
    primero, cualquier respuesta cae siempre en con_leche.

    Para el resto de los criterios (sabor, continente) las claves ya son
    palabras sueltas que el usuario escribe tal cual (dulce, frutal,
    funky, america, africa), así que ahí se mantiene el match directo.
    """
    criterio = pregunta_afinando.get("criterio")
    opciones = pregunta_afinando["opciones"]

    if criterio == "leche":
        if contains_any(user_lower, ["sin leche", "solo", "negro", "sin"]):
            return opciones.get("sin_leche")
        if contains_any(user_lower, ["con leche", "leche", "con"]):
            return opciones.get("con_leche")
        return None

    return next((cafes for clave, cafes in opciones.items() if clave in user_lower), None)

def contains_any(text, terms):
    return any(
        re.search(rf"\b{re.escape(term)}\b", text)
        for term in terms
    )

# Palabras que delatan una pregunta CONCEPTUAL ("¿qué es el filtro?",
# "diferencia entre espresso y filtro") en vez de un pedido directo
# ("para espresso", "algo tradicional"). es_pedido_metodo_perfil() las
# usa para no atropellar intencion_faq/intencion_descripcion — sin esta
# guarda, cualquier mensaje que solo mencione un método o perfil (por
# ejemplo una pregunta sobre qué diferencia hay entre ellos) caería
# directo en intencion_recomendacion.
PALABRAS_CONCEPTUALES = {
    "que", "como", "cual", "cuales", "por", "porque", "diferencia",
    "significa", "significan", "explicame", "explica",
}


def es_pedido_metodo_perfil(mensaje_normalizado: str) -> bool:
    """
    Detecta pedidos directos y cortos que mencionan método y/o perfil sin
    usar ninguna de las frases explícitas de intencion_recomendacion —
    el patrón más común una vez que el chat ofrece perfiles: "para
    espresso", "para filtro exotico", "algo tradicional".

    Restringido a mensajes de <=5 palabras y sin palabras conceptuales
    para no capturar preguntas tipo "¿qué diferencia hay entre espresso
    y filtro?", que deben seguir cayendo en intencion_faq (vía IA, ya
    que esos términos no están en el listado de intencion_faq).
    """
    palabras = mensaje_normalizado.split()
    if len(palabras) > 5:
        return False
    if any(palabra in PALABRAS_CONCEPTUALES for palabra in palabras):
        return False

    menciona_metodo = any(met in mensaje_normalizado for met in lista_metodos)
    menciona_perfil = any(per in mensaje_normalizado for per in lista_perfiles)
    return menciona_metodo or menciona_perfil

def requiere_ia(mensaje_normalizado: str) -> bool:
    texto = f" {mensaje_normalizado} "  # padding para que " mejor " matchee al inicio/fin también
    return any(p in texto for p in seniales_listado + seniales_ranking)

def clasificar_intencion_simple(mensaje: str) -> dict | None:
    user_norm = normalizar_texto(mensaje)

    # 1. Prioridad absoluta: si menciona un café por nombre, es descripción
    #    (evita que "proceso"/"acidez" del café X se coman por intencion_faq)
    if any(normalizar_texto(cafe) in user_norm for cafe in lista_cafes):
        return {"intent": "intencion_descripcion", "confidence": 1.0}

    if contains_any(user_norm, intencion_descripcion):
        return {"intent": "intencion_descripcion", "confidence": 1.0}

    if contains_any(user_norm, intencion_recomendacion):
        return {"intent": "intencion_recomendacion", "confidence": 1.0}

    if es_pedido_metodo_perfil(user_norm):
        return {"intent": "intencion_recomendacion", "confidence": 1.0}

    if user_norm in intencion_saludo:
        return {"intent": "intencion_saludo", "confidence": 1.0}

    # 2. Recién acá, FAQ genérica — y solo si no hubo match de perfil/recomendación
    if contains_any(user_norm, intencion_faq):
        if requiere_ia(user_norm):
            return None
        return {
            "intent": "intencion_faq", "confidence": 1.0,
            "faq_modo": "conceptual", "atributo_ranking": None,
            "orden": None, "n": None, "filtros": {},
        }

    return None

async def clasificar_con_ia(mensaje: str, historial: list[dict] = None) -> dict:
    default = {
        "intent": "intencion_recomendacion",
        "confidence": 0.0,
        "faq_modo": None,
        "atributo_ranking": None,
        "orden": None, "n": None,
        "filtros": {}
    }

    contexto_conversacion = ""
    
    if historial:
        turnos = []
        for turno in historial:
            rol = "Usuario" if turno["role"] == "user" else "Asistente"
            turnos.append(f"{rol}: {turno['content']}")
        contexto_conversacion = "\n".join(turnos)

    system_prompt = f"""
        Eres un clasificador de intenciones para un chatbot de café de especialidad.
        Responde SOLO con JSON, sin texto adicional ni markdown.

        {"HISTORIAL RECIENTE (úsalo SOLO para entender referencias ambiguas como 'ese café', 'los anteriores', 'otro parecido' — clasifica ÚNICAMENTE el último mensaje del usuario, no los del historial):" if contexto_conversacion else ""}
        {contexto_conversacion}

        INTENCIONES:

        intencion_recomendacion: el usuario quiere que le recomienden un café, de forma directa
        (menciona método, sabores que busca, o pide ayuda para elegir).
        Ej: "Quiero un café exótico", "Tengo una V60, ¿qué me recomiendas?",
        "Busco algo achocolatado", "No sé qué elegir".

        intencion_descripcion: el usuario pregunta por las características de uno
        o más cafés mediante nombre.
        Ej: "Descríbeme el Alacrán", "¿Qué origen tiene el Cóndor?",
        "Diferencia entre el Alacrán y el Cóndor".

        intencion_faq: preguntas generales sobre café (acidez, procesos, métodos,
        características, origenes) SIN referirse a un café concreto por nombre. Incluye
        pedir un listado/ranking de productos reales según un atributo.
        Ej: "¿Qué significa que un café sea ácido?", "¿Cuáles son los cafés más
        ácidos?", "Diferencia entre lavado y natural", "¿Qué cafés son de Colombia?".

        Si intencion_faq pide un LISTADO de cafés reales (no una explicación
        conceptual), agrega:
        - faq_modo: "ranking" (pide orden: "más ácido", "mejor puntuado") |
        "filtro" (pide un criterio exacto: "de Colombia", "proceso lavado") |
        "conceptual" (solo explicación, sin listar productos)
        - alcance: "catalogo_completo" | "cafes_previos"
        Usa "cafes_previos" SOLO si el usuario se refiere explícitamente a
        cafés ya mencionados/recomendados en la conversación (ej: "de esos
        cuál es más ácido", "entre los que me diste", "de esos dos").
        Usa "catalogo_completo" para preguntas generales sobre toda la tienda
        (ej: "cuáles son los cafés más ácidos que tienen").
        Solo aplica cuando faq_modo es "ranking" o "filtro"; en otro caso, null.
        - atributo_ranking: "acidez" | "puntaje" | null (solo si faq_modo=ranking)
        - orden: "desc" | "asc" | null
        - n: cantidad de resultados pedidos, default 1
        - filtros: {{"pais": "...", "proceso": "...", "perfil": "...", "tostado": "..."}}
        (solo si faq_modo=filtro, solo las claves mencionadas). "tostado" es el
        método de preparación que menciona el usuario: "espresso" | "filtro"
        (ej: "cafés de Colombia para espresso" -> filtros: {{"pais": "Colombia",
        "tostado": "espresso"}} — permite combinar origen y método en un mismo
        filtro).

        intencion_saludo: saludo, agradecimiento o despedida SIN otra petición.
        Ej: "Hola", "Gracias", "Nos vemos".
        Si el saludo va con una petición, clasifica según la petición:
        "Hola, ¿qué me recomiendas?" -> intencion_compra.

        fallback: cualquier tema fuera del ámbito de la cafetería.
        Ej: "Messi", "¿Qué hora es?".

        FORMATO DE RESPUESTA:
        {{
        "intent": "intencion_recomendacion" | "intencion_descripcion" | "intencion_faq" | "intencion_saludo" | "fallback",
        "confidence": 0.0 a 1.0,
        "faq_modo": "conceptual" | "ranking" | "filtro" | null,
        "alcance": "catalogo_completo" | "cafes_previos",
        "atributo_ranking": "acidez" | "puntaje" | null,
        "orden": "desc" | "asc" | null,
        "n": entero | null,
        "filtros": {{{{}}}}
        }}

        confidence:
        0.90-1.00 clara | 0.75-0.89 bastante clara | 0.50-0.74 ambigua | 0.00-0.49 incierta
    """

    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": mensaje},
            ],
            response_format={"type": "json_object"},
        )

        clasificacion = response.choices[0].message.content.strip()
        json_match = re.search(r"\{.*\}", clasificacion, re.DOTALL)
        if not json_match:
            print(f"⚠️ No se encontró JSON en la respuesta: {clasificacion}")
            return default

        datos = json.loads(json_match.group())

        confidence = float(datos.get("confidence", 0.0))
        intent = datos.get("intent", "intencion_recomendacion")

        if 0.50 <= confidence < 0.75:
            intent = "intencion_recomendacion"

        return {
            "intent": intent,
            "confidence": confidence,
            "faq_modo": datos.get("faq_modo"),
            "alcance": datos.get("alcance"),
            "atributo_ranking": datos.get("atributo_ranking"),
            "orden": datos.get("orden"),
            "n": datos.get("n"),
            "filtros": datos.get("filtros") or {},
        }

    except Exception as e:
        print(f"❌ Error al clasificar con IA: {e}")
        return default