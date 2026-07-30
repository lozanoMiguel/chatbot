from pydantic import BaseModel
from typing import Literal

class ClasificacionSchema(BaseModel):
    intencion: Literal["compra", "descripcion_cafe", "descripcion_faq", "recordatorio", "saludo"]