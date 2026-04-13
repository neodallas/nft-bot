from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import SUPPORTED_CHAINS


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Додати гаманець", callback_data="add_wallet")],
        [InlineKeyboardButton(text="👛 Мої гаманці", callback_data="my_wallets")],
    ])


def wallets_list(wallets: list) -> InlineKeyboardMarkup:
    buttons = []
    for w in wallets:
        buttons.append([
            InlineKeyboardButton(
                text=f"❌ {w['name']}",
                callback_data=f"del:{w['address']}"
            ),
            InlineKeyboardButton(
                text="⚙️",
                callback_data=f"chains:{w['address']}"
            ),
        ])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def chains_keyboard(wallet_address: str, current_chains: list) -> InlineKeyboardMarkup:
    buttons = []
    for chain_id, chain_name in SUPPORTED_CHAINS.items():
        selected = "✅" if chain_id in current_chains else "☑️"
        buttons.append([InlineKeyboardButton(
            text=f"{selected} {chain_name}",
            callback_data=f"toggle:{wallet_address}:{chain_id}"
        )])
    buttons.append([
        InlineKeyboardButton(text="✔️ Зберегти", callback_data=f"save_chains:{wallet_address}"),
        InlineKeyboardButton(text="◀️ Назад", callback_data="my_wallets"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cancel_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="main_menu")]
    ])
