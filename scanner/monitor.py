import asyncio
import logging
from datetime import datetime, timezone, timedelta
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter

from db.database import get_all_wallets, is_tx_seen, mark_tx_seen, cleanup_old_txs
from scanner.moralis import get_wallet_transfers, parse_transfer
from bot.messages import format_alert

MAX_TX_AGE_DAYS = 7

logger = logging.getLogger(__name__)


async def scan_wallets(bot: Bot):
    """Fetch new NFT transfers for all watched wallets and send alerts."""
    wallets = await get_all_wallets()
    if not wallets:
        return

    # Group wallets by address to avoid duplicate API calls when multiple
    # users track the same address.
    addr_map: dict[str, dict] = {}
    for w in wallets:
        addr = w["address"].lower()
        chains = [c.strip() for c in w["chains"].split(",") if c.strip()]
        if addr not in addr_map:
            addr_map[addr] = {"chains": set(), "users": []}
        addr_map[addr]["chains"].update(chains)
        addr_map[addr]["users"].append({"user_id": w["user_id"], "name": w["name"]})

    for address, data in addr_map.items():
        try:
            transfers = await get_wallet_transfers(address, list(data["chains"]))

            for transfer in transfers:
                tx_hash = transfer.get("hash") or ""
                chain = transfer.get("_chain") or ""

                if not tx_hash or not chain:
                    continue

                # Пропускаємо транзакції старші за MAX_TX_AGE_DAYS
                raw_ts = (transfer.get("metadata") or {}).get("blockTimestamp") or ""
                if raw_ts:
                    try:
                        tx_time = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                        if datetime.now(timezone.utc) - tx_time > timedelta(days=MAX_TX_AGE_DAYS):
                            await mark_tx_seen(address, tx_hash, chain)
                            continue
                    except Exception:
                        pass

                if await is_tx_seen(address, tx_hash, chain):
                    continue

                await mark_tx_seen(address, tx_hash, chain)

                parsed = parse_transfer(transfer, address)
                if not parsed:
                    continue

                for user in data["users"]:
                    await _send_alert(bot, user["user_id"], parsed, user["name"] or address)
                    await asyncio.sleep(0.5)  # затримка між повідомленнями

        except Exception as e:
            logger.error(f"Error scanning wallet {address}: {e}")

    await cleanup_old_txs()


async def _send_alert(bot: Bot, user_id: int, event: dict, wallet_name: str):
    text = format_alert(event, wallet_name)
    for attempt in range(3):
        try:
            await bot.send_message(
                user_id,
                text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return
        except TelegramRetryAfter as e:
            wait = e.retry_after + 1
            logger.warning(f"Flood control, чекаємо {wait}с...")
            await asyncio.sleep(wait)
        except TelegramForbiddenError:
            logger.info(f"Користувач {user_id} заблокував бота")
            return
        except TelegramBadRequest as e:
            logger.warning(f"Bad request для {user_id}: {e}")
            return
        except Exception as e:
            logger.error(f"Помилка відправки для {user_id}: {e}")
            return


async def start_monitor(bot: Bot, interval: int = 60):
    """Run the scanning loop forever with the given interval (seconds)."""
    logger.info(f"NFT monitor started (interval={interval}s)")
    while True:
        try:
            await scan_wallets(bot)
        except Exception as e:
            logger.error(f"Monitor loop error: {e}")
        await asyncio.sleep(interval)
