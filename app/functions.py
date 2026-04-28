import unicodedata
import re
from openai import OpenAI
from app.config import OPENAI_API_KEY

# Cliente OpenAI (reutilizamos el mismo)
client = OpenAI(api_key=OPENAI_API_KEY)

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
        from app.main import estado_usuario 
        estado_usuario[session_id]["ultimos_cafes"] = cafes
    
    if not cafes:
        return f"No tenemos cafés {perfil} para {metodo}. ¿Te gustaría probar otro perfil?"
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
    texto = unicodedata.normalize('NFKD', texto)
    texto = texto.encode('ASCII', 'ignore').decode('ASCII')
    
    # 3. Eliminar signos de puntuación y caracteres especiales
    #    Solo mantenemos letras, números y espacios
    texto = re.sub(r'[^a-z0-9\s]', '', texto)
    
    # 4. Eliminar espacios múltiples y trim
    texto = re.sub(r'\s+', ' ', texto).strip()
    
    return texto

def clasificar_intencion_simple(mensaje: str) -> str:
    """
    Clasifica usando reglas simples (rápido y gratuito).
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
    if any(phrase in user_norm for phrase in ["quiero comprar", "quiero un cafe", "recomienda", "cafe por favor"]):
        return "logica_compra"
    
    # ===== PALABRAS CLARAS DE RECORDATORIO =====
    if any(phrase in user_norm for phrase in ["que metodo", "que perfil", "que elegi", "como tomo"]):
        return "pregunta_recordatorio"
    
    # ===== SI EL MENSAJE ES MUY CORTO (posible respuesta a pregunta) =====
    if len(user_norm.split()) <= 2:
        palabras = user_norm.split()
        for p in palabras:
            if p in ["si", "sip", "claro", "correcto", "vale", "ok", "espresso", "filtro", "tradicional", "exotico", "funky"]:
                return "logica_compra"
    
    # No se pudo clasificar con reglas
    return None

async def clasificar_con_ia(mensaje: str) -> str:
    """
    Usa OpenAI para clasificar mensajes que las reglas simples no pudieron procesar.
    Retorna: 'logica_compra', 'ia_descripcion', 'pregunta_recordatorio', 'simple_saludo'
    """
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
                {"role": "system", "content": """
    Eres un clasificador de intenciones. Analiza el mensaje del usuario y responde SOLO con una de estas palabras:

    - DESCRIPCION: El usuario quiere que le DESCRIBAS un café (notas, sabor, origen, características). Ejemplos: "describeme el Alacrán", "qué notas tiene el café", "cómo es ese café", "cuéntame de esos cafés".

    - COMPRA: El usuario quiere comprar o que le RECOMIENDES un café. Incluye preguntas sobre método (espresso/filtro) o perfil (tradicional/exótico/funky). Ejemplos: "quiero un café", "qué café me recomiendas", "quiero espresso", "me gusta el perfil exótico".

    - RECORDATORIO: El usuario pregunta qué eligió antes. Ejemplos: "qué método elegí", "qué perfil dije", "qué me recomendaste".

    - SALUDO: El usuario saluda, agradece o se despide. Ejemplos: "hola", "gracias", "adiós", "buenos días".

    Responde solo con la palabra: DESCRIPCION, COMPRA, RECORDATORIO o SALUDO.
    """} ,
            {"role": "user", "content": mensaje}
        ],
        temperature=0,
        max_tokens=20
    )
    
    clasificacion = response.choices[0].message.content.strip().lower()
    
    # Mapear la respuesta de la IA a nuestros códigos internos
    mapeo = {
        "descripcion": "ia_descripcion",
        "compra": "logica_compra",
        "recordatorio": "pregunta_recordatorio",
        "saludo": "simple_saludo"
    }
    
    return mapeo.get(clasificacion, "logica_compra")