# ☕ CafBot - Asistente de Café con IA

Asistente virtual especializado en recomendación de cafés de especialidad, con memoria conversacional y sistema RAG (Retrieval-Augmented Generation).

## Características
- 🧠 Memoria persistente (SQLite)
- 🔍 Búsqueda semántica de cafés (RAG con Chroma)
- 💬 Interfaz web moderna
- 📊 Base de conocimiento de 10 cafés con perfiles Tradicional, Exótico y Funky

## Tecnologías
- FastAPI (backend)
- OpenAI GPT-3.5-turbo
- LangChain (RAG)
- Chroma (vector database)
- SQLite + aiosqlite (memoria conversacional)
- HTML/CSS/JS (frontend)

## Cómo ejecutar
```bash
git clone https://github.com/tu-usuario/chatbot-cafe
cd chatbot-cafe
python -m venv venv
source venv/bin/activate  # o .\venv\Scripts\activate en Windows
pip install -r requirements.txt
python indexar_documentos.py  # crear índice RAG
uvicorn main:app --reload