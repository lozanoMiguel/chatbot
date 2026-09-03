from typing import List

import aiosqlite
import asyncpg

from app.config import DATABASE_URL
_pool: asyncpg.Pool | None = None


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

seniales_listado:List[str] = [
                        "cuales son los cafes",
                        "que cafes",
                        "cafes de",
                        "cafes con",
                        "cafes mas",
                        "cafes menos"
]

seniales_ranking:List[str] = [
                                " mejor ", 
                                " peor ", 
                                " mayor ", 
                                " menor ", 
                                "top ", 
                                "ranking"
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

intencion_recomendacion: List[str] = [
                                #"recomiendame",
                                #"que cafe me recomiendas",
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



 
 
async def get_pool() -> asyncpg.Pool:
    """
    Crea el pool UNA sola vez y lo reutiliza en todas las funciones
    siguientes, en vez de abrir/cerrar una conexión nueva en cada una
    (que era lo que agotaba las conexiones disponibles de Supabase).
    """
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            statement_cache_size=0,  # necesario por el pooler de Supabase (pgbouncer en modo transacción)
            min_size=1,
            max_size=6,
        )
    return _pool
 
 
async def close_pool():
    """Cierra el pool limpiamente al apagar el servidor."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
 
 
async def init_db():
    flag = 0
    if DATABASE_URL.startswith("postgresql"):
        pool = await get_pool()  # crea el pool (si no existe) y lo reutiliza
        await pool.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await pool.execute(
            "CREATE INDEX IF NOT EXISTS idx_session ON conversations(session_id)"
        )
        flag = 1
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
    """
    Devuelve los últimos `limit` mensajes de la sesión, en orden
    cronológico (del más antiguo al más reciente) — listos para pasarle
    a clasificar_con_ia() como contexto acotado.
 
    Usa `id` (serial, autoincremental) en vez de `created_at` para el
    orden: created_at puede tener timestamps duplicados si dos mensajes
    se insertan muy rápido, mientras que `id` es siempre estrictamente
    secuencial y refleja el orden real de inserción sin ambigüedad.
    """
    if DATABASE_URL.startswith("postgresql"):
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        rows = await conn.fetch(
            """
            SELECT role, content FROM (
                SELECT role, content, id FROM conversations
                WHERE session_id = $1
                ORDER BY id DESC
                LIMIT $2
            ) sub
            ORDER BY id ASC
            """,
            session_id,
            limit,
        )
        await conn.close()
        return [{"role": row["role"], "content": row["content"]} for row in rows]
    else:
        async with aiosqlite.connect(DATABASE_URL) as db:
            async with db.execute(
                """
                SELECT role, content FROM (
                    SELECT role, content, id FROM conversations
                    WHERE session_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                )
                ORDER BY id ASC
                """,
                (session_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [{"role": row[0], "content": row[1]} for row in rows]
