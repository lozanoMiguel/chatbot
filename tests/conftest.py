"""
conftest.py — Fixtures compartidas para todos los tests.
 
pytest las carga automáticamente. Aquí centralizamos:
- El cliente de test de FastAPI
- Los mocks de OpenAI, RAG y Supabase
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
 
 
# ===========================================================
# IMPORTANTE: Ajusta este import al path real de tu app
# Ejemplos comunes:
#   from app.main import app
#   from src.main import app
#   from main import app
# ===========================================================

from app.main import app  
 
 
@pytest.fixture
def app_instance():
    """
    Retorna la instancia de FastAPI.
    Descomenta el import de arriba y elimina el raise.
    """
    # return app
    raise NotImplementedError(
        "Ajusta el import de 'app' en conftest.py al path real de tu proyecto"
    )
 
 
@pytest.fixture
def client(app_instance):
    """Cliente HTTP de test para FastAPI (no levanta servidor real)."""
    return TestClient(app_instance)
 
 
@pytest.fixture
def mock_openai():
    """
    Mock de la llamada a OpenAI GPT-4o-mini.
    Evita costos y dependencia de red en CI.
 
    Ajusta el path según cómo importas OpenAI en tu código.
    Ejemplos:
      'app.services.llm.openai.ChatCompletion.create'
      'openai.chat.completions.create'
    """
    with patch("openai.chat.completions.create") as mock:
        mock.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(content="Respuesta de prueba del chatbot.")
                )
            ]
        )
        yield mock
 
 
@pytest.fixture
def mock_rag():
    """
    Mock del retriever vectorial (Supabase pgvector / FAISS / etc).
    Devuelve documentos de prueba sin consultar la DB vectorial.
 
    Ajusta el path al módulo donde inicializas tu retriever.
    """
    with patch("app.rag.retriever.get_relevant_documents") as mock:
        mock.return_value = [
            MagicMock(page_content="Contexto relevante de prueba número 1."),
            MagicMock(page_content="Contexto relevante de prueba número 2."),
        ]
        yield mock
 
 
@pytest.fixture
def mock_db():
    """
    Mock de la operación de guardado en Supabase/PostgreSQL.
    Ajusta el path a tu función de persistencia.
    """
    with patch("app.database.save_conversation") as mock:
        mock.return_value = {"id": "test-uuid-123", "status": "saved"}
        yield mock
 
 
@pytest.fixture
def mock_db_error():
    """
    Simula un fallo de conexión a la base de datos.
    Usado para testear que el health check devuelve 503.
    """
    with patch("app.database.check_connection") as mock:
        mock.side_effect = Exception("Connection refused")
        yield mock

        
 