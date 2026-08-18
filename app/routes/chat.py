import uuid

from fastapi import APIRouter, HTTPException

from app.database import save_message
from app.functions import (
    clasificar_con_ia,
    clasificar_intencion_simple,
    describir_cafe,
    get_openai_client,
    identificar_metodo,
    identificar_perfil,
    normalizar_texto,
    recomendar_cafe,
)
from app.models import ChatRequest, ChatResponse, Request, Response
from app.rag import buscar_contexto
from app.state import estado_usuario

router = APIRouter()


@router.post("/preguntar", response_model=Response)
async def preguntar(pregunta: Request):
    session_id = pregunta.session_id
    user_message = pregunta.mensaje

    print(f"\n📨 [{session_id[:8]}] Usuario: {user_message}")

    try:
        await save_message(session_id, "user", user_message)

        user_lower = normalizar_texto(user_message)

        identificar_metodo(user_lower, session_id)
        identificar_perfil(user_lower, session_id)

        # asignamos los valores de estado_usuario a la variable estado (si hay que hacer modificaciones posteriormente, utilizamos dicha variable sin tocar la original: estado_usuario)
        estado = estado_usuario[session_id]
        print(
            f"   📊 Estadooo: método={estado['metodo']}, perfil={estado['perfil']}, ultimos_cafes={estado['ultimos_cafes']}"
        )

        # ========== IDENTIFICAION DE INTENCION EN EL MENSAJE ==========
        intencion = clasificar_intencion_simple(user_lower)
        print(f"   🧠 Intención: {intencion}")

        if intencion is None:
            # Si las reglas simples no pudieron clasificar, usamos IA
            print("   🤔 Mensaje ambiguo, usando IA para clasificar...")
            intencion = await clasificar_con_ia(user_message)
            print(f"   🧠 IA clasificó como: {intencion}")
        else:
            print(f"   📏 Reglas simples clasificaron como: {intencion}")

        # ========== RUTA 1: IA para descripciones de cafe ==========
        if intencion == "intencion_descripcion":
            print("   🤖 Usando IA + RAG")
            cafes_a_describir = describir_cafe(estado["metodo"], estado["perfil"], user_lower, estado["ultimos_cafes"])

            if cafes_a_describir:
                # Buscar contexto SOLO para esos cafés
                contexto_parts = []

                for cafe in cafes_a_describir:
                    print(f"\n🔍 Buscando: {cafe}")
                    contexto_parts.append(buscar_contexto(cafe))

                contexto = "\n\n".join(contexto_parts)
                print(f"contexto:{contexto}")

                system_prompt = f"""
                    Eres dueño y tostador de una cafeteria que vende su cafe. Conoces todo el ciclo de produccion, desde que te llega el grano verde, pasando por el tueste, las catas y el envasado. Tu tarea es describir ÚNICAMENTE los siguientes cafés: {", ".join(cafes_a_describir)}.

                    No menciones ningún otro café que no esté en esta lista.

                    INFORMACIÓN DE CADA CAFÉ (Origen, notas, cuerpo, acidez y recomendacion):
                    {contexto}

                    REGLAS DE FORMATO OBLIGATORIAS:
                    1. Escribe CADA café en una línea NUEVA.
                    2. Menciona el nombre del cafe en formato negrita.
                    3. Comienza cada línea con un guión (-) o un número (1., 2., etc.).
                    4. Puedes agregar 2 o 3 emojis, no mas.
                    5. Ejemplo de formato CORRECTO:

                    - Alacrán: Cafe de El Salvador, de la region de Apaneca-Ilamatepec. Tiene notas a chocolate y almendra. Cuerpo meloso, acidez suave. Perfecto para quienes buscan un café clásico con notas a chocolate y frutos secos.

                    - Cóndor: Cafe de Colombia, de la region de Huila. Con notas a caramelo y frutos amarillos. Cuerpo jugoso, acidez equilibrada, Ideal para principiantes o para quienes toman café con leche.

                    Responde de forma natural y entusiasta, pero respetando el formato.

                    """
                client = get_openai_client()
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.3,
                    max_tokens=500,
                )
                respuesta_texto = response.choices[0].message.content
            else:
                respuesta_texto = "No tengo información sobre esos cafés. ¿Podrías especificar cuál te interesa?"

        # ========== RUTA 2: IA descripciones y consultas ==========
        elif intencion == "intencion_faq":
            contexto = buscar_contexto(user_lower)
            system_prompt = f"""
                                Eres un experto en el mundo del cafe de especialidad, tienes bastos conocimientos sobre tostado de cafe, sabes recomendar acertadamente y eres un excelso barista.
                                Utiliza el siguiente contexto para responder o acude a tu base de conocimiento.

                                CONTEXTO RAG:
                                {contexto}

                                REGLAS DE FORMATO:
                                - Si mencionas cafes, mencionalos en formato negrita.
                                - Puedes utilizar emoticones si deseas, 2 o 3 no mas.
                                """
            client = get_openai_client()
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.5,
                max_tokens=500,
            )
            respuesta_texto = response.choices[0].message.content

        # ========== RUTA 3: Saludos y agradecimientos ==========
        elif intencion == "intencion_saludo":
            if "gracias" in user_lower:
                respuesta_texto = "¡De nada! Me alegra haberte ayudado. ¿Hay algo más en lo que pueda asistirte? ☕"
            elif any(word in user_lower for word in ["adios", "chao", "hasta luego"]):
                respuesta_texto = "¡Gracias por consultarnos! Vuelve cuando quieras más café. ¡Hasta luego! ☕"
            else:
                respuesta_texto = (
                    "¡Hola! ¿Cómo tomas tu café, en máquina de espresso o en filtro?"
                )

        # ========== RUTA 4: Lógica dura (compra) ==========
        elif intencion == "intencion_compra":
            print("   💻 Usando lógica dura")
            if not estado["metodo"]:
                respuesta_texto = ("¡Perfecto! ☕ Primero, ¿cómo lo vas a preparar? Espresso o filtro?")
            elif estado["metodo"] and not estado["perfil"]:
                respuesta_texto = (
                    f"""Perfecto, para {estado["metodo"]} ¿Qué perfil te apetece?

                        🌰 Tradicional — clásico y equilibrado
                        🍊 Exótico — frutal y complejo
                        🧪 Funky — fermentado e intenso
                    """)
            else:
                cafes_recomendados = recomendar_cafe(
                    estado["metodo"], estado["perfil"], session_id
                )
                if not cafes_recomendados:
                    respuesta_texto = f"No tenemos cafés {estado['perfil']} para {estado['metodo']}. ¿Te gustaría probar otro perfil?"
                #elif len(cafes_recomendados) == 1:

                    #respuesta_texto = f"Para {estado['metodo']} y perfil {estado['perfil']}, te recomiendo {cafes_recomendados[0]}. ¡Es una excelente elección!"
               # else:
                #    respuesta_texto =  f"Para {estado['metodo']} y perfil {estado['perfil']}, te recomiendo: {', '.join(cafes_recomendados[:-1])} y {cafes_recomendados[-1]}."
                else:
                    contexto_parts = []
                    for cafe in cafes_recomendados:
                        print(f"\n🔍 Buscando: {cafe}")
                        contexto_parts.append(buscar_contexto(cafe))
                    contexto = "\n\n".join(contexto_parts)
                    system_prompt = f"""
                                        Eres dueño y tostador de una cafeteria que vende su cafe. Conoces todo el ciclo de produccion, desde que te llega el grano verde, pasando por el tueste, las catas y el envasado. Tu tarea es describir ÚNICAMENTE los siguientes cafés: {", ".join(cafes_recomendados)}.

                                        No menciones ningún otro café que no esté en esta lista.

                                        INFORMACIÓN DE CADA CAFÉ (Origen, notas, cuerpo, acidez y recomendacion):
                                        {contexto}

                                        REGLAS DE FORMATO OBLIGATORIAS:
                                        1. Empieza la respuesta diciendo: Para {estado['metodo']} y perfil {estado['perfil']} te recomiendo:
                                        2. Escribe CADA café en una línea NUEVA.
                                        3. Menciona el nombre del cafe en formato negrita.
                                        4. Comienza cada línea con un guión (-) o un número (1., 2., etc.).
                                        5. Puedes agregar 2 o 3 emojis, no mas.
                                        6. Ejemplo de formato CORRECTO:

                                        - Alacrán: Cafe de El Salvador, de la region de Apaneca-Ilamatepec. Tiene notas a chocolate y almendra. Cuerpo meloso, acidez suave. Perfecto para quienes buscan un café clásico con notas a chocolate y frutos secos.

                                        Responde de forma natural y entusiasta, pero respetando el formato.

                                        """
                    client = get_openai_client()
                    response = client.chat.completions.create(
                                        model="gpt-4o-mini",
                                        messages=[
                                            {"role": "system", "content": system_prompt},
                                            {"role": "user", "content": user_message},
                                        ],
                                        temperature=0.3,
                                        max_tokens=500,
                                    )
                    respuesta_texto = response.choices[0].message.content
        # ========== RUTA 5: Fallback ==========
        else: #fallback
            respuesta_texto = "Puedo ayudarte a encontrar el café que mejor se adapte a tus gustos, solo cuentame como lo preparas en casa :)"

        # Guardar respuesta
        await save_message(session_id, "assistant", respuesta_texto)
        print(f"   💬 Respuesta: {respuesta_texto[:100]}...")

        return Response(respuesta=respuesta_texto)

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}") from e


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    session_id = f"test_{uuid.uuid4().hex[:8]}"
    pregunta = Request(mensaje=request.mensaje, session_id=session_id)
    resultado = await preguntar(pregunta)
    return ChatResponse(respuesta=resultado.respuesta)
