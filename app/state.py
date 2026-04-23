"""
Módulo de gestión de estado de la conversación (memoria artificial)
Mantiene el método (espresso/filtro) y perfil (tradicional/exótico/funky) 
que el usuario ha elegido durante la conversación.
"""

from collections import defaultdict

# Almacenamiento del estado de cada conversación
# estructura: {session_id: {"metodo": str, "perfil": str}}
estado_usuario = defaultdict(lambda: {"metodo": None, "perfil": None})

# Palabras clave para detectar nueva solicitud de compra
PALABRAS_NUEVA_COMPRA = [
    "quiero comprar", "quiero un cafe", "busco un cafe", 
    "recomienda", "hola quiero", "cafe por favor", 
    "necesito un cafe", "me recomiendas", "cual cafe",
    "quiero cafe", "comprar cafe"
]

# Palabras clave para detectar método
PALABRAS_METODO = {
    "espresso": ["espresso", "espreso", "expreso", "maquina"],
    "filtro": ["filtro", "filter", "v60", "chemex", "prensa", "aeropress"]
}

# Palabras clave para detectar perfil
PALABRAS_PERFIL = {
    "tradicional": ["tradicional", "clasico", "normal", "achocolatado"],
    "exotico": ["exotico", "afrutado", "frutal", "floral", "citrico"],
    "funky": ["funky", "fermentado", "licoroso", "atrevido"]
}


def es_nueva_solicitud_compra(mensaje: str) -> bool:
    """
    Detecta si el mensaje del usuario indica una nueva intención de compra.
    
    Args:
        mensaje: El mensaje del usuario en minúsculas
        
    Returns:
        True si el usuario quiere comprar un café, False en caso contrario
    """
    mensaje_lower = mensaje.lower()
    return any(phrase in mensaje_lower for phrase in PALABRAS_NUEVA_COMPRA)


def detectar_metodo(mensaje: str) -> str | None:
    """
    Detecta el método de preparación en el mensaje del usuario.
    
    Args:
        mensaje: El mensaje del usuario en minúsculas
        
    Returns:
        'espresso', 'filtro' o None si no se detecta
    """
    mensaje_lower = mensaje.lower()
    for metodo, palabras in PALABRAS_METODO.items():
        if any(palabra in mensaje_lower for palabra in palabras):
            return metodo
    return None


def detectar_perfil(mensaje: str) -> str | None:
    """
    Detecta el perfil de sabor en el mensaje del usuario.
    
    Args:
        mensaje: El mensaje del usuario en minúsculas
        
    Returns:
        'tradicional', 'exotico', 'funky' o None si no se detecta
    """
    mensaje_lower = mensaje.lower()
    for perfil, palabras in PALABRAS_PERFIL.items():
        if any(palabra in mensaje_lower for palabra in palabras):
            return perfil
    return None


def actualizar_estado(session_id: str, mensaje: str) -> dict:
    """
    Actualiza el estado de la conversación basado en el mensaje del usuario.
    
    Reglas:
    1. Si el usuario inicia una NUEVA solicitud de compra, resetea el estado.
    2. Si detecta método, lo actualiza.
    3. Si detecta perfil, lo actualiza.
    
    Args:
        session_id: Identificador único de la sesión/conversación
        mensaje: El mensaje del usuario
        
    Returns:
        El estado actualizado (diccionario con 'metodo' y 'perfil')
    """
    mensaje_lower = mensaje.lower()
    estado_anterior = estado_usuario[session_id].copy()
    
    # ========== REGLA 1: Resetear en nueva solicitud de compra ==========
    if es_nueva_solicitud_compra(mensaje_lower):
        # Solo resetear si ya había información previa
        if estado_anterior["metodo"] or estado_anterior["perfil"]:
            estado_usuario[session_id] = {"metodo": None, "perfil": None}
            print(f"🔄 Estado reseteado para sesión {session_id[:20]}... (nueva compra)")
    
    # ========== REGLA 2: Detectar método ==========
    metodo_detectado = detectar_metodo(mensaje_lower)
    if metodo_detectado:
        estado_usuario[session_id]["metodo"] = metodo_detectado
        print(f"📌 Método detectado: {metodo_detectado}")
    
    # ========== REGLA 3: Detectar perfil ==========
    perfil_detectado = detectar_perfil(mensaje_lower)
    if perfil_detectado:
        estado_usuario[session_id]["perfil"] = perfil_detectado
        print(f"📌 Perfil detectado: {perfil_detectado}")
    
    estado_nuevo = estado_usuario[session_id]
    
    # Log de cambios
    if estado_anterior != estado_nuevo:
        print(f"📊 Estado actualizado: método={estado_nuevo['metodo']}, perfil={estado_nuevo['perfil']}")
    
    return estado_nuevo


def obtener_estado(session_id: str) -> dict:
    """
    Obtiene el estado actual de una conversación.
    
    Args:
        session_id: Identificador único de la sesión/conversación
        
    Returns:
        Diccionario con 'metodo' y 'perfil'
    """
    return estado_usuario[session_id]


def resetear_estado(session_id: str) -> None:
    """
    Resetea manualmente el estado de una conversación.
    Útil para iniciar una conversación completamente nueva.
    
    Args:
        session_id: Identificador único de la sesión/conversación
    """
    estado_usuario[session_id] = {"metodo": None, "perfil": None}
    print(f"🦜 Estado manualmente reseteado para sesión {session_id[:20]}...")


def tiene_estado_completo(session_id: str) -> bool:
    """
    Verifica si el usuario ya ha elegido tanto método como perfil.
    
    Args:
        session_id: Identificador único de la sesión/conversación
        
    Returns:
        True si tiene método y perfil, False en caso contrario
    """
    estado = estado_usuario[session_id]
    return estado["metodo"] is not None and estado["perfil"] is not None