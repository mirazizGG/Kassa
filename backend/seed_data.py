import asyncio
from sqlalchemy import select
from database import SessionLocal, Product, Category, init_db

async def seed_data():
    await init_db()
    async with SessionLocal() as db:
        # Check if categories exist
        result = await db.execute(select(Category))
        categories = result.scalars().all()
        if not categories:
            print("Creating categories...")
            c1 = Category(name="Ichimliklar")
            c2 = Category(name="Oziq-ovqat")
            db.add_all([c1, c2])
            await db.commit()
            categories = [c1, c2]

        # Check if products exist
        result = await db.execute(select(Product))
        products = result.scalars().all()
        if not products:
            print("Creating mock products...")
            p1 = Product(
                name="Coca-Cola 1.5L",
                barcode="123456",
                buy_price=8000,
                sell_price=12000,
                stock=50,
                unit="dona",
                category_id=categories[0].id
            )
            p2 = Product(
                name="Non",
                barcode="111",
                buy_price=2000,
                sell_price=3000,
                stock=100,
                unit="dona",
                category_id=categories[1].id
            )
            db.add_all([p1, p2])
            await db.commit()
            print("Done.")

if __name__ == "__main__":
    asyncio.run(seed_data())
