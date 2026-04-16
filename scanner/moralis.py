import aiohttp
import logging
from config import ALCHEMY_API_KEY

logger = logging.getLogger(__name__)

# Chain -> Alchemy network subdomain
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


def _base_url(chain: str) -> str | None:
    network = ALCHEMY_NETWORK_MAP.get(chain)
    if not network:
        return None
    return f"https://{network}.g.alchemy.com/nft/v3/{ALCHEMY_API_KEY}"


async def _fetch(url: str, params: dict) -> list:
    headers = {"accept": "application/json"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("nftTransfers", [])
                else:
                    text = await resp.text()
                    logger.warning(f"Alchemy {resp.status}: {text[:200]}")
                    return []
    except Exception as e:
        logger.error(f"Alchemy request error: {e}")
        return []


async def get_wallet_transfers(address: str, chains: list, limit: int = 25) -> list:
    """Fetch recent NFT transfers for a wallet across multiple chains."""
    all_transfers = []

    for chain in chains:
        base = _base_url(chain)
        if not base:
            continue

        url = f"{base}/getTransfersForOwner"

        # Отримуємо вхідні (mint/buy) та вихідні (sell) окремо
        for transfer_type in ("TO", "FROM"):
            transfers = await _fetch(url, {
                "owner": address,
                "transferType": transfer_type,
                "pageSize": limit,
                "withMetadata": "true",
            })
            for t in transfers:
                t["_chain"] = chain
            all_transfers.extend(transfers)

    return all_transfers


def parse_transfer(transfer: dict, wallet_address: str) -> dict | None:
    """Parse an Alchemy NFT transfer into a clean event dict."""
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

        nft_name = (
            transfer.get("title")
            or transfer.get("tokenName")
            or "Unknown NFT"
        )

        # ERC1155 може мати кілька токенів в одній транзакції
        erc1155 = transfer.get("erc1155Metadata") or []
        quantity = sum(int(m.get("value", 1)) for m in erc1155) if erc1155 else 1

        chain = transfer.get("_chain") or ""
        tx_hash = transfer.get("hash") or ""
        token_id = str(transfer.get("tokenId") or "")
        contract_address = transfer.get("contractAddress") or ""

        # Час транзакції
        metadata = transfer.get("metadata") or {}
        block_timestamp = metadata.get("blockTimestamp") or ""

        return {
            "event_type": event_type,
            "nft_name": nft_name,
            "collection_name": nft_name,
            "price": None,
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
