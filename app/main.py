from contextlib import asynccontextmanager # Permite definir el ciclo de vida de la aplicación FastAPI
from fastapi import FastAPI, HTTPException #FastAPI crea la aplicación web; HTTPException permite devolver errores HTTP (ej. 404, 500) de forma controlada
from fastapi.middleware.cors import CORSMiddleware #Permite que el frontend (HTML/JS) en cualquier dominio/puerto pueda llamar a la API (evita errores CORS)
from fastapi.responses import HTMLResponse #Indica que el endpoint / devuelve contenido HTML en lugar de JSON
from fastapi.staticfiles import StaticFiles
from app.database import init_db
from app.routes import chat_router, health_router, debug_router


# ==================== LIFESPAN ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    print("🛑 Servidor detenido")


# ==================== APP ====================
app = FastAPI(title="CafBot - Asistente de Café", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
# le decimos a fastapi que toda todo archivo que se sirva de esta carpeta sera estatico
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(chat_router)
app.include_router(health_router)
app.include_router(debug_router)

# ==================== HTML ====================
@app.get("/", response_class=HTMLResponse)
async def get_chat():
    with open("app/templates/index.html", "r", encoding="utf-8") as f:
        return f.read()
