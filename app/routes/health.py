from fastapi import APIRouter, HTTPException
from app.database import DATABASE_URL
from app.config import OPENAI_API_KEY
from app.functions import get_openai_client
import asyncpg
import aiosqlite

router = APIRouter()

@router.get("/health")
async def health_check():
    db_status = "connected"
    try:
        if DATABASE_URL.startswith("postgresql"):
            conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
            await conn.close()
        else:
            async with aiosqlite.connect(DATABASE_URL) as db:
                await db.execute("SELECT 1")
    except Exception:
        db_status = "disconnected"

    llm_status = "connected"
    if OPENAI_API_KEY and not OPENAI_API_KEY.startswith("sk-test"):
        try:
            client = get_openai_client()
            client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5,
            )
        except Exception:
            llm_status = "disconnected"
    else:
        llm_status = "not configured"

    overall_status = (
        "ok" if db_status == "connected" and llm_status == "connected" else "degraded"
    )

    return {
        "status": overall_status,
        "database": db_status,
        "llm": llm_status,
        "version": "1.0.0",
    }
