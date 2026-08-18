import os
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db
from app.main import app


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    """Inicializa la base de datos antes de los tests."""
    await init_db()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def chat_request(client, mensaje, session_id=None):
    if session_id is None:
        session_id = f"test_{uuid.uuid4().hex[:8]}"
    payload = {"mensaje": mensaje, "session_id": session_id}
    return client.post("/preguntar", json=payload)


@pytest.fixture
def mock_openai():
    """Mock de OpenAI."""
    import app.functions
    import app.routes.chat

    with patch.object(app.functions, "get_openai_client") as mock1, \
         patch.object(app.routes.chat, "get_openai_client") as mock2:
        mock_openai_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="Respuesta de prueba del chatbot."))
        ]
        mock_openai_instance.chat.completions.create.return_value = mock_response
        mock1.return_value = mock_openai_instance
        mock2.return_value = mock_openai_instance
        yield mock1


@pytest.fixture
def mock_rag():
    """Mock de la búsqueda en ChromaDB."""
    import app.routes.chat

    with patch.object(app.routes.chat, "buscar_contexto") as mock:
        mock.return_value = """
        Documento de prueba 1: notas de chocolate y almendra
        Documento de prueba 2: notas de caramelo y frutos amarillos
        """
        yield mock


@pytest.fixture
def mock_db():
    """Mock de save_message."""
    import app.routes.chat
    with patch.object(app.routes.chat, "save_message") as mock:
        mock.return_value = None
        yield mock


@pytest.fixture
def mock_db_error():
    """Simula un fallo de conexión a la base de datos."""
    with patch("asyncpg.connect") as mock:
        mock.side_effect = Exception("Connection refused")
        yield mock
