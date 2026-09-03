from pydantic import BaseModel
from typing import Optional

class PreferenciasUsuario(BaseModel):
    metodo: Optional[str] = None
    ultimos_cafes: list[str] = []
    candidatos_actuales: list[str] = []
    afinando: Optional[dict] = None
    

    def actualizar(self, **cambios):
        """Solo pisa los campos que vienen con valor, preserva el resto."""
        for clave, valor in cambios.items():
            if valor is not None:
                setattr(self, clave, valor)


from collections import defaultdict
estado_usuario: dict[str, PreferenciasUsuario] = defaultdict(PreferenciasUsuario)