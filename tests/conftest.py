import sys
import os
import uuid
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from fastapi.testclient import TestClient
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

def chat_request(client, mensaje, session_id=None):
    if session_id is None:
        session_id = f"test_{uuid.uuid4().hex[:8]}"
    
    payload = {
        "mensaje": mensaje,
        "session_id": session_id
    }
    return client.post("/preguntar", json=payload)


@pytest.fixture
def mock_openai():
    """Mock de OpenAI para que no haga llamadas reales."""
    with patch("app.main.client.chat.completions.create") as mock:
        # Simular una respuesta de OpenAI
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="Respuesta de prueba del chatbot."))
        ]
        mock.return_value = mock_response
        yield mock


@pytest.fixture
def mock_rag():
    """Mock de ChromaDB para devolver documentos de prueba."""
    with patch("app.rag.vectorstore.similarity_search") as mock:
        # Crear documentos de prueba
        doc1 = MagicMock()
        doc1.page_content = "Documento de prueba 1: notas de chocolate y almendra"
        doc1.metadata = {"source": "test"}
        
        doc2 = MagicMock()
        doc2.page_content = "Documento de prueba 2: notas de caramelo y frutos amarillos"
        doc2.metadata = {"source": "test"}
        
        # Devolver una lista de documentos
        mock.return_value = [doc1, doc2]
        yield mock


@pytest.fixture
def mock_db():
    """Mock de save_message en app.main (el lugar donde se usa)."""
    import app.main
    with patch.object(app.main, "save_message") as mock:
        mock.return_value = None
        yield mock

@pytest.fixture
def mock_db_error():
    """Simula un fallo de conexión a la base de datos."""
    with patch("asyncpg.connect") as mock:
        mock.side_effect = Exception("Connection refused")
        yield mock