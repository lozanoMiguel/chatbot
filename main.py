from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from openai import OpenAI
import asyncpg
import os
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
import aiosqlite
from contextlib import asynccontextmanager

# ==================== BASE DE DATOS ====================
DATABASE_PATH = "chat_history.db"
DATABASE_URL = os.getenv("DATABASE_URL")

async def init_db():
    """Crea la tabla si no existe en Supabase"""
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id SERIAL PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON conversations(session_id)")
    await conn.close()
    print("✅ Base de datos PostgreSQL inicializada")

async def save_message(session_id: str, role: str, content: str):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(
        "INSERT INTO conversations (session_id, role, content) VALUES ($1, $2, $3)",
        session_id, role, content
    )
    await conn.close()

async def get_conversation_history(session_id: str, limit: int = 10):
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch(
        "SELECT role, content FROM conversations WHERE session_id = $1 ORDER BY created_at ASC LIMIT $2",
        session_id, limit
    )
    await conn.close()
    return [{"role": row["role"], "content": row["content"]} for row in rows]

# ==================== LIFESPAN ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicio
    await init_db()
    print("✅ Base de datos inicializada")
    yield
    # Cierre
    print("🛑 Cerrando conexiones...")

# ==================== CONFIGURACIÓN ====================
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

embeddings = OpenAIEmbeddings()
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)

# ==================== APP ====================
app = FastAPI(
    title="Cafetería Tostadora - Asistente",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== MODELOS ====================
class Pregunta(BaseModel):
    mensaje: str
    session_id: str

class Respuesta(BaseModel):
    respuesta: str
    
class ChatRequest(BaseModel):
    message: str

# ==================== FUNCIONES RAG ====================
def buscar_contexto(pregunta: str) -> str:
    docs = vectorstore.similarity_search(pregunta, k=10)
    contexto = "\n\n".join([doc.page_content for doc in docs])
    return contexto

# ==================== ENDPOINTS ====================
@app.post("/preguntar", response_model=Respuesta)
async def preguntar(pregunta: Pregunta):
    try:
        session_id = pregunta.session_id
        user_message = pregunta.mensaje

        # Guardar mensaje del usuario
        await save_message(session_id, "user", user_message)

        # Obtener contexto RAG
        contexto = buscar_contexto(user_message)

        # Obtener historial reciente
        historial = await get_conversation_history(session_id, limit=10)

        # Construir system prompt con contexto
        system_prompt = f"""
            Eres un experto en café de especialidad con más de 10 años de experiencia. Tu misión es asesorar a los clientes para que compren el café perfecto según sus necesidades.

            INFORMACIÓN REAL DE LA CAFETERÍA (contexto RAG):
            {contexto}

            REGLAS ESTRICTAS DE COMPORTAMIENTO:

            1  . **Solo usa la información del contexto**. Nunca inventes nombres de cafés, notas, precios o atributos. Si no aparece en el contexto, di: "No tengo información sobre eso. ¿Podrías consultar directamente en nuestra tienda?"

            2. **Flujo de recomendación (por orden, una pregunta cada vez)**:
            - Primero, pregunta: "¿Cómo tomas el café, en máquina de espresso o en filtro?"
            - Según la respuesta, lista SOLO los cafés que coincidan con ese tostado (expresso o filtro) que aparecen en el contexto.
            - Luego pregunta por el perfil deseado: tradicional, exótico o funky. Si el usuario no sabe, explica brevemente cada uno.
            - Finalmente, recomienda 1 o 2 cafés que cumplan los criterios.

            3. **Si el usuario es nuevo o no sabe qué quiere**, guíalo paso a paso con las preguntas anteriores. Sé paciente y cercano.

            4. **Si solo hay dos opciones para un tostado** (ej. para filtro solo Correcaminos y Nebiri), recomienda directamente esos dos, explicando el perfil de cada uno (tradicional, exótico, notas, etc.) usando la información del contexto.

            5. **Combina brevedad y profundidad**: responde con claridad, pero da detalles suficientes (notas, cuerpo, acidez) para que el cliente se sienta bien asesorado.

            6. **Estilo cercano y ameno**, como un barista experto que habla con un amigo. Usa emojis de café ☕, taza 🍵, fuego 🔥 con moderación.

            7. **No asumas roles ni des información no solicitada**. Si el usuario pregunta algo fuera del café (clima, política, etc.), responde amablemente: "Solo puedo ayudarte con temas de café. ¿Te gustaría que te recomiende algún café?"

            8. **Recuerda la conversación** (el historial ya se incluye en los mensajes). No repitas preguntas que ya has hecho.

            FORMATO DE RESPUESTA (cuando recomiendes):
            "☕ Para [método] y perfil [perfil], te recomiendo [NOMBRE]. Es un café [PERFIL] con notas de [NOTAS]. Tiene [ACIDEZ] y cuerpo [CUERPO]. [Si es filtro o expresso]. ¡[FRASE DE CIERRE PERSONALIZADA]!"

            Si hay más de una opción, menciónalas ordenadas por puntuación SCA (mayor primero).
            """

        # Construir mensajes para OpenAI
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(historial)
        messages.append({"role": "user", "content": user_message})

        # Llamar a OpenAI
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",  # o "gpt-4o-mini" si quieres
            messages=messages,
            max_tokens=600,
            temperature=0.5
        )

        respuesta_texto = completion.choices[0].message.content

        # Guardar respuesta
        await save_message(session_id, "assistant", respuesta_texto)

        return Respuesta(respuesta=respuesta_texto)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/", response_class=HTMLResponse)
async def get_chat():
    return """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Asistente de Café ☕</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .chat-container {
            width: 90%;
            max-width: 800px;
            height: 80vh;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .chat-header {
            background: #6f4e37;
            color: white;
            padding: 20px;
            text-align: center;
        }
        .chat-header h1 { font-size: 1.5em; margin-bottom: 5px; }
        .chat-header p { font-size: 0.9em; opacity: 0.9; }
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .message {
            margin-bottom: 15px;
            display: flex;
            align-items: flex-start;
        }
        .message.user { justify-content: flex-end; }
        .message-content {
            max-width: 70%;
            padding: 10px 15px;
            border-radius: 18px;
            position: relative;
        }
        .user .message-content {
            background: #667eea;
            color: white;
            border-bottom-right-radius: 4px;
        }
        .assistant .message-content {
            background: white;
            color: #333;
            border: 1px solid #ddd;
            border-bottom-left-radius: 4px;
        }
        .typing-indicator {
            display: none;
            padding: 10px 15px;
            background: white;
            border-radius: 18px;
            border: 1px solid #ddd;
            width: fit-content;
        }
        .typing-indicator span {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #999;
            margin: 0 2px;
            animation: typing 1.4s infinite;
        }
        .typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
        .typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes typing {
            0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
            30% { transform: translateY(-10px); opacity: 1; }
        }
        .chat-input-container {
            padding: 20px;
            background: white;
            border-top: 1px solid #ddd;
            display: flex;
            gap: 10px;
        }
        .chat-input {
            flex: 1;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 25px;
            font-size: 1em;
            outline: none;
            transition: border-color 0.3s;
        }
        .chat-input:focus { border-color: #667eea; }
        .send-button {
            padding: 12px 24px;
            background: #6f4e37;
            color: white;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            font-size: 1em;
            transition: background 0.3s;
        }
        .send-button:hover { background: #5a3d2b; }
        .send-button:disabled { background: #ccc; cursor: not-allowed; }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            <h1>☕ Asistente de Café</h1>
            <p>Tu experto barista personal - Pregúntame lo que quieras sobre café</p>
        </div>
        <div class="chat-messages" id="chatMessages">
            <div class="message assistant">
                <div class="message-content">
                    ¡Hola! Soy tu asistente experto en café. ¿En qué puedo ayudarte hoy?
                </div>
            </div>
        </div>
        <div class="chat-input-container">
            <input type="text" class="chat-input" id="messageInput" placeholder="Escribe tu pregunta sobre café..." onkeypress="handleKeyPress(event)">
            <button class="send-button" id="sendButton" onclick="sendMessage()">Enviar</button>
        </div>
    </div>
    <script>
        const chatMessages = document.getElementById('chatMessages');
        const messageInput = document.getElementById('messageInput');
        const sendButton = document.getElementById('sendButton');
        
        let sessionId = localStorage.getItem('chat_session_id');
        if (!sessionId) {
            sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36);
            localStorage.setItem('chat_session_id', sessionId);
        }
        
        function handleKeyPress(event) { if (event.key === 'Enter') sendMessage(); }
        
        function addMessage(content, isUser) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${isUser ? 'user' : 'assistant'}`;
            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            contentDiv.innerHTML = content.replace(/\\n/g, '<br>');
            messageDiv.appendChild(contentDiv);
            chatMessages.appendChild(messageDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
        
        function showTypingIndicator() {
            const typingDiv = document.createElement('div');
            typingDiv.className = 'message assistant';
            typingDiv.id = 'typingIndicator';
            const indicatorDiv = document.createElement('div');
            indicatorDiv.className = 'typing-indicator';
            indicatorDiv.innerHTML = '<span></span><span></span><span></span>';
            indicatorDiv.style.display = 'block';
            typingDiv.appendChild(indicatorDiv);
            chatMessages.appendChild(typingDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
        
        function removeTypingIndicator() {
            const indicator = document.getElementById('typingIndicator');
            if (indicator) indicator.remove();
        }
        
        async function sendMessage() {
            const message = messageInput.value.trim();
            if (!message) return;
            messageInput.disabled = true;
            sendButton.disabled = true;
            addMessage(message, true);
            messageInput.value = '';
            showTypingIndicator();
            try {
                const response = await fetch('/preguntar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        mensaje: message,
                        session_id: sessionId
                    })
                });
                removeTypingIndicator();
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || 'Error en el servidor');
                }
                const data = await response.json();
                addMessage(data.respuesta, false);
            } catch (error) {
                removeTypingIndicator();
                addMessage(`❌ Error: ${error.message}`, false);
                console.error('Error:', error);
            } finally {
                messageInput.disabled = false;
                sendButton.disabled = false;
                messageInput.focus();
            }
        }
    </script>
</body>
</html>"""

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    # 1. Obtener el mensaje del usuario
    user_message = request.message

    # 2. ¡Aquí usamos la lógica que ya tienes!
    #    Obtenemos el contexto relevante y generamos la respuesta.
    contexto = buscar_contexto(user_message)
    # ... (aquí iría toda la lógica para construir el prompt y llamar a OpenAI)
    # ... (debes integrar el código de tu función 'preguntar' aquí)

    # 3. Por ahora, para probar, devolveremos un mensaje simple.
    #    Luego lo reemplazarás con la respuesta real de tu bot.
    respuesta_del_bot = f"Recibí tu mensaje: '{user_message}'. ¡Pronto te daré una recomendación de café!"

    # 4. Devolver la respuesta en el formato que espera la API
    return {"response": respuesta_del_bot}