import aiohttp
import logging
from config import ALCHEMY_API_KEY

logger = logging.getLogger(__name__)

# Chain -> Alchemy network subdomain (всі використовують один API ключ)
ALCHEMY_NETWORK_MAP = {
    "ethereum": "eth-mainnet",
    "base":     "base-mainnet",
    "arbitrum": "arb-mainnet",
    "bsc":      None,  # Alchemy не підтримує BSC
    "abstract": None,
    "megaeth":  None,
    "tempo":    None,
}

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


def _rpc_url(chain: str) -> str | None:
    network = ALCHEMY_NETWORK_MAP.get(chain)
    if not network:
        return None
    return f"https://{network}.g.alchemy.com/v2/{ALCHEMY_API_KEY}"


async def _asset_transfers(url: str, address: str, direction: str, limit: int) -> list:
    """Отримати NFT трансфери через alchemy_getAssetTransfers (JSON-RPC)."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "alchemy_getAssetTransfers",
        "params": [{
            f"{direction}Address": address,
            "fromBlock": "0x0",
            "toBlock": "latest",
            "category": ["erc721", "erc1155"],
            "maxCount": hex(limit),
            "withMetadata": True,
            "order": "desc",
        }]
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return (data.get("result") or {}).get("transfers", [])
                else:
                    text = await resp.text()
                    logger.warning(f"Alchemy {resp.status} ({direction}): {text[:200]}")
                    return []
    except Exception as e:
        logger.error(f"Alchemy request error: {e}")
        return []


async def get_wallet_transfers(address: str, chains: list, limit: int = 20) -> list:
    """Отримати всі NFT трансфери гаманця по всіх мережах."""
    all_transfers = []

    for chain in chains:
        url = _rpc_url(chain)
        if not url:
            continue

        # Вхідні (mint/buy) + вихідні (sell)
        for direction in ("to", "from"):
            transfers = await _asset_transfers(url, address, direction, limit)
            for t in transfers:
                t["_chain"] = chain
            all_transfers.extend(transfers)

    return all_transfers


def parse_transfer(transfer: dict, wallet_address: str) -> dict | None:
    """Перетворити Alchemy трансфер на зручний словник."""
    try:
        from_addr = (transfer.get("from") or "").lower()
        to_addr = (transfer.get("to") or "").lower()
        wallet = wallet_address.lower()

        if from_addr == ZERO_ADDRESS:
            event_type = "mint"
        elif to_addr == wallet:
            event_type = "buy"
        elif from_addr == wallet:
            event_type = "sell"
        else:
            return None

        nft_name = transfer.get("asset") or "Unknown NFT"

        # ERC1155 метадані
        erc1155 = transfer.get("erc1155Metadata") or []
        quantity = sum(int(m.get("value", "0x1"), 16) for m in erc1155) if erc1155 else 1

        # Token ID: для ERC721 — з tokenId, для ERC1155 — з erc1155Metadata
        raw_id = (
            transfer.get("tokenId")
            or transfer.get("erc721TokenId")
            or (erc1155[0].get("tokenId") if erc1155 else None)
            or ""
        )
        try:
            token_id = str(int(raw_id, 16)) if str(raw_id).startswith("0x") else str(raw_id)
        except (ValueError, AttributeError):
            token_id = str(raw_id)

        contract_address = (transfer.get("rawContract") or {}).get("address") or ""

        # Ціна в ETH
        value = transfer.get("value")
        price = float(value) if value else None

        chain = transfer.get("_chain") or ""
        tx_hash = transfer.get("hash") or ""

        # Час транзакції
        metadata = transfer.get("metadata") or {}
        block_timestamp = metadata.get("blockTimestamp") or ""

        return {
            "event_type": event_type,
            "nft_name": nft_name,
            "collection_name": nft_name,
            "price": price,
            "symbol": "ETH",
            "marketplace": "",
            "chain": chain,
            "tx_hash": tx_hash,
            "token_id": token_id,
            "quantity": quantity,
            "contract_address": contract_address,
            "block_timestamp": block_timestamp,
        }
    except Exception as e:
        logger.error(f"Error parsing Alchemy transfer: {e}")
        return None
