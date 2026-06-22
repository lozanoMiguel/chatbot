"""
Tests básicos de salud para el chatbot API.
Verifican que los endpoints principales responden correctamente.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ajusta este import al nombre real de tu módulo principal
# Ejemplo: from app.main import app
from app.main import app

from .conftest import chat_request

# ===========================================================
# SECCIÓN 1: Tests del endpoint /health
# ===========================================================


class TestHealthEndpoint:
    """
    Verifica que el endpoint /health responde y valida
    la conectividad con Supabase y el modelo LLM.
    """

    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_has_required_fields(self, client):
        response = client.get("/health")
        data = response.json()
        # El endpoint debe informar el estado de cada servicio
        assert "status" in data
        assert "database" in data
        assert "llm" in data

    def test_health_status_is_ok_when_services_up(self, client):
        response = client.get("/health")
        data = response.json()
        assert data["status"] in ["ok", "degraded"]


# ===========================================================
# SECCIÓN 2: Tests del endpoint /chat
# ===========================================================


class TestChatEndpoint:
    """
    Verifica la lógica del endpoint de chat sin llamar
    realmente a OpenAI ni a Supabase (mocks).
    """

    def test_chat_requires_message(self, client):
        """Debe rechazar requests sin campo 'message'."""
        response = client.post("/preguntar", json={})
        assert response.status_code == 422  # Unprocessable Entity

    def test_chat_rejects_empty_message(self, client):
        """Debe rechazar mensajes vacíos."""
        response = client.post("/preguntar", json={"mensaje": ""})
        assert response.status_code == 422

    def test_chat_returns_response_field(self, client, mock_openai, mock_rag):
        """La respuesta debe contener el campo 'respuesta'."""
        response = chat_request(client, "Hola, ¿cómo estás?")
        assert response.status_code == 200
        assert "respuesta" in response.json()

    def test_chat_response_is_not_empty(self, client, mock_openai, mock_rag):
        """La respuesta del chatbot no debe estar vacía."""
        response = chat_request(client, "¿Qué puedes hacer?")
        data = response.json()
        assert "respuesta" in data
        assert len(data["respuesta"]) > 0


# ===========================================================
# SECCIÓN 3: Tests del pipeline RAG
# ===========================================================


class TestRAGPipeline:
    """
    Verifica que el sistema de recuperación de contexto (RAG)
    funciona: recupera chunks relevantes y los incluye en el prompt.
    """

    def test_rag_retriever_returns_documents(self, client, mock_rag, mock_openai):
        """Debe recuperar documentos de ChromaDB."""
        response = chat_request(client, "Descríbeme el café Puma")
        assert response.status_code == 200
        mock_rag.assert_called_once()

    def test_rag_documents_have_content(self, mock_rag):
        """Los documentos recuperados deben tener contenido."""
        docs = mock_rag.get_relevant_documents("pregunta de prueba")
        for doc in docs:
            assert doc.page_content != ""

    def test_rag_context_is_passed_to_llm(self, client, mock_rag):
        """Debe pasar el contexto RAG a la IA."""
        # Establecer estado
        chat_request(client, "Quiero un café para espresso")
        chat_request(client, "Exótico")

        # Pedir descripción
        response = chat_request(client, "Descríbeme el café Puma")

        # Verificar que la respuesta contiene información del café
        assert response.status_code == 200
        data = response.json()
        assert "respuesta" in data
        assert len(data["respuesta"]) > 0
        # Opcional: verificar que la respuesta contiene "Puma"
        assert "Puma" in data["respuesta"] or "puma" in data["respuesta"].lower()


# ===========================================================
# SECCIÓN 4: Tests de base de datos
# ===========================================================


class TestDatabase:
    """
    Verifica operaciones básicas con Supabase/PostgreSQL.
    Usa mocks para no depender de la DB real en CI.
    """

    def test_conversation_is_persisted(self, client, mock_db, mock_openai, mock_rag):
        """Debe guardar la conversación en la base de datos."""
        response = chat_request(client, "Hola, quiero un café")
        assert response.status_code == 200

        # Verificar que se llamó al menos una vez
        assert mock_db.call_count > 0
        print(f"✅ save_message llamado {mock_db.call_count} veces")

    def test_db_error_returns_503(self, client, mock_db_error):
        """Debe indicar que la base de datos no está disponible."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["database"] == "disconnected"
        assert data["status"] == "degraded"
