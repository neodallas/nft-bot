import aiosqlite
from config import DATABASE_PATH


async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                address TEXT NOT NULL,
                name TEXT,
                chains TEXT DEFAULT 'ethereum',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (user_id, address)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS seen_txs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address TEXT NOT NULL,
                tx_hash TEXT NOT NULL,
                chain TEXT NOT NULL,
                seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (wallet_address, tx_hash, chain)
            )
        """)
        await db.commit()


async def add_wallet(user_id: int, address: str, name: str, chains: str = "ethereum") -> bool:
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                "INSERT INTO wallets (user_id, address, name, chains) VALUES (?, ?, ?, ?)",
                (user_id, address.lower(), name, chains)
            )
            await db.commit()
            return True
    except aiosqlite.IntegrityError:
        return False


async def remove_wallet(user_id: int, address: str) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM wallets WHERE user_id = ? AND address = ?",
            (user_id, address.lower())
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_user_wallets(user_id: int) -> list:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM wallets WHERE user_id = ? ORDER BY created_at",
            (user_id,)
        )
        return await cursor.fetchall()


async def count_user_wallets(user_id: int) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM wallets WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        return row[0]


async def update_wallet_chains(user_id: int, address: str, chains: str) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "UPDATE wallets SET chains = ? WHERE user_id = ? AND address = ?",
            (chains, user_id, address.lower())
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_all_wallets() -> list:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM wallets")
        return await cursor.fetchall()


async def is_tx_seen(wallet_address: str, tx_hash: str, chain: str) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM seen_txs WHERE wallet_address = ? AND tx_hash = ? AND chain = ?",
            (wallet_address.lower(), tx_hash, chain)
        )
        return await cursor.fetchone() is not None


async def mark_tx_seen(wallet_address: str, tx_hash: str, chain: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO seen_txs (wallet_address, tx_hash, chain) VALUES (?, ?, ?)",
            (wallet_address.lower(), tx_hash, chain)
        )
        await db.commit()


async def seed_seen_txs(wallet_address: str, transfers: list):
    """Mark all existing transactions as seen (called when wallet is first added)."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        for t in transfers:
            tx_hash = t.get("transaction") or ""
            chain = t.get("chain") or ""
            if tx_hash and chain:
                await db.execute(
                    "INSERT OR IGNORE INTO seen_txs (wallet_address, tx_hash, chain) VALUES (?, ?, ?)",
                    (wallet_address.lower(), tx_hash, chain)
                )
        await db.commit()


async def cleanup_old_txs():
    """Keep only last 7 days of seen txs to prevent DB bloat."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM seen_txs WHERE seen_at < datetime('now', '-7 days')"
        )
        await db.commit()
