import aiohttp
import logging
from config import MORALIS_API_KEY

logger = logging.getLogger(__name__)

MORALIS_BASE = "https://deep-index.moralis.io/api/v2.2"

# Internal chain ID -> Moralis chain param
MORALIS_CHAIN_MAP = {
    "ethereum": "eth",
    "base": "base",
    "arbitrum": "arbitrum",
    "bsc": "bsc",
}

# Chains not yet supported by Moralis
UNSUPPORTED_CHAINS = {"abstract", "megaeth", "tempo"}

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


async def get_wallet_transfers(address: str, chains: list, limit: int = 20) -> list:
    """Fetch recent NFT transfers for a wallet across multiple chains."""
    all_transfers = []

    for chain in chains:
        if chain in UNSUPPORTED_CHAINS:
            continue

        moralis_chain = MORALIS_CHAIN_MAP.get(chain, chain)
        url = f"{MORALIS_BASE}/wallets/{address}/nfts/transfers"
        params = {
            "chain": moralis_chain,
            "limit": limit,
            "order": "DESC",
        }
        headers = {
            "X-API-Key": MORALIS_API_KEY,
            "accept": "application/json",
        }

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
                        transfers = data.get("result", [])
                        for t in transfers:
                            t["_chain"] = chain
                        all_transfers.extend(transfers)
                    else:
                        text = await resp.text()
                        logger.warning(f"Moralis {resp.status} for {address} on {chain}: {text[:200]}")
        except aiohttp.ClientError as e:
            logger.error(f"Moralis request error for {address} on {chain}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching transfers for {address} on {chain}: {e}")

    return all_transfers


def parse_transfer(transfer: dict, wallet_address: str) -> dict | None:
    """Parse a Moralis NFT transfer into a clean event dict."""
    try:
        from_addr = (transfer.get("from_address") or "").lower()
        to_addr = (transfer.get("to_address") or "").lower()
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
            (transfer.get("normalized_metadata") or {}).get("name")
            or transfer.get("name")
            or "Unknown NFT"
        )

        value = transfer.get("value")
        price = None
        if value and value != "0":
            try:
                price = int(value) / (10 ** 18)
            except (ValueError, TypeError):
                pass

        chain = transfer.get("_chain") or ""
        tx_hash = transfer.get("transaction_hash") or ""
        token_id = transfer.get("token_id") or ""
        quantity = int(transfer.get("amount") or 1)
        contract_address = transfer.get("token_address") or ""

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
        }
    except Exception as e:
        logger.error(f"Error parsing transfer: {e}")
        return None
