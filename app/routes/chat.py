import uuid
import random
from fastapi import APIRouter, HTTPException

from app.database import save_message,get_conversation_history, intencion_indiferencia
from app.functions import (
    clasificar_con_ia,
    clasificar_intencion_simple,
    cafes_mencionados,
    contains_any,
    get_openai_client,
    identificar_metodo,
    identificar_perfil,
    normalizar_texto,
)
from app.models import ChatRequest, ChatResponse, Request, Response
from app.rag import buscar_contexto, obtener_cafes_por_nombre, top_cafes_por_acidez, top_cafes_por_puntaje,filtrar_por_metadata, elegir_criterio_discriminante,  candidatos_por_metodo, METODO_A_TOSTADO
from app.models.preferencias_usuario import estado_usuario

router = APIRouter()


@router.post("/preguntar", response_model=Response)
async def preguntar(pregunta: Request):
    session_id = pregunta.session_id
    user_message = pregunta.mensaje

    print(f"\n📨 [{session_id[:8]}] Usuario: {user_message}")

    try:
        
        historial_reciente = await get_conversation_history(session_id, limit=4)
        await save_message(session_id, "user", user_message)

        user_lower = normalizar_texto(user_message)

        # Guardamos método/perfil previos para poder distinguir "el usuario
        # está respondiendo la pregunta activa" de "el usuario cambió de
        # opinión a mitad de camino" — ver más abajo.
        metodo_previo = estado_usuario[session_id].metodo
        perfil_previo = estado_usuario[session_id].perfil

        identificar_metodo(user_lower, session_id)
        identificar_perfil(user_lower, session_id)
        
        # asignamos los valores de estado_usuario a la variable estado (si hay que hacer modificaciones posteriores, utilizamos dicha variable sin tocar la original: estado_usuario)
        estado = estado_usuario[session_id]
        print(
            f"   📊 Estado: método={estado.metodo}, perfil={estado.perfil} ultimos_cafes={estado.ultimos_cafes}"
        )

        # Si el afinamiento activo YA es la pregunta de perfil, un cambio de
        # estado.perfil en este mensaje es la respuesta esperada a esa
        # pregunta (se resuelve más abajo, en el bloque de intencion_recomendacion)
        # — no es un pivot que deba tirar abajo lo ya armado.
        afinando_activo_es_perfil = bool(estado.afinando) and estado.afinando.get("criterio") == "perfil"

        cambio_metodo = metodo_previo is not None and estado.metodo != metodo_previo
        cambio_perfil = (
            perfil_previo is not None
            and estado.perfil != perfil_previo
            and not afinando_activo_es_perfil
        )

        # Reset del afinamiento en curso si método o perfil cambiaron a
        # mitad de camino (no como respuesta a la pregunta activa).
        if cambio_metodo and (estado.candidatos_actuales or estado.afinando):
            print(
                f"   🔄 Cambio de método a mitad de flujo ({metodo_previo}->{estado.metodo}), reiniciando afinamiento"
            )
            estado.candidatos_actuales = []
            estado.afinando = None

        if cambio_perfil and (estado.candidatos_actuales or estado.afinando):
            print(
                f"   🔄 Cambio de perfil a mitad de flujo ({perfil_previo}->{estado.perfil}), reiniciando afinamiento"
            )
            estado.candidatos_actuales = []
            estado.afinando = None

        # Fix quirúrgico: el perfil es "pegajoso" dentro del mismo método
        # (si ya sabemos que quiere tradicional, no hace falta repreguntar
        # con cada mensaje), pero NO cruza a un método distinto salvo que
        # el usuario lo reafirme en el mismo mensaje en que cambia de
        # método (ej. "para filtro exotico" sí lo reafirma; "para filtro"
        # solo, no). Sin esto, un perfil elegido hace rato para espresso
        # se arrastraba silenciosamente a una recomendación de filtro.
        if cambio_metodo and not cambio_perfil and estado.perfil is not None:
            print(
                f"   🔄 Método cambió sin reafirmar perfil, soltando perfil previo ({perfil_previo})"
            )
            estado.perfil = None

        # ========== IDENTIFICAION DE INTENCION EN EL MENSAJE ==========
        resultado_ia = {}
        intencion = None

        if estado.afinando:
            opciones = estado.afinando["opciones"]
            if any(clave in user_lower for clave in opciones.keys()):
                intencion = "intencion_recomendacion"
                print("   🎯 Respondiendo afinamiento activo, forzando intención")
            # si no matchea ninguna opción, no seteamos intencion acá —
            # cae naturalmente al bloque de abajo para clasificar normal

        if intencion is None:
            resultado_simple = clasificar_intencion_simple(user_lower)
            print(f"   🧠 Intención: {resultado_simple}")

            if resultado_simple is None:
                print("   🤔 Mensaje ambiguo, usando IA para clasificar...")
                resultado_ia = await clasificar_con_ia(user_message, historial_reciente)
                intencion = resultado_ia["intent"]
                print(f"   🧠 IA clasificó como: {intencion}")
            else:
                resultado_ia = resultado_simple
                intencion = resultado_simple["intent"]
                print(f"   📏 Reglas simples clasificaron como: {intencion}")

        # ========== RUTA 1: IA para descripciones de cafe ==========
        if intencion == "intencion_descripcion":
            print("   🤖 Usando IA + RAG")
            cafes = cafes_mencionados(user_lower, estado.ultimos_cafes)

            if cafes:
                # Buscar contexto SOLO para esos cafés
                print(f"\n🔍 Buscando: {cafes}")
                contexto = obtener_cafes_por_nombre(cafes, tostado=estado.metodo)
                print(f"contexto:{contexto}")

                system_prompt = f"""
                    Eres dueño de una cafetería de especialidad con tostador propio. Conoces todo el ciclo de producción, desde que te llega el grano verde, pasando por el tueste, las catas y el envasado. Tu tarea es describir ÚNICAMENTE los siguientes cafés: {", ".join(cafes)}.
                    No menciones ningún otro café que no esté en esta lista.

                    INFORMACIÓN DE CADA CAFÉ (Origen, notas, cuerpo, acidez y recomendacion):
                    {contexto}

                    Si la información anterior no incluye datos para alguno de los cafés listados,
                    no inventes esos datos: nombralo igual pero aclará que no tenés la ficha completa.

                    REGLAS DE FORMATO OBLIGATORIAS:
                    1. Escribe CADA café en una línea NUEVA.
                    2. Menciona el nombre del café en formato negrita.
                    3. Comienza cada línea con un guión (-) o un número (1., 2., etc.).
                    4. Puedes agregar 2 o 3 emojis en total, no más.
                    5. Ejemplo de formato CORRECTO:

                    - Alacrán: Café de El Salvador, de la región de Apaneca-Ilamatepec. Tiene notas a chocolate y almendra. Cuerpo meloso, acidez suave. Perfecto para quienes buscan un café clásico con notas a chocolate y frutos secos.

                    - Cóndor: Café de Colombia, de la región de Huila. Con notas a caramelo y frutos amarillos. Cuerpo jugoso, acidez equilibrada. Ideal para principiantes o para quienes toman café con leche.

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
            faq_modo = resultado_ia.get("faq_modo", "conceptual")
            alcance = resultado_ia.get("alcance", "catalogo_completo")

            # Si el usuario se refiere a cafés ya mencionados, restringimos el
            # ranking/filtro a esos, siempre que tengamos algo guardado en estado
            
            nombres_base = (
                estado.ultimos_cafes
                if alcance == "cafes_previos" and estado.ultimos_cafes
                else None
            )

            if faq_modo == "ranking":
                n = resultado_ia.get("n") or 1
                ascendente = resultado_ia.get("orden") == "asc"
                atributo = resultado_ia.get("atributo_ranking")
                if atributo == "acidez":
                    contexto = top_cafes_por_acidez(n=n, ascendente=ascendente, nombres=nombres_base)
                else:
                    contexto = top_cafes_por_puntaje(n=n, ascendente=ascendente, nombres=nombres_base)

            elif faq_modo == "filtro":
                filtros = resultado_ia.get("filtros") or {}
                if "tostado" in filtros:
                    # La metadata guarda "Expresso" (con x, no "espresso"),
                    # igual que en candidatos_por_metodo — mismo mapeo para
                    # que el filtro por tostado matchee de verdad.
                    valor_tostado = str(filtros["tostado"]).lower()
                    filtros["tostado"] = METODO_A_TOSTADO.get(valor_tostado, valor_tostado)
                contexto = (
                    filtrar_por_metadata(nombres=nombres_base, **filtros)
                    if filtros
                    else buscar_contexto(user_lower, tipo="faq")
                )
                print(f"   📦 Cafés en contexto: {[l for l in contexto.split(chr(10)) if l.startswith('NOMBRE')]}")
            else:
                contexto = buscar_contexto(user_lower, tipo="faq")
                
            nombres_esperados = [
                l.replace("NOMBRE:", "").strip()
                for l in contexto.split("\n")
                if l.strip().startswith("NOMBRE")
            ]
            
            if faq_modo == "filtro" and nombres_esperados:
                estado.ultimos_cafes = nombres_esperados
            
                
            if faq_modo in ("ranking", "filtro"):
                system_prompt = f"""
                Eres un experto en café de especialidad.

                Usa ÚNICAMENTE la siguiente información para responder. Los cafés
                mencionados abajo son TODO nuestro catálogo relevante a esta
                pregunta — no existen otros.

                CONTEXTO RAG:
                {contexto}
                
                DEBES mencionar EXACTAMENTE esta cantidad {len(nombres_esperados)},
                ni uno menos: {", ".join(nombres_esperados)}.

                La selección de cuáles cafés califican para esta pregunta YA fue
                hecha antes de dártelos (por eso están en el contexto) — no vuelvas
                a evaluar si "realmente" califican según tu propio criterio. Tu
                única tarea es describir cada uno de los {len(nombres_esperados)}
                cafés listados arriba, ninguno más, ninguno menos.

                Si el contexto está vacío, dilo explícitamente ("no tenemos cafés
                que cumplan ese criterio por ahora") en vez de inventar datos.

                NUNCA menciones países, cafés o marcas que no aparezcan en el
                contexto de arriba. No uses tu conocimiento general de café para
                completar la respuesta.

                REGLAS DE FORMATO:
                - Menciona cada café en formato negrita y puedes agregarle a cada uno de ellos, uno o dos emojis.
                
            """
            else:  # conceptual — aquí sí tiene sentido dar más libertad
                system_prompt = f"""
                    Eres un experto en el mundo del café de especialidad, con amplios
                    conocimientos sobre tueste, preparación y catación.

                    Usa el siguiente contexto si es relevante para la pregunta; si no
                    aporta nada, puedes responder con tu conocimiento general sobre
                    café.

                    CONTEXTO RAG:
                    {contexto}

                    REGLAS DE FORMATO:
                    - Si mencionas cafés, hazlo en formato negrita.
                    - Puedes usar 2 o 3 emojis, no más.
                """                  
            client = get_openai_client()
            #temperature = 0.1 if faq_modo in ("ranking", "filtro") else 0.5
            response = client.responses.create(
                                model="gpt-5.6-luna",
                                input=[
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": user_message},
                                ],
                                
                                max_output_tokens=500,
                            )
            respuesta_texto = response.output_text  
            if faq_modo in ("ranking", "filtro") and nombres_esperados:
                faltantes = [n for n in nombres_esperados if n not in respuesta_texto]
                if faltantes:
                    print(f"   ⚠️ El modelo omitió: {faltantes}. Reintentando con corrección...")
                    
                    system_prompt_reforzado = system_prompt + f"""

                            ADVERTENCIA: en un intento anterior omitiste mencionar: {", ".join(faltantes)}.
                            Verifica que TODOS los cafés del contexto aparezcan en tu respuesta.
                            Mantén el MISMO formato pedido arriba (nombre en negrita, descripción
                            natural breve, 1-2 emojis por café). NO copies los campos crudos del
                            contexto (PAIS:, REGION:, PROCESO:, etc.) tal cual — redacta una
                            descripción natural igual que harías para cualquier otro café.
                            """
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": system_prompt_reforzado},
                            {"role": "user", "content": user_message},
                            {"role": "assistant", "content": respuesta_texto},
                            {
                                "role": "user",
                                "content": (
                                    f"Te faltó incluir: {', '.join(faltantes)}. "
                                    f"Reescribe la respuesta completa incluyendo "
                                    f"TODOS los {len(nombres_esperados)} cafés: "
                                    f"{', '.join(nombres_esperados)}."
                                ),
                            },
                        ],
                        temperature=0.1,
                        max_tokens=500,
                    )
                respuesta_texto = response.output_text
 
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

        # ========== RUTA 4: Lógica dura (recomendacion) ==========
        elif intencion == "intencion_recomendacion":
            respuesta_texto = None
            cafes_a_describir = None

            pool_indiferencia = (
                estado.candidatos_actuales
                or [c for lista in (estado.afinando or {}).get("opciones", {}).values() for c in lista]
                or estado.ultimos_cafes
            )
            if pool_indiferencia and contains_any(user_lower, intencion_indiferencia):
                cafes_a_describir = [random.choice(pool_indiferencia)]
                estado.afinando = None
                estado.candidatos_actuales = []

            elif estado.afinando:
                criterio_activo = estado.afinando.get("criterio")
                opciones = estado.afinando["opciones"]
                clave_elegida = next((clave for clave in opciones.keys() if clave in user_lower), None)
                estado.afinando = None
                if clave_elegida:
                    estado.candidatos_actuales = opciones[clave_elegida]
                    # Si lo que se estaba afinando era perfil, guardamos la
                    # elección en estado.perfil — así queda disponible para
                    # el atajo de candidatos_por_metodo si más adelante
                    # cambia el método y hay que recalcular candidatos.
                    if criterio_activo == "perfil":
                        estado.perfil = clave_elegida
                # si no matcheó ninguna clave, candidatos_actuales queda
                # como estaba (comportamiento previo sin cambios)

            elif not estado.metodo:
                respuesta_texto = "¡Perfecto! ☕ Primero, ¿cómo lo vas a preparar? Espresso o filtro?"

            elif not estado.candidatos_actuales:
                # Si ya detectamos el perfil de antemano (mensaje del tipo
                # "quiero un espresso exótico"), nos saltamos la pregunta de
                # perfil y arrancamos directo filtrados por método+perfil.
                if estado.perfil:
                    estado.candidatos_actuales = candidatos_por_metodo(estado.metodo, estado.perfil)
                    if not estado.candidatos_actuales:
                        # Cruce método+perfil sin resultados (p.ej. "filtro
                        # funky" y no hay funky en filtro todavía): en vez
                        # de un callejón sin salida, ignoramos el perfil
                        # detectado y volvemos al filtro solo por método.
                        print(f"   ⚠️ Sin cafés {estado.perfil} para {estado.metodo}, ignorando perfil detectado")
                        estado.perfil = None

                if not estado.candidatos_actuales:
                    estado.candidatos_actuales = candidatos_por_metodo(estado.metodo)

                if not estado.candidatos_actuales:
                    respuesta_texto = f"No tenemos cafés disponibles para {estado.metodo} por ahora."

            if respuesta_texto is None and not cafes_a_describir:
                siguiente_pregunta = elegir_criterio_discriminante(estado.candidatos_actuales, estado.metodo)
                if siguiente_pregunta:
                    estado.afinando = siguiente_pregunta
                    respuesta_texto = siguiente_pregunta["pregunta"]
                else:
                    cafes_a_describir = estado.candidatos_actuales

            if cafes_a_describir:
                print(f"\n🔍 Buscando: {cafes_a_describir}")
                contexto = obtener_cafes_por_nombre(cafes_a_describir, tostado=estado.metodo)
                estado.ultimos_cafes = cafes_a_describir
                estado.candidatos_actuales = []
                system_prompt = f"""
                                        Eres dueño y tostador de una cafeteria que vende su cafe. Conoces todo el ciclo de produccion, desde que te llega el grano verde, pasando por el tueste, las catas y el envasado. Tu tarea es describir ÚNICAMENTE los siguientes cafés: {", ".join(cafes_a_describir)}.

                                        No menciones ningún otro café que no esté en esta lista.

                                        INFORMACIÓN DE CADA CAFÉ (Origen, notas, cuerpo, acidez y recomendacion):
                                        {contexto}

                                        REGLAS DE FORMATO OBLIGATORIAS:
                                        1. Empieza la respuesta diciendo: Para {estado.metodo} te recomiendo:
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