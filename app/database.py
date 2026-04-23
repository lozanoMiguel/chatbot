import aiosqlite
import asyncpg
from app.config import DATABASE_URL

async def init_db():
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
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON conversations(session_id)")
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
            await db.execute("CREATE INDEX IF NOT EXISTS idx_session ON conversations(session_id)")
    print("✅ Base de datos inicializada")

async def save_message(session_id: str, role: str, content: str):
    if DATABASE_URL.startswith("postgresql"):
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        await conn.execute(
            "INSERT INTO conversations (session_id, role, content) VALUES ($1, $2, $3)",
            session_id, role, content
        )
        await conn.close()
    else:
        async with aiosqlite.connect(DATABASE_URL) as db:
            await db.execute(
                "INSERT INTO conversations (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content)
            )
            await db.commit()

async def get_conversation_history(session_id: str, limit: int = 10):
    if DATABASE_URL.startswith("postgresql"):
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        rows = await conn.fetch(
            "SELECT role, content FROM conversations WHERE session_id = $1 ORDER BY created_at ASC LIMIT $2",
            session_id, limit
        )
        await conn.close()
        return [{"role": row["role"], "content": row["content"]} for row in rows]
    else:
        async with aiosqlite.connect(DATABASE_URL) as db:
            async with db.execute(
                "SELECT role, content FROM conversations WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
                (session_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                return [{"role": row[0], "content": row[1]} for row in rows]