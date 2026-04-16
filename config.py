import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ALCHEMY_API_KEY = os.getenv("ALCHEMY_API_KEY")
DATABASE_PATH = os.getenv("DATABASE_PATH", "nft_bot.db")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))
MAX_WALLETS_PER_USER = 20

# Chain ID -> Display name
SUPPORTED_CHAINS = {
    "ethereum": "Ethereum",
    "base": "Base",
    "abstract": "Abstract",
    "arbitrum": "Arbitrum",
    "bsc": "BSC",
    "megaeth": "MegaETH",
    "tempo": "Tempo",
}

# User input alias -> internal chain ID
CHAIN_ALIASES = {
    "eth": "ethereum",
    "ethereum": "ethereum",
    "base": "base",
    "abstract": "abstract",
    "arb": "arbitrum",
    "arbitrum": "arbitrum",
    "bsc": "bsc",
    "bnb": "bsc",
    "megaeth": "megaeth",
    "tempo": "tempo",
}
