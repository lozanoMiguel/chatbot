tools = [
    {
        "type": "function",
        "function": {
            "name": "recomendar_cafe",
            "description": "Recomienda un café específico basado en el método y perfil",
            "parameters": {
                "type": "object",
                "properties": {
                    "metodo": {"type": "string", "enum": ["espresso", "filtro"]},
                    "perfil": {"type": "string", "enum": ["tradicional", "exotico", "funky"]}
                },
                "required": ["metodo", "perfil"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "preguntar_metodo",
            "description": "Pregunta al usuario cómo toma su café",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "preguntar_perfil",
            "description": "Pregunta al usuario qué perfil de sabor prefiere",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "explicar_perfiles",
            "description": "Explica los perfiles de café",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manejar_saludo",
            "description": "Responde a un saludo del usuario",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manejar_despedida",
            "description": "Responde a una despedida del usuario",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "respuesta_generica",
            "description": "Respuesta para consultas no clasificadas",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    }
]