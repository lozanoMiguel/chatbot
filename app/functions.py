import unicodedata
import re

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

def preguntar_metodo() -> str:
    return "¿Cómo tomas tu café, en máquina de espresso o en filtro?"

def preguntar_perfil(metodo: str = None) -> str:
    if metodo:
        return f"Para café en {metodo}, ¿qué perfil de sabor te gusta más: TRADICIONAL (chocolate, nueces), EXÓTICO (frutas, flores) o FUNKY (fermentado, intenso)?"
    return "¿Qué perfil de sabor te gusta más: TRADICIONAL, EXÓTICO o FUNKY?"

def explicar_perfiles() -> str:
    return """
        **Perfiles de café:**
        - **TRADICIONAL**: Sabores clásicos como chocolate, nueces y caramelo. Acidez suave.
        - **EXÓTICO**: Sabores frutales como fresa, mango, mora. Acidez brillante.
        - **FUNKY**: Sabores fermentados, licorosos, frutas maduras. Intenso y complejo.
        """


    return "No entendí tu consulta. ¿Te gustaría que te ayude a elegir un café?"

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

def clasificar_intencion(mensaje: str) -> str:
    """
    Clasifica la intención del usuario.
    Retorna: 'compra', 'descripcion', 'info_general' o 'otro'
    """
    user_lower = normalizar_texto(mensaje)
    
    # Intenciones que usan IA
    if any(phrase in user_lower for phrase in [
        "describeme", "describime","qué notas tiene", "contame sobre", "que significa",
        "de dónde es", "origen", "diferencia entre", "cuéntame más",
        "explicame","explicarme" "como se prepara","que perfil"
    ]):
        return "ia_descripcion"
    
    if any(word in user_lower for word in ["hola", "buenos dias", "buenas tardes"]):
        return "simple_saludo"
    if "gracias" in user_lower or "graciass" in user_lower:
        return "simple_saludo"
    if any(word in user_lower for word in ["adios", "chao", "hasta luego", "nos vemos", "bye"]):
        return "simple_saludo"
    
    frases_recordatorio = [
        "que metodo", "que perfil", "que elegi", "como tomo el cafe",
        "que me recomendaste", "cual fue mi eleccion", "que habia elegido"
    ]
    if any(phrase in user_lower for phrase in frases_recordatorio):
        return "pregunta_recordatorio"
    
    # Intenciones que usan lógica dura
    if any(phrase in user_lower for phrase in [
        "quiero comprar", "quiero un cafe", "recomienda", "cafe por favor"
    ]):
        return "logica_compra"
    
    if any(word in user_lower for word in ["espresso", "filtro", "tradicional", "exotico", "funky"]):
        return "logica_compra"
    
    return "logica_compra"  # por defecto