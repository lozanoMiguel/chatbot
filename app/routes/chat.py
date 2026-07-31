import uuid

from fastapi import APIRouter, HTTPException

from app.database import save_message
from app.functions import (
    clasificar_con_ia,
    clasificar_intencion_simple,
    get_metodo,
    get_openai_client,
    get_perfil,
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

        user_lower = user_message.lower()

        metodos = [
            "maquina de espresso",
            "maquina de expreso",
            "maquina de espreso",
            "espresso",
            "espreso",
            "expreso",
            "expresso",
            "filtro",
            "filtrado",
            "filter",
        ]
        perfiles = [
            "tradicionales",
            "tradicional",
            "exotico",
            "exotic",
            "fanky",
            "funky",
            "fonky",
        ]

        for met in metodos:
            if met in user_lower:
                estado_usuario[session_id]["metodo"] = get_metodo(user_lower)

        for per in perfiles:
            if per in user_lower:
                estado_usuario[session_id]["perfil"] = get_perfil(user_lower)

        # asignamos los valores de estado_usuario a la variable estado (si hay que hacer modificaciones posteriormente, utilizamos dicha variable sin tocar la original: estado_usuario)
        estado = estado_usuario[session_id]
        print(
            f"   📊 Estadooo: método={estado['metodo']}, perfil={estado['perfil']}, ultimos_cafes={estado['ultimos_cafes']}"
        )

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
        if intencion == "ia_descripcion_cafe":
            print("   🤖 Usando IA + RAG")
            cafes_mencionados = []

            todos_los_cafes = [
                "Alacrán",
                "Cóndor",
                "Lince",
                "Yurumi",
                "Correcaminos",
                "Dimeti",
                "Delfín Rosado",
                "Puma",
                "Nebiri",
                "Coyote",
            ]

            # PRIORIDAD 1: Usar los cafés ya fueron consultados

            # revisa en el mensaje si el usuario hace mencion a un cafe en particular utilizando todos nuestros cafes y lo matchea con la consulta
            for cafe in todos_los_cafes:
                cafe_normalizado = normalizar_texto(
                    cafe
                )  # normaliza el cafe que coincidió para buscarlo en el mensaje pero agrega el cafe sin normalizar para la busqueda en el indice rag
                if cafe_normalizado in user_lower:
                    cafes_mencionados.append(cafe)

            if cafes_mencionados:
                cafes_a_describir = cafes_mencionados
                print(
                    f"Usuario menciono especificamente{cafes_mencionados} verificacion: {cafes_a_describir}"
                )
            elif estado.get("ultimos_cafes", []):
                cafes_a_describir = estado.get("ultimos_cafes", [])
                print("Usando ultimos cafes")

            # PRIORIDAD 2: Si no hay cafés guardados, usar la matriz según método+perfil
            if not cafes_a_describir and estado["metodo"] and estado["perfil"]:
                matriz_cafes = {
                    ("espresso", "tradicional"): [
                        "Alacrán",
                        "Cóndor",
                        "Lince",
                        "Yurumi",
                    ],
                    ("espresso", "exotico"): ["Dimeti", "Delfín Rosado", "Puma"],
                    ("espresso", "funky"): ["Coyote"],
                    ("filtro", "exotico"): ["Correcaminos", "Nebiri"],
                }
                cafes_a_describir = matriz_cafes.get(
                    (estado["metodo"], estado["perfil"]), []
                )
                print(f"   📌 Usando matriz: {cafes_a_describir}")

            if cafes_a_describir:
                # Buscar contexto SOLO para esos cafés
                contexto_parts = []

                for cafe in cafes_a_describir:
                    print(f"\n🔍 Buscando: {cafe}")
                    contexto_parts.append(buscar_contexto(cafe, filtro_nombre=cafe))

                contexto = "\n\n".join(contexto_parts)

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
        elif intencion == "ia_faq":
            contexto = buscar_contexto(user_lower)
            system_prompt = f"""
                                Eres un experto en el mundo del cafe de especialidad, tienes bastos conocimientos sobre tostado de cafe, sabes recomendar acertadamente y eres un excelso barista.
                                Usa SOLO el siguiente contexto para responder.

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

        # ========== RUTA 3: Recordatorio de cafes ==========
        elif intencion == "pregunta_recordatorio":
            print("   📝 Usando recordatorio de estado")

            if estado["ultimos_cafes"]:
                cafes = estado["ultimos_cafes"]
                respuesta_texto = f"Estos son los cafes que te recomendé anteriormente: {', '.join(cafes[:-1])} y {cafes[-1]}"
            else:
                respuesta_texto = "Aún no me has dicho cómo tomas tu café. ¿En máquina de espresso o en filtro?"

        # ========== RUTA 4: Saludos y agradecimientos ==========
        elif intencion == "simple_saludo":
            if "gracias" in user_lower or "graciass" in user_lower:
                respuesta_texto = "¡De nada! Me alegra haberte ayudado. ¿Hay algo más en lo que pueda asistirte? ☕"
            elif any(word in user_lower for word in ["adios", "chao", "hasta luego"]):
                respuesta_texto = "¡Gracias por consultarnos! Vuelve cuando quieras más café. ¡Hasta luego! ☕"
            else:
                respuesta_texto = (
                    "¡Hola! ¿Cómo tomas tu café, en máquina de espresso o en filtro?"
                )

        # ========== RUTA 5: Lógica dura (compra) ==========
        else:  # logica_compra
            print("   💻 Usando lógica dura")

            if not estado["perfil"]:
                respuesta_texto = """Tenemos 3 perfiles de café:

                                - TRADICIONAL (niveles 1/3 a 3/3): Sabores clásicos, achocolatados, nueces, caramelo. Acidez suave a media. Cuerpo meloso o jugoso. Ideal para quienes empiezan o buscan un espresso reconfortante.

                                - EXÓTICO (niveles 1/3 a 3/3): Sabores frutales (fresa, mango, mora), florales, cítricos. Acidez más marcada (málica, cítrica, tartárica). Cuerpo cremoso. Para paladares aventureros.

                                - FUNKY (nivel 3/3): Sabores licorosos, fermentados, frutas maduras, vino, mermelada. Acidez media a alta. Cuerpo cremoso. Para expertos.

                                Que perfil te gustaria probar?
                                """
            elif estado["perfil"] and not estado["metodo"]:
                respuesta_texto = (
                    "¿Cómo tomas tu café, en máquina de espresso o en filtro?"
                )
            else:
                respuesta_texto = recomendar_cafe(
                    estado["metodo"], estado["perfil"], session_id
                )

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
