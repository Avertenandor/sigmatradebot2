#!/usr/bin/env python3
"""Check for duplicate wallet addresses."""
import asyncio
import sys
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.config.settings import settings

async def check():
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.connect() as conn:
        result = await conn.execute(text(
            "SELECT wallet_address, COUNT(*) FROM users GROUP BY wallet_address HAVING COUNT(*) > 1"
        ))
        duplicates = result.fetchall()
        if duplicates:
            print(f"❌ Found {len(duplicates)} duplicate wallets:")
            for row in duplicates:
                print(f"  - {row[0]}: {row[1]} users")
        else:
            print("✅ No duplicate wallets found.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check())

