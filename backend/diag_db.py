import asyncio
import os
import sys
from sqlalchemy import text
from database import SessionLocal

async def audit_products():
    async with SessionLocal() as db:
        result = await db.execute(text("SELECT * FROM products"))
        keys = result.keys()
        rows = result.fetchall()
        print(f"Audit of {len(rows)} products:")
        for row in rows:
            data = dict(zip(keys, row))
            print(f"Product ID: {data.get('id')}")
            for k, v in data.items():
                print(f"  {k}: {v} ({type(v)})")
            print("-" * 20)

if __name__ == "__main__":
    asyncio.run(audit_products())
