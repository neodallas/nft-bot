import re
import logging

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import MAX_WALLETS_PER_USER, SUPPORTED_CHAINS
from db.database import (
    add_wallet,
    remove_wallet,
    get_user_wallets,
    count_user_wallets,
    update_wallet_chains,
    seed_seen_txs,
)
from scanner.moralis import get_wallet_transfers
from bot.keyboards import main_menu, wallets_list, chains_keyboard, cancel_button

logger = logging.getLogger(__name__)
router = Router()

ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")

# Temporary storage for chain editing: user_id -> {wallet_address, selected_chains}
_chain_edit: dict[int, dict] = {}


class AddWallet(StatesGroup):
    waiting_address = State()
    waiting_name = State()


def is_valid_address(address: str) -> bool:
    return bool(ADDRESS_RE.match(address))


def chains_display(chains_str: str) -> str:
    return ", ".join(SUPPORTED_CHAINS.get(c.strip(), c.strip()) for c in chains_str.split(","))


WELCOME_TEXT = (
    "👋 <b>NFT Scan</b>\n\n"
    "Відстежую EVM-гаманці та надсилаю алерти про NFT активність.\n\n"
    "<b>Що відстежую:</b>\n"
    "🌿 Мінти (безкоштовні та платні)\n"
    "💰 Покупки на OpenSea, Blur\n"
    "💸 Продажі\n\n"
    "Алерти приходять протягом 2 хвилин"
)


# ──────────────────────────────────────────────
# /start
# ──────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(WELCOME_TEXT, parse_mode="HTML", reply_markup=main_menu())


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(WELCOME_TEXT, parse_mode="HTML", reply_markup=main_menu())


# ──────────────────────────────────────────────
# Додати гаманець
# ──────────────────────────────────────────────

@router.callback_query(F.data == "add_wallet")
async def cb_add_wallet(call: CallbackQuery, state: FSMContext):
    count = await count_user_wallets(call.from_user.id)
    if count >= MAX_WALLETS_PER_USER:
        await call.answer(f"Ліміт {MAX_WALLETS_PER_USER} гаманців вичерпано", show_alert=True)
        return

    await state.set_state(AddWallet.waiting_address)
    await call.message.edit_text(
        "📍 Надішли адресу гаманця\n\nПриклад: <code>0x1234...abcd</code>",
        parse_mode="HTML",
        reply_markup=cancel_button(),
    )


@router.message(AddWallet.waiting_address)
async def process_address(message: Message, state: FSMContext):
    address = message.text.strip()

    if not is_valid_address(address):
        await message.answer(
            "❌ Невірна адреса. Має починатись з <code>0x</code> і містити 42 символи.\n\nСпробуй ще раз:",
            parse_mode="HTML",
            reply_markup=cancel_button(),
        )
        return

    await state.update_data(address=address)
    await state.set_state(AddWallet.waiting_name)
    await message.answer(
        f"✅ Адреса прийнята\n<code>{address}</code>\n\nТепер надішли <b>назву</b> для цього гаманця:",
        parse_mode="HTML",
        reply_markup=cancel_button(),
    )


@router.message(AddWallet.waiting_name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()
    data = await state.get_data()
    address = data["address"]

    await state.clear()

    success = await add_wallet(message.from_user.id, address, name)
    if not success:
        await message.answer("❌ Цей гаманець вже є у твоєму списку.", reply_markup=main_menu())
        return

    # Seed existing transactions so we don't spam on first scan
    try:
        transfers = await get_wallet_transfers(address.lower(), ["ethereum"])
        await seed_seen_txs(address.lower(), transfers)
    except Exception as e:
        logger.warning(f"Could not seed seen txs for {address}: {e}")

    count = await count_user_wallets(message.from_user.id)
    await message.answer(
        f"✅ Гаманець додано!\n\n"
        f"📍 <b>{name}</b>\n"
        f"<code>{address}</code>\n"
        f"Мережі: Ethereum\n\n"
        f"{count}/{MAX_WALLETS_PER_USER} гаманців",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


# ──────────────────────────────────────────────
# Мої гаманці
# ──────────────────────────────────────────────

@router.callback_query(F.data == "my_wallets")
async def cb_my_wallets(call: CallbackQuery, state: FSMContext):
    await state.clear()
    wallets = await get_user_wallets(call.from_user.id)

    if not wallets:
        await call.message.edit_text(
            "У тебе немає доданих гаманців.",
            reply_markup=main_menu(),
        )
        return

    lines = ["👛 <b>Твої гаманці:</b>\n"]
    for i, w in enumerate(wallets, 1):
        cd = chains_display(w["chains"])
        lines.append(
            f"{i}. <b>{w['name']}</b>\n"
            f"<code>{w['address']}</code>\n"
            f"Мережі: {cd}"
        )
    lines.append(f"\n{len(wallets)}/{MAX_WALLETS_PER_USER} гаманців")
    lines.append("\n<i>❌ — видалити · ⚙️ — мережі</i>")

    await call.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=wallets_list(wallets),
    )


# ──────────────────────────────────────────────
# Видалити гаманець
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("del:"))
async def cb_delete_wallet(call: CallbackQuery):
    address = call.data.split(":", 1)[1]
    success = await remove_wallet(call.from_user.id, address)

    if success:
        await call.answer("✅ Гаманець видалено")
        # Refresh the wallets list
        wallets = await get_user_wallets(call.from_user.id)
        if not wallets:
            await call.message.edit_text(
                "У тебе немає доданих гаманців.",
                reply_markup=main_menu(),
            )
            return

        lines = ["👛 <b>Твої гаманці:</b>\n"]
        for i, w in enumerate(wallets, 1):
            cd = chains_display(w["chains"])
            lines.append(
                f"{i}. <b>{w['name']}</b>\n"
                f"<code>{w['address']}</code>\n"
                f"Мережі: {cd}"
            )
        lines.append(f"\n{len(wallets)}/{MAX_WALLETS_PER_USER} гаманців")
        lines.append("\n<i>❌ — видалити · ⚙️ — мережі</i>")

        await call.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=wallets_list(wallets),
        )
    else:
        await call.answer("❌ Гаманець не знайдено", show_alert=True)


# ──────────────────────────────────────────────
# Налаштувати мережі
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("chains:"))
async def cb_chains(call: CallbackQuery):
    address = call.data.split(":", 1)[1]
    wallets = await get_user_wallets(call.from_user.id)
    wallet = next((w for w in wallets if w["address"] == address.lower()), None)

    if not wallet:
        await call.answer("Гаманець не знайдено", show_alert=True)
        return

    current_chains = [c.strip() for c in wallet["chains"].split(",")]
    _chain_edit[call.from_user.id] = {
        "address": address,
        "chains": current_chains.copy(),
    }

    await call.message.edit_text(
        f"⚙️ <b>Мережі для {wallet['name']}</b>\n"
        f"<code>{address}</code>\n\n"
        "Вибери мережі для відстеження:",
        parse_mode="HTML",
        reply_markup=chains_keyboard(address, current_chains),
    )


@router.callback_query(F.data.startswith("toggle:"))
async def cb_toggle_chain(call: CallbackQuery):
    _, address, chain_id = call.data.split(":", 2)
    user_id = call.from_user.id

    if user_id not in _chain_edit:
        await call.answer("Сесія застаріла, спробуй ще раз", show_alert=True)
        return

    edit = _chain_edit[user_id]
    if chain_id in edit["chains"]:
        if len(edit["chains"]) > 1:
            edit["chains"].remove(chain_id)
        else:
            await call.answer("Має бути вибрана хоча б одна мережа", show_alert=True)
            return
    else:
        edit["chains"].append(chain_id)

    await call.message.edit_reply_markup(
        reply_markup=chains_keyboard(address, edit["chains"])
    )
    await call.answer()


@router.callback_query(F.data.startswith("save_chains:"))
async def cb_save_chains(call: CallbackQuery):
    address = call.data.split(":", 1)[1]
    user_id = call.from_user.id

    if user_id not in _chain_edit:
        await call.answer("Сесія застаріла", show_alert=True)
        return

    chains = _chain_edit.pop(user_id)["chains"]
    chains_str = ",".join(chains)

    success = await update_wallet_chains(user_id, address, chains_str)
    if success:
        await call.answer("✅ Збережено")
        await call.message.edit_text(
            f"✅ Мережі оновлено!\n\n"
            f"<code>{address}</code>\n"
            f"Мережі: {chains_display(chains_str)}",
            parse_mode="HTML",
            reply_markup=main_menu(),
        )
    else:
        await call.answer("❌ Помилка збереження", show_alert=True)
