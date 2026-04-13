from config import SUPPORTED_CHAINS

CHAIN_EXPLORERS = {
    "ethereum": "https://etherscan.io/tx/",
    "base": "https://basescan.org/tx/",
    "arbitrum": "https://arbiscan.io/tx/",
    "bsc": "https://bscscan.com/tx/",
    "abstract": "https://abscan.org/tx/",
    "megaeth": "https://megaexplorer.xyz/tx/",
    "tempo": "https://explorer.tempo.net/tx/",
}

OPENSEA_CHAIN_SLUGS = {
    "ethereum": "ethereum",
    "base": "base",
    "arbitrum": "arbitrum",
    "bsc": "bsc",
    "abstract": "abstract",
}

EVENT_EMOJI = {
    "mint": "🌿",
    "buy": "💰",
    "sell": "💸",
}

EVENT_LABEL = {
    "mint": "замінтив",
    "buy": "купив",
    "sell": "продав",
}


def format_alert(data: dict, wallet_name: str) -> str:
    event = data["event_type"]
    emoji = EVENT_EMOJI.get(event, "📌")
    label = EVENT_LABEL.get(event, event)

    qty_str = f"x{data['quantity']} " if (data["quantity"] or 1) > 1 else ""
    chain_display = SUPPORTED_CHAINS.get(data["chain"], data["chain"])

    lines = [
        f"{emoji} <b>{wallet_name}</b> {label} {qty_str}<b>{data['nft_name']}</b>"
    ]

    if data["price"]:
        price_val = data["price"]
        price_str = f"{price_val:.6f}".rstrip("0").rstrip(".")
        lines.append(f"Ціна: <b>{price_str} {data['symbol']}</b>")

    if data["marketplace"]:
        lines.append(f"Маркетплейс: {data['marketplace']}")

    lines.append(f"Мережа: {chain_display}")
    lines.append("—————")

    # Links
    chain = data["chain"]
    tx_hash = data["tx_hash"]
    contract = data["contract_address"]
    token_id = data["token_id"]

    link_parts = []

    explorer = CHAIN_EXPLORERS.get(chain)
    if explorer and tx_hash:
        link_parts.append(f'<a href="{explorer}{tx_hash}">Транзакція</a>')

    os_slug = OPENSEA_CHAIN_SLUGS.get(chain)
    if os_slug and contract and token_id:
        os_url = f"https://opensea.io/assets/{os_slug}/{contract}/{token_id}"
        link_parts.append(f'<a href="{os_url}">OpenSea</a>')

    if link_parts:
        lines.append(" · ".join(link_parts))

    return "\n".join(lines)
