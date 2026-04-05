
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

# Inicializar el cliente de OpenAI (nueva forma)
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

<<<<<<< HEAD
app = FastAPI(title="Asistente de Café", version="1.0.0")

# Permitir peticiones desde cualquier origen (para la interfaz web)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class Pregunta(BaseModel):
    mensaje: str

class Respuesta(BaseModel):
    respuesta: str

@app.post("/preguntar", response_model=Respuesta)
async def preguntar(pregunta: Pregunta):
    """Endpoint que recibe una pregunta sobre café y responde con OpenAI"""
    try:
        system_prompt = """
        Eres un experto barista y conocedor de café. Tu misión es ayudar a los usuarios con dudas sobre:
        - Tipos de granos (arábiga, robusta, etc.)
        - Métodos de preparación (espresso, prensa francesa, pour over, etc.)
        - Temperatura, molienda, extracción
        - Historia y curiosidades del café
        - Recomendaciones de cafeterías y marcas
        Responde de forma amigable, precisa y con pasión por el café.
        Responde siempre en español.
        """

        # NUEVA forma de llamar a la API (versión >=1.0.0)
        completion = client.chat.completions.create(
            model="gpt-4.1-mini",  # o "gpt-4" si tienes acceso
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": pregunta.mensaje}
            ],
            max_tokens=500,
            temperature=0.7
        )

        respuesta_texto = completion.choices[0].message.content
        return Respuesta(respuesta=respuesta_texto)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error con OpenAI: {str(e)}")

@app.get("/", response_class=HTMLResponse)
async def get_chat():
    """Servir la interfaz HTML del chatbot"""
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Asistente de Café ☕</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
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
            
            .chat-header h1 {
                font-size: 1.5em;
                margin-bottom: 5px;
            }
            
            .chat-header p {
                font-size: 0.9em;
                opacity: 0.9;
            }
            
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
            
            .message.user {
                justify-content: flex-end;
            }
            
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
            
            .chat-input:focus {
                border-color: #667eea;
            }
            
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
            
            .send-button:hover {
                background: #5a3d2b;
            }
            
            .send-button:disabled {
                background: #ccc;
                cursor: not-allowed;
            }
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
                        ¡Hola! Soy tu asistente experto en café. ¿En qué puedo ayudarte hoy? Puedo asesorarte sobre:
                        <ul style="margin-top: 8px; margin-left: 20px;">
                            <li>Tipos de granos y tostados</li>
                            <li>Métodos de preparación</li>
                            <li>Temperatura y molienda</li>
                            <li>Historia y curiosidades</li>
                            <li>Recomendaciones y marcas</li>
                        </ul>
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
            
            function handleKeyPress(event) {
                if (event.key === 'Enter') {
                    sendMessage();
                }
            }
            
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
                if (indicator) {
                    indicator.remove();
                }
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
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ mensaje: message })
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



