import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.getcwd())

from app.core.database import AsyncSessionLocal
from sqlalchemy import text

async def patch():
    print("Patching DB...")
    async with AsyncSessionLocal() as session:
        try:
            # using 'json' type for compatibility
            await session.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS hot_words json DEFAULT '[\"help\", \"bachao\", \"save me\", \"police\"]'"))
            await session.commit()
            print("✅ Column hot_words added.")
        except Exception as e:
            print(f"❌ Error: {e}")
            await session.rollback()

if __name__ == "__main__":
    asyncio.run(patch())
