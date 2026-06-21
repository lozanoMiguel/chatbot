# test_db.py
import asyncio

import asyncpg

DATABASE_URL = "postgresql://postgres.eegvfklfiwqdyujdzmvu:6j%23Vr4fX%257yX_fY@aws-0-eu-west-1.pooler.supabase.com:6543/postgres?sslmode=require"


async def test():
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        print("✅ Conexión exitosa a Supabase desde LOCAL")
        await conn.close()
    except Exception as e:
        print(f"❌ Error de conexión: {e}")


asyncio.run(test())
