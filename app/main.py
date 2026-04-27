"""
Chatbot de café - Main
Flujo controlado por lógica dura en Python, no por IA.
"""

from contextlib import asynccontextmanager
from collections import defaultdict
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from openai import OpenAI

from app.config import OPENAI_API_KEY
from app.database import init_db, save_message, get_conversation_history
from app.rag import buscar_contexto
from app.functions import clasificar_intencion, recomendar_cafe  # normalizar_texto está dentro de functions

# Cliente OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# ==================== ESTADO DE CONVERSACIÓN ====================
# Ahora guarda también la lista de últimos cafés recomendados
estado_usuario = defaultdict(lambda: {"metodo": None, "perfil": None, "ultimos_cafes": []})


# ==================== LIFESPAN ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print("✅ Base de datos inicializada")
    yield
    print("🛑 Servidor detenido")

# ==================== APP ====================
app = FastAPI(title="CafBot - Asistente de Café", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# ==================== MODELOS ====================
class Pregunta(BaseModel):
    mensaje: str
    session_id: str

class Respuesta(BaseModel):
    respuesta: str

# ==================== ENDPOINT PRINCIPAL ====================
@app.post("/preguntar", response_model=Respuesta)
async def preguntar(pregunta: Pregunta):
    session_id = pregunta.session_id
    user_message = pregunta.mensaje
    
    print(f"\n📨 [{session_id[:8]}] Usuario: {user_message}")
    
    try:
        await save_message(session_id, "user", user_message)
        
        user_lower = user_message.lower()
        
        # ========== ACTUALIZAR ESTADO ==========
        if "espresso" in user_lower or "espreso" in user_lower:
            estado_usuario[session_id]["metodo"] = "espresso"
        elif "filtro" in user_lower:
            estado_usuario[session_id]["metodo"] = "filtro"
        
        if "tradicional" in user_lower:
            estado_usuario[session_id]["perfil"] = "tradicional"
        elif "exotico" in user_lower or "afrutado" in user_lower:
            estado_usuario[session_id]["perfil"] = "exotico"
        elif "funky" in user_lower:
            estado_usuario[session_id]["perfil"] = "funky"
        
        estado = estado_usuario[session_id]
        print(f"   📊 Estado: método={estado['metodo']}, perfil={estado['perfil']}, ultimos_cafes={estado['ultimos_cafes']}")
        
        intencion = clasificar_intencion(user_lower)
        print(f"   🧠 Intención: {intencion}")
        
        # ========== RUTA 1: IA para descripciones ==========
        if intencion == "ia_descripcion":
            print(f"   🤖 Usando IA + RAG")
            
            # PRIORIDAD 1: Usar los cafés que ya fueron recomendados (si existen)
            cafes_a_describir = estado.get("ultimos_cafes", [])
            
            # PRIORIDAD 2: Si no hay cafés guardados, usar la matriz según método+perfil
            if not cafes_a_describir and estado["metodo"] and estado["perfil"]:
                matriz_cafes = {
                    ("espresso", "tradicional"): ["Alacrán", "Cóndor", "Lince", "Yurumi"],
                    ("espresso", "exotico"): ["Dimeti", "Delfín Rosado", "Puma"],
                    ("espresso", "funky"): ["Coyote"],
                    ("filtro", "exotico"): ["Correcaminos", "Nebiri"],
                }
                cafes_a_describir = matriz_cafes.get((estado["metodo"], estado["perfil"]), [])
            
            if cafes_a_describir:
                # Buscar contexto SOLO para esos cafés
                contexto_parts = []
                for cafe in cafes_a_describir:
                    contexto_parts.append(buscar_contexto(cafe))
                contexto = "\n\n".join(contexto_parts)
                
                system_prompt = f"""
                    Eres un experto barista. Tu tarea es describir ÚNICAMENTE los siguientes cafés: {', '.join(cafes_a_describir)}.

                    No menciones ningún otro café que no esté en esta lista.

                    INFORMACIÓN DE CADA CAFÉ (notas, cuerpo, acidez):
                    {contexto}

                    REGLAS DE FORMATO OBLIGATORIAS:
                    1. Escribe CADA café en una línea NUEVA.
                    2. Comienza cada línea con un guión (-) o un número (1., 2., etc.).
                    3. Deja UNA línea en blanco entre cada café.
                    4. Ejemplo de formato CORRECTO:

                    - Alacrán: notas de chocolate y almendra. Cuerpo meloso, acidez suave.

                    - Cóndor: notas de caramelo y frutos amarillos. Cuerpo jugoso, acidez equilibrada.

                    Responde de forma natural y entusiasta, pero respetando el formato.
                    """
            else:
                contexto = buscar_contexto(user_message)
                system_prompt = f"""
                    Eres un experto barista. Usa SOLO el siguiente contexto para responder.

                    CONTEXTO RAG:
                    {contexto}

                    REGLAS DE FORMATO:
                    - Usa saltos de línea entre ideas.
                    - Si enumeras cafés, usa líneas separadas con guiones.
                    """
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3,
                max_tokens=500
            )
            respuesta_texto = response.choices[0].message.content

        # ========== RUTA 2: Recordatorio del estado ==========
        elif intencion == "pregunta_recordatorio":
            print(f"   📝 Usando recordatorio de estado")
            
            if estado["metodo"] and estado["perfil"]:
                respuesta_texto = f"Según lo que hablamos, elegiste café en {estado['metodo']} con perfil {estado['perfil']}. ¿Te gustaría que te recomiende algo de esa combinación?"
            elif estado["metodo"] and not estado["perfil"]:
                respuesta_texto = f"Elegiste café en {estado['metodo']}, pero aún no me has dicho qué perfil prefieres (tradicional, exótico o funky)."
            else:
                respuesta_texto = "Aún no me has dicho cómo tomas tu café. ¿En máquina de espresso o en filtro?"

        # ========== RUTA 3: Saludos y agradecimientos ==========
        elif intencion == "simple_saludo":
            if "gracias" in user_lower or "graciass" in user_lower:
                respuesta_texto = "¡De nada! Me alegra haberte ayudado. ¿Hay algo más en lo que pueda asistirte? ☕"
            elif any(word in user_lower for word in ["adios", "chao", "hasta luego"]):
                respuesta_texto = "¡Gracias por consultarnos! Vuelve cuando quieras más café. ¡Hasta luego! ☕"
            else:
                respuesta_texto = "¡Hola! ¿Cómo tomas tu café, en máquina de espresso o en filtro?"

        # ========== RUTA 4: Lógica dura (compra) ==========
        else:  # logica_compra
            print(f"   💻 Usando lógica dura")
            
            if not estado["metodo"]:
                respuesta_texto = "¿Cómo tomas tu café, en máquina de espresso o en filtro?"
            elif estado["metodo"] and not estado["perfil"]:
                respuesta_texto = f"Para café en {estado['metodo']}, ¿qué perfil te gusta? TRADICIONAL, EXÓTICO o FUNKY?"
            else:
                respuesta_texto = recomendar_cafe(estado["metodo"], estado["perfil"], session_id)
        
        # Guardar respuesta
        await save_message(session_id, "assistant", respuesta_texto)
        print(f"   💬 Respuesta: {respuesta_texto[:100]}...")
        
        return Respuesta(respuesta=respuesta_texto)
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# ==================== ENDPOINT DE DEPURACIÓN ====================
@app.get("/debug/estado/{session_id}")
async def debug_estado(session_id: str):
    """Ver el estado actual de una sesión (útil para depurar)"""
    estado = estado_usuario.get(session_id, {"metodo": None, "perfil": None, "ultimos_cafes": []})
    return {
        "session_id": session_id,
        "metodo": estado["metodo"],
        "perfil": estado["perfil"],
        "ultimos_cafes": estado["ultimos_cafes"]
    }

# ==================== HTML ====================
@app.get("/", response_class=HTMLResponse)
async def get_chat():
    return """
    <!doctype html>
    <html lang="es">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Asistente de Café ☕</title>
        <link rel="icon" type="image/png" href="/static/logo.png">
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                position: relative;
                font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
                background: #1a1a1a;
                height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
            }
            
            /* Logo esquina superior izquierda */
            .logo-top-left {
                position: absolute;
                top: 20px;
                left: 20px;
                width: 200px;
                height: 200px;
                z-index: 10;
                opacity: 0.15;
                pointer-events: none;
            }
            
            /* Logo esquina inferior derecha (marca de agua) */
            .logo-bottom-right {
                position: absolute;
                bottom: 20px;
                right: 20px;
                width: 200px;
                height: 200px;
                z-index: 10;
                opacity: 0.15;
                pointer-events: none;
            }
            
            .chat-container {
                width: 90%;
                max-width: 800px;
                height: 80vh;
                background: #ffffff;
                border-radius: 28px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
                display: flex;
                flex-direction: column;
                overflow: hidden;
                border: 1px solid #e0e0e0;
                position: relative;
                z-index: 1;
            }
            
            .chat-header {
                background: #000000;
                color: white;
                padding: 20px;
                text-align: center;
                border-bottom: 1px solid #333;
            }
            
            .chat-header h1 {
                font-size: 1.5em;
                margin-bottom: 5px;
                font-weight: 600;
            }
            
            .chat-header p {
                font-size: 0.85em;
                opacity: 0.7;
            }
            
            .chat-messages {
                flex: 1;
                overflow-y: auto;
                padding: 20px;
                background: #f8f8f8;
            }
            
            .chat-messages::-webkit-scrollbar {
                width: 6px;
            }
            
            .chat-messages::-webkit-scrollbar-track {
                background: #e0e0e0;
                border-radius: 3px;
            }
            
            .chat-messages::-webkit-scrollbar-thumb {
                background: #888;
                border-radius: 3px;
            }
            
            .message {
                margin-bottom: 20px;
                display: flex;
                align-items: flex-start;
                animation: fadeIn 0.3s ease;
            }
            
            @keyframes fadeIn {
                from {
                    opacity: 0;
                    transform: translateY(10px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            
            .message.user {
                justify-content: flex-end;
            }
            
            .message-content {
                max-width: 70%;
                padding: 12px 18px;
                border-radius: 20px;
                position: relative;
                line-height: 1.5;
                font-size: 0.95em;
            }
            
            .user .message-content {
                background: #000000;
                color: #ffffff;
                border-bottom-right-radius: 4px;
                border: 1px solid #333;
            }
            
            .assistant .message-content {
                background: #ffffff;
                color: #1a1a1a;
                border: 1px solid #d0d0d0;
                border-bottom-left-radius: 4px;
                box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
            }
            
            .assistant .message-content ul,
            .assistant .message-content ol {
                margin: 8px 0 8px 20px;
            }
            
            .assistant .message-content li {
                margin: 4px 0;
            }
            
            .assistant .message-content p {
                margin: 8px 0;
            }
            
            .assistant .message-content br {
                display: block;
                margin: 8px 0;
                content: "";
            }
            
            .typing-indicator {
                display: none;
                padding: 12px 18px;
                background: #ffffff;
                border-radius: 20px;
                border: 1px solid #d0d0d0;
                width: fit-content;
                border-bottom-left-radius: 4px;
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
            
            .typing-indicator span:nth-child(2) {
                animation-delay: 0.2s;
            }
            
            .typing-indicator span:nth-child(3) {
                animation-delay: 0.4s;
            }
            
            @keyframes typing {
                0%, 60%, 100% {
                    transform: translateY(0);
                    opacity: 0.5;
                }
                30% {
                    transform: translateY(-10px);
                    opacity: 1;
                }
            }
            
            .chat-input-container {
                padding: 16px 20px;
                background: #ffffff;
                border-top: 1px solid #e0e0e0;
                display: flex;
                gap: 12px;
            }
            
            .chat-input {
                flex: 1;
                padding: 12px 18px;
                border: 1.5px solid #d0d0d0;
                border-radius: 30px;
                font-size: 0.95em;
                outline: none;
                transition: all 0.3s ease;
                font-family: inherit;
                background: #ffffff;
                color: #1a1a1a;
            }
            
            .chat-input:focus {
                border-color: #000000;
                box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.05);
            }
            
            .chat-input::placeholder {
                color: #aaa;
                font-weight: 400;
            }
            
            .send-button {
                padding: 12px 28px;
                background: #000000;
                color: white;
                border: none;
                border-radius: 30px;
                cursor: pointer;
                font-size: 0.95em;
                font-weight: 500;
                transition: all 0.3s ease;
                font-family: inherit;
            }
            
            .send-button:hover {
                background: #cc0000;
                transform: scale(0.98);
            }
            
            .send-button:disabled {
                background: #999999;
                cursor: not-allowed;
                transform: none;
            }
        </style>
    </head>
    <body>
        <!-- Logo en esquina superior izquierda -->
        <img src="/static/logo.png" alt="Logo" class="logo-top-left">
        
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
        
        <!-- Logo en esquina inferior derecha (semitransparente como marca de agua) -->
        <img src="/static/logo.png" alt="Logo" class="logo-bottom-right">
        <script>
        const chatMessages = document.getElementById("chatMessages");
        const messageInput = document.getElementById("messageInput");
        const sendButton = document.getElementById("sendButton");

        let sessionId = localStorage.getItem("chat_session_id");
        if (!sessionId) {
            sessionId = "session_" + Date.now() + "_" + Math.random().toString(36);
            localStorage.setItem("chat_session_id", sessionId);
        }

        function handleKeyPress(event) {
            if (event.key === "Enter") sendMessage();
        }

        function addMessage(content, isUser) {
            const messageDiv = document.createElement("div");
            messageDiv.className = `message ${isUser ? "user" : "assistant"}`;
            const contentDiv = document.createElement("div");
            contentDiv.className = "message-content";
            contentDiv.innerHTML = content.replace(/\\n/g, "<br>");
            messageDiv.appendChild(contentDiv);
            chatMessages.appendChild(messageDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        function showTypingIndicator() {
            const typingDiv = document.createElement("div");
            typingDiv.className = "message assistant";
            typingDiv.id = "typingIndicator";
            const indicatorDiv = document.createElement("div");
            indicatorDiv.className = "typing-indicator";
            indicatorDiv.innerHTML = "<span></span><span></span><span></span>";
            indicatorDiv.style.display = "block";
            typingDiv.appendChild(indicatorDiv);
            chatMessages.appendChild(typingDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        function removeTypingIndicator() {
            const indicator = document.getElementById("typingIndicator");
            if (indicator) indicator.remove();
        }

        async function sendMessage() {
            const message = messageInput.value.trim();
            if (!message) return;
            messageInput.disabled = true;
            sendButton.disabled = true;
            addMessage(message, true);
            messageInput.value = "";
            showTypingIndicator();
            try {
            const response = await fetch("/preguntar", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                mensaje: message,
                session_id: sessionId,
                }),
            });
            removeTypingIndicator();
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || "Error en el servidor");
            }
            const data = await response.json();
            addMessage(data.respuesta, false);
            } catch (error) {
            removeTypingIndicator();
            addMessage(`❌ Error: ${error.message}`, false);
            console.error("Error:", error);
            } finally {
            messageInput.disabled = false;
            sendButton.disabled = false;
            messageInput.focus();
            }
        }
        </script>
    </body>
    </html>
    """
