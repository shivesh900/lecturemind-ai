"""Create MongoDB indexes (also done automatically on API startup).

Usage (from backend/):  python -m scripts.init_db
"""
import asyncio

from app.core.config import get_settings
from app.core.database import INDEXES, close_db, get_db, init_indexes


async def main():
    s = get_settings()
    db = get_db()
    await db.command("ping")
    await init_indexes(db)
    print(f"Connected to {s.mongodb_db}. Indexes ensured on: {', '.join(INDEXES)}")
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
