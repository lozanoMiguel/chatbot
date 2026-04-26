"""
Chatbot de café - Main
Flujo controlado por lógica dura en Python, no por IA.
"""

import json
from contextlib import asynccontextmanager
from collections import defaultdict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from openai import OpenAI
import unicodedata
import re

from app.config import OPENAI_API_KEY
from app.database import init_db, save_message, get_conversation_history
from app.rag import buscar_contexto

# Cliente OpenAI (solo para preguntas específicas)
client = OpenAI(api_key=OPENAI_API_KEY)

# ==================== ESTADO DE CONVERSACIÓN ====================
estado_usuario = defaultdict(lambda: {"metodo": None, "perfil": None})

# ==================== FUNCIONES DE RECOMENDACIÓN ====================
def normalizar_texto(texto: str) -> str:
    """
    Normaliza el texto: minúsculas, sin acentos, sin caracteres especiales.
    
    Ejemplos:
        "¿Cómo tomas tu café?" → "como tomas tu cafe"
        "¡Hola! ¿Qué tal?" → "hola que tal"
        "Té o café?" → "te o cafe"
    """
    # 1. Convertir a minúsculas
    texto = texto.lower()
    
    # 2. Eliminar acentos (normalizar a forma ASCII)
    #    'café' → 'cafe', 'té' → 'te', 'más' → 'mas'
    texto = unicodedata.normalize('NFKD', texto)
    texto = texto.encode('ASCII', 'ignore').decode('ASCII')
    
    # 3. Eliminar signos de puntuación y caracteres especiales
    #    Solo mantenemos letras, números y espacios
    texto = re.sub(r'[^a-z0-9\s]', '', texto)
    
    # 4. Eliminar espacios múltiples y trim
    texto = re.sub(r'\s+', ' ', texto).strip()
    
    return texto
def recomendar_cafe(metodo: str, perfil: str) -> str:
    """Recomienda cafés según método y perfil"""
    matriz = {
        ("espresso", "tradicional"): ["Alacrán", "Cóndor", "Lince", "Yurumi"],
        ("espresso", "exotico"): ["Dimeti", "Delfín Rosado", "Puma"],
        ("espresso", "funky"): ["Coyote"],
        ("filtro", "exotico"): ["Correcaminos", "Nebiri"],
    }
    cafes = matriz.get((metodo, perfil), [])
    
    if not cafes:
        return f"No tenemos cafés {perfil} para {metodo}. ¿Te gustaría probar otro perfil?"
    elif len(cafes) == 1:
        return f"Para {metodo} y perfil {perfil}, te recomiendo {cafes[0]}. ¡Es una excelente elección!"
    else:
        return f"Para {metodo} y perfil {perfil}, te recomiendo: {', '.join(cafes[:-1])} y {cafes[-1]}."

def clasificar_intencion(mensaje: str) -> str:
    """
    Clasifica la intención del usuario.
    Retorna: 'compra', 'descripcion', 'info_general' o 'otro'
    """
    user_lower = normalizar_texto(mensaje)
    
    # Intenciones que usan IA
    if any(phrase in user_lower for phrase in [
        "describeme", "describime","qué notas tiene", "contame sobre", "que significa",
        "de dónde es", "origen", "diferencia entre", "cuéntame más",
        "explicame","explicarme" "como se prepara","que perfil"
    ]):
        return "ia_descripcion"
    
    if user_lower in ["hola", "buenos dias", "buenas tardes", "gracias", "adios"]:
        return "simple_saludo"
    
    frases_recordatorio = [
        "que metodo", "que perfil", "que elegi", "como tomo el cafe",
        "que me recomendaste", "cual fue mi eleccion", "que habia elegido"
    ]
    if any(phrase in user_lower for phrase in frases_recordatorio):
        return "pregunta_recordatorio"
    
    # Intenciones que usan lógica dura
    if any(phrase in user_lower for phrase in [
        "quiero comprar", "quiero un cafe", "recomienda", "cafe por favor"
    ]):
        return "logica_compra"
    
    if any(word in user_lower for word in ["espresso", "filtro", "tradicional", "exotico", "funky"]):
        return "logica_compra"
    
    return "logica_compra"  # por defecto

def actualizar_estado_desde_mensaje(session_id: str, mensaje: str):
    """Actualiza el estado de la conversación basado en el mensaje"""
    
    if "espresso" in mensaje or "espreso" in mensaje:
        estado_usuario[session_id]["metodo"] = "espresso"
    elif "filtro" in mensaje:
        estado_usuario[session_id]["metodo"] = "filtro"
    
    if "tradicional" in mensaje:
        estado_usuario[session_id]["perfil"] = "tradicional"
    elif "exotico" in mensaje or "afrutado" in mensaje:
        estado_usuario[session_id]["perfil"] = "exotico"
    elif "funky" in mensaje:
        estado_usuario[session_id]["perfil"] = "funky"
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
        
        # ========== CLASIFICAR INTENCIÓN ==========
        intencion = clasificar_intencion(user_lower)
        print(f"   🧠 Intención detectada: {intencion}")
        
        # ========== RUTA 1: IA para descripciones ==========
        if intencion == "ia_descripcion":
            print(f"   🤖 Usando IA + RAG")
            contexto = buscar_contexto(user_message)
            
            system_prompt = f"""
Eres un experto barista. Usa SOLO el siguiente contexto para responder.
Si la respuesta no está en el contexto, di: "No tengo información sobre eso. ¿Quieres que te ayude a elegir un café?"

CONTEXTO: {contexto}
"""
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.3,
                max_tokens=300
            )
            respuesta_texto = response.choices[0].message.content
            
            if intencion == "pregunta_recordatorio":
                estado = estado_usuario[session_id]
        
            if estado["metodo"] and estado["perfil"]:
                respuesta_texto = f"Según nuestra conversación, elegiste café en {estado['metodo']} con perfil {estado['perfil']}. ¿Te gustaría probar algún café de esta combinación?"
            elif estado["metodo"] and not estado["perfil"]:
                respuesta_texto = f"Elegiste café en {estado['metodo']}, pero aún no me has dicho qué perfil prefieres. ¿Tradicional, exótico o funky?"
            elif not estado["metodo"]:
                respuesta_texto = "Aún no me has dicho cómo tomas tu café. ¿En máquina de espresso o en filtro?"
            else:
                respuesta_texto = "No tengo información sobre tu elección anterior. ¿Quieres que te ayude a elegir un café?"
        
        # ========== RUTA 2: Saludos simples (sin estado) ==========
        elif intencion == "simple_saludo":
            if "hola" in user_lower or "buenos" in user_lower:
                respuesta_texto = "¡Hola! ¿Cómo tomas tu café, en máquina de espresso o en filtro?"
            elif "gracias" in user_lower:
                respuesta_texto = "¡De nada! ¿Hay algo más en lo que pueda ayudarte? ☕"
            elif "adiós" in user_lower or "chao" in user_lower:
                respuesta_texto = "¡Gracias por consultarnos! Vuelve cuando quieras más café ☕"
            else:
                respuesta_texto = "¿Cómo tomas tu café, en máquina de espresso o en filtro?"
        
        # ========== RUTA 3: Lógica dura para compras ==========
        else:  # logica_compra
            print(f"   💻 Usando lógica dura")
            
            # Actualizar estado
            actualizar_estado_desde_mensaje(session_id, user_lower)
            estado = estado_usuario[session_id]
            print(f"   📊 Estado: método={estado['metodo']}, perfil={estado['perfil']}")
            
            # Generar respuesta según estado
            if not estado["metodo"]:
                respuesta_texto = "¿Cómo tomas tu café, en máquina de espresso o en filtro?"
            
            elif estado["metodo"] and not estado["perfil"]:
                respuesta_texto = f"Para café en {estado['metodo']}, ¿qué perfil te gusta? tradicional, exotico o funky?"
            
            else:
                respuesta_texto = recomendar_cafe(estado["metodo"], estado["perfil"])
        
        # Guardar y devolver
        await save_message(session_id, "assistant", respuesta_texto)
        print(f"   💬 Respuesta: {respuesta_texto[:80]}...")
        
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
    estado = estado_usuario.get(session_id, {"metodo": None, "perfil": None})
    return {
        "session_id": session_id,
        "metodo": estado["metodo"],
        "perfil": estado["perfil"]
    }

# ==================== HTML (leer desde archivo) ====================
@app.get("/", response_class=HTMLResponse)
async def get_chat():
    """Sirve la interfaz HTML"""
    return HTML_CONTENT

# ==================== CONTENIDO HTML ====================
HTML_CONTENT = """
<!DOCTYPE html>
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
</html>
"""
