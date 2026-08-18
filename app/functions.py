import re
import unicodedata
import json

from openai import OpenAI
from typing import Optional
from app.config import OPENAI_API_KEY

from app.database import (
                        lista_metodos, 
                        lista_perfiles, 
                        palabras_espresso, 
                        palabras_filtro, 
                        intencion_metodo, 
                        intencion_perfil, 
                        lista_cafes,
                        intencion_faq,
                        intencion_descripcion,
                        intencion_compra,
                        intencion_saludo
)
from app.state import estado_usuario

# Cliente OpenAI (reutilizamos el mismo)
_openai_client = None


def get_openai_client():
    """
    Retorna el cliente de OpenAI, inicializándolo solo cuando se llama por primera vez.
    Esto evita errores de importación cuando no hay API key (ej. en el CI).
    """
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


def identificar_metodo(mensaje: str, session_id: str):
    if any(met in mensaje for met in lista_metodos):
        estado_usuario[session_id]["metodo"] = get_metodo(mensaje)
    elif any(phrase in mensaje for phrase in intencion_metodo):
        nuevo_metodo = get_metodo(mensaje, True)
        if nuevo_metodo is not None:
            estado_usuario[session_id]["metodo"] = nuevo_metodo
        

def identificar_perfil(mensaje: str, session_id: str):
    if any(per in mensaje for per in lista_perfiles):
        estado_usuario[session_id]["perfil"] = get_perfil(mensaje)
    elif any(intencion in mensaje for intencion in intencion_perfil):
        estado_usuario[session_id]["perfil"] = get_perfil(mensaje, True)
    
    
def get_metodo(mensaje: str, flag_ia: bool = False) -> Optional[str]:
    respuesta = ""
    if flag_ia:
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                        {
                            "role": "system",
                            "content": """
                                Eres un clasificador de intenciones experto en café de especialidad.
                                Analiza el mensaje del usuario y clasifícalo en una de las siguientes categorías:
                                - espresso: Si en el mensaje el usuario hace alusion a una maquina de espresso o si solo menciona alguna marca de cafetera:(ej:"De'Longhi", "Nespresso", "Breville", "La Marzocco", "Rocket", "Ninja", etc) 
                                - filtro: si el mensaje hace alusion a un metodo de filtrado(ej: "V60", "Chemex", "Prensa francesa", "AeroPress", "Clever Dripper") o marca de metodo de filtrado: (ej: "hario", "cafec", etc)
                                Si no encaja en ninguna de las categorias devuelve NONE
                            """,
                        },
                        {"role": "user", "content": mensaje}],
            temperature=0.5,
            max_tokens=20,
        )
        respuesta = response.choices[0].message.content
        print(f"Utilizando IA para detectar METODO! {respuesta}")
        if respuesta == "NONE":
            respuesta = None
        return respuesta
    if any(palabra in mensaje for palabra in palabras_espresso):
        respuesta = "espresso"
        return respuesta
    elif any(palabra in mensaje for palabra in palabras_filtro):
        respuesta = "filtro"
        return respuesta
    

def get_perfil(mensaje: str, flag_ia: bool = False) -> str:
    respuesta = ""
    if flag_ia:
        client = get_openai_client()
        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                            {
                                "role": "system",
                                "content": """
                                            Eres un clasificador de perfiles experto en café de especialidad.
                                            Analiza el mensaje del usuario y clasifícalo en una de las siguientes categorías:
                                            - tradicional: Sabores clásicos, achocolatados, nueces, caramelo. Acidez suave a media. Cuerpo meloso o jugoso. Ideal para quienes empiezan o buscan un espresso reconfortante. 
                                            - exotico: Sabores frutales (fresa, mango, mora), florales, cítricos. Acidez más marcada (málica, cítrica, tartárica). Cuerpo cremoso. Para paladares aventureros.
                                            - funky: Sabores licorosos, fermentados, frutas maduras, vino, mermelada. Acidez media a alta. Cuerpo cremoso. Para expertos.
                                            Solo responde con la categoria que corresponda, sino encaja en ninguna devuelve: ""
                                            """,
                            },
                            {"role": "user", "content": mensaje}],
                                temperature=0.5,
                                max_tokens=20,
                            )
        respuesta = response.choices[0].message.content
        print("Utilizando IA para detectar PERFIL!")
        return respuesta
    if any(palabra in mensaje for palabra in ["tradicional", "chocolat", "poca acidez", "clasico", "dulce"]):
        respuesta = "tradicional"
    elif any(palabra in mensaje for palabra in [ "exotic", "citrico", "floral", "citri", "frutal"]):
        respuesta = "exotico"
    elif any(palabra in mensaje for palabra in ["funky", "fanky", "fonky", "fermen","mucha acidez", "licor"]):
        respuesta = "funky"
    return respuesta


def recomendar_cafe(metodo: str, perfil: str, session_id: str = None) -> str:
    """Recomienda cafés según método y perfil, y opcionalmente guarda la lista en el estado"""
    matriz = {
        ("espresso", "tradicional"): ["Alacran", "Condor", "Lince", "Yurumi"],
        ("espresso", "exotico"): ["Dimeti", "Delfin Rosado", "Puma"],
        ("espresso", "funky"): ["Coyote"],
        ("filtro", "exotico"): ["Correcaminos", "Nebiri"],
    }
    cafes = matriz.get((metodo, perfil), [])

    # Guardar en el estado si se proporciona session_id
    if session_id and cafes:
        from app.state import estado_usuario

        estado_usuario[session_id]["ultimos_cafes"] = cafes

    return cafes


def describir_cafe(metodo: str, perfil: str, mensaje: str, ultimos_cafes:Optional[list])-> list:
    cafes_mencionados = []
    # PRIORIDAD 1: Usar los cafés ya fueron consultados
    for cafe in lista_cafes:
        cafe_normalizado = normalizar_texto(cafe)  # normaliza el cafe que coincidió para buscarlo en el mensaje pero agrega el cafe sin normalizar para la busqueda en el indice rag
        if cafe_normalizado in mensaje:
            cafes_mencionados.append(cafe)

    if cafes_mencionados:
        print(f"Usuario menciono especificamente{cafes_mencionados}")
        
    elif ultimos_cafes:
        cafes_mencionados = ultimos_cafes
        print("Usando ultimos cafes mencionados en la conversacion")

    # PRIORIDAD 2: Si no hay cafés guardados, usar la matriz según método+perfil
    elif metodo and perfil:
        cafes_mencionados = recomendar_cafe(metodo, perfil)
        print(f"   📌 Usando matriz de funcion recomendar_Cafe: {cafes_mencionados}")
    
    return cafes_mencionados


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
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ASCII", "ignore").decode("ASCII")

    # 3. Eliminar signos de puntuación y caracteres especiales
    #    Solo mantenemos letras, números y espacios
    texto = re.sub(r"[^a-z0-9\s]", "", texto)

    # 4. Eliminar espacios múltiples y trim
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto


def contains_any(text, terms):
    return any(
        re.search(rf"\b{re.escape(term)}\b", text)
        for term in terms
    )


def clasificar_intencion_simple(mensaje: str) -> str:
    
    user_norm = normalizar_texto(mensaje)
    if contains_any(user_norm, intencion_faq):
        return "intencion_faq"
    if contains_any(user_norm, intencion_descripcion):
        return "intencion_descripcion"
    if contains_any(user_norm, intencion_compra):
        return "intencion_compra"
    if user_norm in intencion_saludo:
        return "intencion_saludo"
    # No se pudo clasificar con reglas
    return None


async def clasificar_con_ia(mensaje: str) -> str:
    """
    Usa OpenAI con Salidas Estructuradas para clasificar mensajes sin errores de formato.
    """
    client = get_openai_client()

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """
                    Eres un clasificador de intenciones experto en café de especialidad.
                    Analiza el mensaje del usuario y clasifícalo en una de las siguientes categorías:

                    1. Clasifica como "intencion_compra" cuando el usuario quiere encontrar,
                        elegir o recibir una recomendación de café.

                        La intención de compra puede estar expresada de forma directa o indirecta.

                        Incluye mensajes donde el usuario:
                        - Solo menciona el perfil(tradicional, exotico o funky)
                        - Solo menciona el meotdo(espresso o filtro)
                        - Quiere comprar o elegir un café.
                        - Pide una recomendación de café.
                        - Indica que quiere café para una máquina de espresso.
                        - Indica que quiere café para un método de filtro.
                        - Indica un perfil de sabor que busca, como tradicional, exótico o funky.
                        - Describe sabores que le gustaría encontrar en el café, por ejemplo:
                          achocolatado, afrutado, floral, fermentado, tropical, dulce o cítrico.
                        - Dice que no sabe qué café elegir y pide ayuda.
                        - Busca un café adecuado para una determinada preparación.

                        Ejemplos:
                        - "Quiero comprar café"
                        - "¿Qué café me recomiendas?"
                        - "Tengo una máquina de espresso"
                        - "Tengo una maquina (menciona alguna marca)"
                        - "Busco un café para V60"
                        - "Quiero algo tradicional"
                        - "Quiero un café exótico"
                        - "Quiero algo funky"
                        - "Busco un café achocolatado"
                        - "Quiero un café fermentado"
                        - "No sé cuál elegir"

                        NO clasifiques como "intencion_compra" si el usuario simplemente
                        quiere conocer las características de un café concreto.

                        Ejemplos que NO pertenecen:
                        - "Descríbeme el Alacrán"
                        - "¿Qué origen tiene el Cóndor?"
                        - "¿Qué notas tiene este café?"
                        
                    2. Clasifica como "intencion_descripcion" cuando el usuario quiere
                        obtener información sobre las características de uno o varios cafés,
                        sin estar pidiendo principalmente una recomendación.

                        Incluye preguntas sobre:
                        - Descripción de un café concreto.
                        - Origen.
                        - País o región.
                        - Variedad.
                        - Proceso.
                        - Notas de cata.
                        - Perfil de sabor.
                        - Acidez.
                        - Cuerpo.
                        - Dulzor.
                        - Características generales de uno o varios cafés.
                        - Comparaciones entre cafés cuando el objetivo es conocer sus características.

                        Ejemplos:
                        - "Descríbeme el Alacrán"
                        - "¿Qué origen tiene el Cóndor?"
                        - "¿Qué notas tiene este café?"
                        - "¿Cómo es el Alacrán?"
                        - "¿De dónde viene este café?"
                        - "¿Qué proceso tiene el Cóndor?"
                        - "¿Puedes describirme esos cafés?"
                        - "¿Cuál es la diferencia entre el Alacrán y el Cóndor?"

                        NO clasifiques como "intencion_descripcion" cuando el usuario
                        está buscando que le recomiendes un café según sus gustos,
                        método de preparación o perfil.

                        Ejemplos que NO pertenecen:
                        - "Quiero un café achocolatado"
                        - "¿Qué café me recomiendas?"
                        - "Tengo una V60, ¿qué café debería comprar?"
                        
                    4. Clasifica como "intencion_faq" cuando el usuario haga una pregunta
                        general relacionada con el café, su preparación, sus características,
                        sus procesos o sus métodos, y no esté preguntando específicamente
                        por las características de un café concreto.

                        Esta intención incluye preguntas que permitan orientar al usuario
                        sobre nuestros cafés, perfiles o métodos de preparación.

                        Incluye preguntas sobre:

                        1. ACIDEZ DEL CAFÉ
                        - Qué cafés son más ácidos.
                        - Qué perfiles tienen mayor acidez.
                        - Qué cafés tienen una acidez más marcada.
                        - Qué significa que un café sea ácido.
                        - Qué diferencia hay entre un café ácido y uno suave.
                        - Qué cafés tienen una acidez parecida a frutas cítricas.
                        - Busco un café con mucha acidez.
                        - ¿Qué café debería probar si me gustan los cafés ácidos?

                        En estos casos, puedes orientar al usuario hacia perfiles
                        EXÓTICOS o FUNKY cuando corresponda.
                        Los cafés FUNKY pueden presentar una acidez y fermentación
                        especialmente marcadas.

                        2. PROCESOS DEL CAFÉ
                        Incluye preguntas sobre procesos como:
                        - Lavado / lavado tradicional.
                        - Natural.
                        - Honey.
                        - Fermentación.
                        - Fermentación anaeróbica.
                        - Fermentación controlada.
                        - Fermentaciones prolongadas.
                        - Diferencias entre procesos.
                        - Cómo influye el proceso en el sabor.
                        - Qué proceso produce cafés más afrutados.
                        - Qué proceso produce cafés más dulces.
                        - Qué proceso puede generar notas más fermentadas o funky.

                        Ejemplos:
                        - ¿Qué diferencia hay entre un café lavado y uno natural?
                        - ¿Qué es un café fermentado?
                        - ¿Cómo afecta la fermentación al sabor?
                        - ¿Qué proceso hace que el café sea más afrutado?
                        - ¿Qué significa que un café sea anaeróbico?
                        - ¿Los cafés naturales son más dulces?
                        - ¿Qué proceso da más acidez?

                        3. MÉTODOS DE PREPARACIÓN
                        Incluye preguntas generales sobre métodos de preparación:
                        - Espresso.
                        - V60.
                        - Chemex.
                        - Aeropress.
                        - Prensa francesa.
                        - Filtro en general.

                        Ejemplos:
                        - ¿Qué diferencia hay entre espresso y filtro?
                        - ¿Qué método resalta más la acidez?
                        - ¿Qué método resalta más los sabores frutales?
                        - ¿Qué método produce más cuerpo?
                        - ¿Qué método debería utilizar para apreciar mejor un café exótico?

                        4. CARACTERÍSTICAS GENERALES DEL CAFÉ
                        Incluye preguntas sobre:
                        - Acidez.
                        - Dulzor.
                        - Cuerpo.
                        - Intensidad.
                        - Aroma.
                        - Notas de cata.
                        - Tostado.
                        - Diferencias entre perfiles tradicionales, exóticos y funky.

                        Ejemplos:
                        - ¿Qué significa que un café tenga mucho cuerpo?
                        - ¿Qué diferencia hay entre intensidad y acidez?
                        - ¿Por qué algunos cafés saben a frutas?
                        - ¿Por qué algunos cafés tienen notas de chocolate?
                        - ¿Qué hace que un café sea funky?
                        - ¿Qué diferencia hay entre un café tradicional y uno exótico?

                        NO clasifiques como "intencion_faq" cuando el usuario pregunte
                        específicamente por las características de un café concreto.

                        Ejemplos:
                        - "¿Qué notas tiene el Alacrán?" → intencion_descripcion
                        - "¿De dónde viene el Cóndor?" → intencion_descripcion
                        - "Descríbeme el Alacrán" → intencion_descripcion

                        Tampoco clasifiques como "intencion_faq" cuando el usuario
                        simplemente quiera que le recomiendes un café según sus gustos.

                        Ejemplos:
                        - "Quiero un café achocolatado" → intencion_compra
                        - "Quiero un café exótico" → intencion_compra
                        - "¿Qué café me recomiendas?" → intencion_compra
                        - "Tengo una V60, ¿qué café me recomiendas?" → intencion_compra
                        
                    3. Clasifica como "intencion_saludo" cuando el mensaje sea únicamente
                        un saludo, agradecimiento o despedida y no contenga otra intención
                        relacionada con el café o la tienda.

                        Incluye:
                        - Saludos.
                        - Agradecimientos.
                        - Despedidas.
                        - Expresiones breves de cortesía.

                        Ejemplos:
                        - "Hola"
                        - "Buenas"
                        - "Hola, ¿qué tal?"
                        - "Gracias"
                        - "Muchas gracias"
                        - "Perfecto, gracias"
                        - "Adiós"
                        - "Hasta luego"
                        - "Nos vemos"

                        Si el mensaje contiene una petición además del saludo,
                        clasifícalo según la intención de la petición.

                        Ejemplos:
                        - "Hola, ¿qué café me recomiendas?" → intencion_compra
                        - "Buenas, ¿qué origen tiene el Alacrán?" → intencion_descripcion
                    
                    4. Utiliza "fallback" cuando el mensaje no corresponda
                        a ninguna de las intenciones anteriores o esté fuera
                        del ámbito del asistente. 
                        Ejemplos
                        - "Messi"
                        - "Que hora es?
                        - "Hara buen clima mañana?
                    Devuelve únicamente JSON con este formato:

                    {
                        "intent": "string",
                        "confidence": 0.0
                    }

                    La confidence debe estar entre 0 y 1.

                    Utiliza:
                    - 0.90 - 1.00: intención muy clara
                    - 0.75 - 0.89: intención bastante clara
                    - 0.50 - 0.74: intención ambigua
                    - 0.00 - 0.49: intención muy incierta
                    
                """,
            },
            {"role": "user", "content": mensaje},
        ],
        temperature=0.5,
    )

    # La IA garantiza devolver uno de los strings definidos en el Literal
    clasificacion = response.choices[0].message.content
    datos = json.loads(clasificacion)
    intent = datos["intent"]
    print(datos)
    if datos["confidence"] < 75 and datos["confidence"] > 50:
        intent = "intencion_compra"
    return intent
