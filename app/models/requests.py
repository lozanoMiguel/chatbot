from pydantic import BaseModel


class Request(BaseModel):
    mensaje: str
    session_id: str


class ChatRequest(BaseModel):
    mensaje: str
