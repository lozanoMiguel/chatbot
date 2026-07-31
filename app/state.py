from collections import defaultdict

# Estado de conversación
estado_usuario = defaultdict(
    lambda: {"metodo": None, "perfil": None, "ultimos_cafes": []}
)
