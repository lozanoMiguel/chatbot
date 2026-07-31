from fastapi import APIRouter

from app.state import estado_usuario

router = APIRouter()


@router.get("/debug/estado/{session_id}")
async def debug_estado(session_id: str):
    """Ver el estado actual de una sesión (útil para depurar)"""
    estado = estado_usuario.get(
        session_id, {"metodo": None, "perfil": None, "ultimos_cafes": []}
    )
    return {
        "session_id": session_id,
        "metodo": estado["metodo"],
        "perfil": estado["perfil"],
        "ultimos_cafes": estado["ultimos_cafes"],
    }
