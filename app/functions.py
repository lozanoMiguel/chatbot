import re
import unicodedata
from openai import OpenAI
from app.config import OPENAI_API_KEY
from app.models import ClasificacionSchema

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


def get_metodo(mensaje: str) -> str:
    if any(
        palabra in mensaje for palabra in ["espresso", "expresso", "espreso", "expreso"]
    ):
        return "espresso"
    elif any(palabra in mensaje for palabra in ["filtro", "filter", "filtrado"]):
        return "filtro"
    return ""


def get_perfil(mensaje: str) -> str:

    if "tradicional" in mensaje:
        return "tradicional"
    elif any(palabra in mensaje for palabra in ["exotico", "exotic"]):
        return "exotico"
    elif any(palabra in mensaje for palabra in ["funky", "fanky", "fonky"]):
        return "funky"
    return ""


def recomendar_cafe(metodo: str, perfil: str, session_id: str = None) -> str:
    """Recomienda cafés según método y perfil, y opcionalmente guarda la lista en el estado"""
    matriz = {
        ("espresso", "tradicional"): ["Alacrán", "Cóndor", "Lince", "Yurumi"],
        ("espresso", "exotico"): ["Dimeti", "Delfín Rosado", "Puma"],
        ("espresso", "funky"): ["Coyote"],
        ("filtro", "exotico"): ["Correcaminos", "Nebiri"],
    }
    cafes = matriz.get((metodo, perfil), [])

    # Guardar en el estado si se proporciona session_id
    if session_id and cafes:
        from app.state import estado_usuario

        estado_usuario[session_id]["ultimos_cafes"] = cafes

    if not cafes:
        return (
            f"No tenemos cafés {perfil} para {metodo}. ¿Te gustaría probar otro perfil?"
        )
    elif len(cafes) == 1:
        return f"Para {metodo} y perfil {perfil}, te recomiendo {cafes[0]}. ¡Es una excelente elección!"
    else:
        return f"Para {metodo} y perfil {perfil}, te recomiendo: {', '.join(cafes[:-1])} y {cafes[-1]}."


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


def clasificar_intencion_simple(mensaje: str) -> str:
    """
    Clasifica usando reglas simples.
    Retorna: 'logica_compra', 'simple_saludo', 'pregunta_recordatorio', o None si no está claro
    """
    user_norm = normalizar_texto(mensaje)

    # ===== SALUDOS Y AGRADECIMIENTOS =====
    if "gracias" in user_norm:
        return "simple_saludo"
    if any(word in user_norm for word in ["adios", "chao", "hasta luego", "bye"]):
        return "simple_saludo"
    if user_norm in ["hola", "buenos dias", "buenas tardes", "buenas noches"]:
        return "simple_saludo"

    # ===== PALABRAS CLARAS DE COMPRA =====
    if any(
        phrase in user_norm
        for phrase in ["quiero comprar", "quiero un cafe", "quiero un perfil", "recomiendame un cafe"]
    ):
        return "logica_compra"

    # ===== PALABRAS CLARAS DE RECORDATORIO =====
    if any(
        phrase in user_norm
        for phrase in ["que metodo", "que perfil", "que elegi", "como tomo"]
    ):
        return "pregunta_recordatorio"

    # ===== PALABRAS CLARAS DE DESCRIPCION DE CAFE =====
    if any(
        phrase in user_norm
        for phrase in [
            "describeme",
            "describime",
            "descríbeme",
            "descripcion",
            "contame",
            "cuentame",
            "notas",
            "caracteristicas",
            "sabor",
        ]
    ):
        return "ia_descripcion_cafe"

    # ===== SI EL MENSAJE ES MUY CORTO (posible respuesta a pregunta) =====
    if len(user_norm.split()) <= 2:
        palabras = user_norm.split()
        for p in palabras:
            if p in [
                "si",
                "sip",
                "claro",
                "correcto",
                "vale",
                "ok",
                "espresso",
                "filtro",
                "tradicional",
                "exotico",
                "funky",
            ]:
                return "logica_compra"

    # No se pudo clasificar con reglas
    return None


async def clasificar_con_ia(mensaje: str) -> str:
    """
    Usa OpenAI con Salidas Estructuradas para clasificar mensajes sin errores de formato.
    """
    client = get_openai_client()
    
    response = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """
                    Eres un clasificador de intenciones experto en café de especialidad. 
                    Analiza el mensaje del usuario y clasifícalo en una de las siguientes categorías:

                    - compra: Si el hilo de la conversacion es acerca de la compra o recomendacion de cafe y aun no se ha mencionado el metodo(maquina de espresso o filtro) o el perfil(tradicional,exotico o fanky)
                    - descripcion_cafe: El usuario pide describir un café en especifico o cafés recomendados(ej. "describeme el Alacrán", "qué origen tiene el cóndor", "puedes describirme esos cafes?", "hablame de esos cafes").
                    - descripcion_faq: El usuario quiere que le respondas preguntas tipicas en una cafeteria de especialidad. Ejemplo: "¿Qué café me recomiendas si soy principiante?", "¿Recomiéndame un café para filtro?", "¿Cuál es el café más ácido y afrutado?", "Explicame los diferentes perfiles cafe que tienen", "Explicame el cafe exotico","Como se prepara un cafe filtrado?", "Como es el tostado de cafe para espresso?" 
                    - recordatorio: Preguntas sobre recomendaciones previas (ej. "¿qué opciones tenía?", "¿qué cafés me habías recomendado?").
                    - saludo: Saludos, agradecimientos o despedidas (ej. "hola", "gracias", "adiós").
                    """,
            },
            {"role": "user", "content": mensaje},
        ],
        temperature=0,
        response_format=ClasificacionSchema, # Forzamos el formato Pydantic
    )

    # La IA garantiza devolver uno de los strings definidos en el Literal
    clasificacion = response.choices[0].message.parsed.intencion

    # Mapeo seguro con llaves controladas
    mapeo = {
        "descripcion_faq": "ia_faq",
        "descripcion_cafe": "ia_descripcion_cafe",
        "compra": "logica_compra",
        "recordatorio": "pregunta_recordatorio",
        "saludo": "simple_saludo",
    }

    return mapeo.get(clasificacion, "logica_compra")
