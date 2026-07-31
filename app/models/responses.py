from pydantic import BaseModel


class Response(BaseModel):
    respuesta: str


class ChatResponse(BaseModel):
    respuesta: str
