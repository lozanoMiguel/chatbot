from typing import Literal

from pydantic import BaseModel


class ClasificacionSchema(BaseModel):
    intencion: Literal[
        "compra", "descripcion_cafe", "descripcion_faq", "recordatorio", "saludo"
    ]
