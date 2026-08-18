import aiosqlite
import asyncpg
from typing import List
from app.config import DATABASE_URL

#lista_cafes: List[str] = [
#                           "Anaerobic natural", 
#                         "Black honey", 
#                         "Cerro azul", 
#                         "Decaf Honey", 
#                          "El Obraje", 
#                          "Finca Las Mercedes", 
 #                           "Gesha village", 
 #                           "Granito de oro", 
 #                           "Honey java", 
 #                           "La loma",
 #                           "Maracaturra",
 #                           "Montecarlo",
 #                           "Natural gesha",
 #                           "Natural limau",
 #                           "Organic SHB",
 #                           "Peaberry de Kenia",
 #                           "Sidra del ecuador",
 #                           "Tropical natural",
 #                           "Washed geisha"
 #                       ]

lista_cafes: List[str] = [
    "Alacrán", "Cóndor", "Lince", "Yurumi", "Dimeti", "Delfin Rosado", "Puma", "Coyote","Correcaminos", "Nebiri"
]

intencion_metodo: List[str] = [
                            "utilizo",
                            "uso",
                            "tengo una",
                            "preparo",
                            "cafetera",
                            "maquina",
                            "de brazo",
                            "de maneral",
                            "portafiltro",
                            "maquinita",
                            "para mi"
                        ]

lista_metodos: List[str] = [
                            "automatica",
                            "semiautomatica",
                            "superautomatica",
                            "espresso",
                            "espreso",
                            "expresso" ,
                            "expreso", 
                            "filtro",
                            "filtrado",
                            "filter",
                            "v60",
                            "chemex",
                            "moka",
                            "aeropress",
                            "italiana",
                            "marzocco", 
                            "rocket",
                            "krups",
                            "jura",
                            "saeco",
                            "breville",
                            "gaggia",
                            "nespresso",
                            "lavaz",
                            "philips",
                            "ecm",
                            "delonghi",
                            "lelit",
                            "rancilio",
                            "sage",
                            "oscar",
                            "simonelli",
                            "flair",
                            "miele",
                            "cafelat",
                            "pavoni", 
                            "hario", 
                            "kalita", 
                            "melitta",
                            "goteo", 
                            "chemex", 
                            "moccamaster", 
                            "origami", 
                            "fellow"
                        ]

palabras_espresso: List[str] = [
                                "espresso",
                                "espreso",
                                "expresso",
                                "expres",
                                "automatica",
                                "semiautomatica",
                                "superautomatica",
                                "marzocco",
                                "rocket",
                                "krups",
                                "jura",
                                "saeco",
                                "breville",
                                "gaggia",
                                "nespresso",
                                "lavazza",
                                "philips",
                                "ecm",
                                "delonghi",
                                "lelit",
                                "rancilio",
                                "sage",
                                "oscar",
                                "simonelli",
                                "flair",
                                "miele",
                                "cafelat",
                                "pavoni", 
                            ]

palabras_filtro: List[str] = [
                                "filtro",
                                "filtrado",
                                "filter",
                                "v60",
                                "chemex",
                                "moka",
                                "goteo",
                                "aeropres",
                                "la italiana",
                                "hario", 
                                "kalita", 
                                "melitta", 
                                "chemex", 
                                "camaster", 
                                "origami", 
                                "fellow"                        
]

intencion_perfil: List[str] = [
                               "tradicional",
                               "exotico",
                               "funky",
                               "notas",
                               "sabor",
                               "cuerpo",
                               "huelen",
                               "olor",
                               "que sepa",
                               "perfil",
                               "intenso",
                               "con mucha",
                               "con mucho",
                               "con poca",
                               "acidez"
                            ]

lista_perfiles: List[str] = [
                             "tradicional",
                             "clasico",
                             "dulce",
                             "chocola",
                             "poca acidez",
                             "frutal", 
                             "citrico",
                             "floral",
                             "mucha acidez",
                             "fermentado",
                             "licoroso",
                             "exotico",
                             "fanky",
                             "funky",
                             "fonky",
                          ]

intencion_faq: List[str] = [
                            "sca",
                            "puntos sca",
                            "puntuacion sca",
                            "variedad",
                            "variedades",
                            "proceso",
                            "procesos",
                            "lavado",
                            "natural",
                            "naturales",
                            "honey",
                            "fermentado",
                            "fermentacion",
                            "tostado",
                            "tueste",
                            "cuerpo",
                            "acidez",
                            "dulzor",
                            "amargor",
                            "altitud",
                            "altura",
                            "terroir",
                            "catacion",
                            "cata",
                            "extraccion",
                            "molienda",
                            "moler",
                            "ratio",
                            "temperatura",
                            "bloom",
                            "preinfusion"
]

intencion_descripcion: List[str] = [
                            "describeme",
                            "descripcion",
                            "caracteristicas del cafe",
                            "notas del cafe",
                            "perfil del cafe",
                            "a que sabe",
                            "como sabe",
                            "que sabores tiene",
                            "que notas tiene"
]

intencion_compra: List[str] = [
                                "recomiendame",
                                "que cafe me recomiendas",
                                "quiero un cafe",
                                "busco un cafe",
                                "me gustaria un cafe",
                                "quiero comprar",
                                "que cafe compro",
                                "cual me recomiendas",
                                "cual elegir"
]

intencion_saludo: List[str] = [
                                "hola",
                                "buenos dias",
                                "buenas tardes",
                                "buenas noches",
                                "adios",
                                "chao",
                                "hasta luego",
                                "bye",
                                "gracias",
                                "muchas gracias",
                                "listo"
]

async def check_connection():
    """Verifica que la conexión a la base de datos está activa."""
    # Lógica simple para probar la conexión
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.close()
    return True


async def init_db():
    flag = 0
    if DATABASE_URL.startswith("postgresql"):
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_session ON conversations(session_id)"
        )
        flag = 1
        await conn.close()
    else:
        async with aiosqlite.connect(DATABASE_URL) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_session ON conversations(session_id)"
            )
            flag = 2
    print(f"✅ Base de datos inicializada {flag}")


async def save_message(session_id: str, role: str, content: str):
    if DATABASE_URL.startswith("postgresql"):
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        await conn.execute(
            "INSERT INTO conversations (session_id, role, content) VALUES ($1, $2, $3)",
            session_id,
            role,
            content,
        )
        await conn.close()
    else:
        async with aiosqlite.connect(DATABASE_URL) as db:
            await db.execute(
                "INSERT INTO conversations (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content),
            )
            await db.commit()


async def get_conversation_history(session_id: str, limit: int = 10):
    if DATABASE_URL.startswith("postgresql"):
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        rows = await conn.fetch(
            "SELECT role, content FROM conversations WHERE session_id = $1 ORDER BY created_at ASC LIMIT $2",
            session_id,
            limit,
        )
        await conn.close()
        return [{"role": row["role"], "content": row["content"]} for row in rows]
    else:
        async with aiosqlite.connect(DATABASE_URL) as db:
            async with db.execute(
                "SELECT role, content FROM conversations WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
                (session_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [{"role": row[0], "content": row[1]} for row in rows]
