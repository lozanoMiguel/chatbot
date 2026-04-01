"""
Aplicación principal con FastAPI
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Crear instancia de FastAPI
app = FastAPI(
    title="Mi Proyecto con FastAPI",
    description="API construida con FastAPI, Uvicorn y OpenAI",
    version="0.1.0"
)

@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "message": "Bienvenido a mi API",
        "status": "online",
        "version": "0.1.0"
    }

@app.get("/health")
async def health():
    """Health check para verificar que el servicio está funcionando"""
    return {
        "status": "Healthy",
        "python_version": "3.11",
        "framework": "FastAPI"
    }

@app.get("/info")
async def info():
    """Información del proyecto"""
    return {
        "name": "Proyecto FastAPI",
        "dependencies": {
            "fastapi": "latest",
            "uvicorn": "latest",
            "openai": "latest"
        },
        "environment": {
            "openai_key_configured": bool(os.getenv("OPENAI_API_KEY"))
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=port, reload=True)
