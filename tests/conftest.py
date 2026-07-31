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


@pytest.fixture(autouse=True)
def mock_openai():
    """Mock de OpenAI que se aplica automáticamente a todos los tests."""
    import app.functions
    import app.routes.chat

    with patch.object(app.functions,"get_openai_client") as mock_get_client:
        mock_openai_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="Respuesta de prueba del chatbot."))
        ]
        mock_openai_instance.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_openai_instance

        # También parchear en main
        with patch.object(app.functions,"get_openai_client") as mock_main_get_client:
            mock_main_get_client.return_value = mock_openai_instance
            yield mock_get_client


@pytest.fixture
def mock_rag():
    """Mock de la búsqueda en ChromaDB."""
    from app.rag import get_vectorstore

    with patch("app.rag.get_vectorstore") as mock:
        mock_vectorstore = MagicMock()
        mock_vectorstore.similarity_search.return_value = [
            MagicMock(
                page_content="Documento de prueba 1: notas de chocolate y almendra",
                metadata={"source": "test"},
            ),
            MagicMock(
                page_content="Documento de prueba 2: notas de caramelo y frutos amarillos",
                metadata={"source": "test"},
            ),
        ]
        mock.return_value = mock_vectorstore
        yield mock


@pytest.fixture
def mock_db():
    """Mock de save_message en app.main (el lugar donde se usa)."""
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
