def recomendar_cafe(metodo: str, perfil: str) -> str:
    matriz = {
        ("espresso", "tradicional"): ["Alacrán", "Cóndor", "Lince", "Yurumi"],
        ("espresso", "exotico"): ["Dimeti", "Delfín Rosado", "Puma"],
        ("espresso", "funky"): ["Coyote"],
        ("filtro", "tradicional"): [],
        ("filtro", "exotico"): ["Correcaminos", "Nebiri"],
        ("filtro", "funky"): [],
    }
    cafes = matriz.get((metodo, perfil), [])
    if not cafes:
        return f"No tenemos cafés {perfil} para {metodo}. ¿Te gustaría probar otro perfil?"
    if len(cafes) == 1:
        return f"Para {metodo} y perfil {perfil}, te recomiendo {cafes[0]}. ¡Es una excelente elección!"
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

def manejar_saludo() -> str:
    return "¡Hola! Soy tu asistente experto en café. ¿En qué puedo ayudarte hoy?"

def manejar_despedida() -> str:
    return "¡Gracias por consultarnos! Vuelve cuando quieras más café ☕"

def respuesta_generica() -> str:
    return "No entendí tu consulta. ¿Te gustaría que te ayude a elegir un café?"