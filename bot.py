import json
import asyncio
import logging
import random
import nest_asyncio
from time import time
from datetime import datetime
from web3 import Web3
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

nest_asyncio.apply()
logging.basicConfig(level=logging.INFO)

# ---------------- CONFIG ----------------
TOKEN = "7242771948:AAHLKPZpZksVbNssGOmRZoLq_hUsRV_MMdI"
RPC_URL = 'https://zenchain-testnet.api.onfinality.io/public'
EXPLORER_URL = 'https://explorer.zenchain-testnet.network/tx/'
PRIVATE_KEY = "0865833388dd07bd134a64b21497b9c2bf134ec05ac1491206e8bda386bbf07c"

FAUCET_AMOUNT = Web3.to_wei(10, 'ether')
w3 = Web3(Web3.HTTPProvider(RPC_URL))
FAUCET_ADDRESS = w3.eth.account.from_key(PRIVATE_KEY).address

# ---------------- DATA STORE ----------------
try:
    with open("data.json", "r") as f:
        data = json.load(f)
except FileNotFoundError:
    data = {}

if "giveaway" not in data:
    data["giveaway"] = {
        "entries": [],
        "config": {
            "prize": w3.to_wei(500, 'ether'),
            "num_winners": 1,
            "end_time": 0
        }
    }

async def save_data():
    with open("data.json", "w") as f:
        json.dump(data, f)

def upgrade_user(user_id):
    if user_id not in data:
        data[user_id] = {"addresses": [], "last_faucet_time": 0}
    elif isinstance(data[user_id], list):
        data[user_id] = {"addresses": data[user_id], "last_faucet_time": 0}
    else:
        data[user_id].setdefault("addresses", [])
        data[user_id].setdefault("last_faucet_time", 0)

# ---------------- COMMANDS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Welcome to ZenWatcher!*\n\n"
        "This bot helps you:\n"
        "• Watch wallet addresses for incoming or outgoing ZTC transactions\n"
        "• Claim free ZTC daily from the faucet\n"
        "• Join giveaways for a chance to win large prizes(Under Development)\n\n"
        "Type /help to see all available commands.\n\n"
        "Enjoy exploring ZenChain! 🚀",
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Welcome to ZenBot!*\n\n"
        "Commands:\n"
        "/watch <address> - Watch\n"
        "/list - Show watched\n"
        "/remove <address> - Stop watching\n"
        "/clear - Remove all\n"
        "/balance <address> - Check balance\n"
        "/stats - Bot stats\n"
        "/faucet <address> - 100 ZTC every 24h\n"
        "/giveawayinfo - Current giveaway\n"
        "/join <wallet> - Join giveaway\n"
        "/help - Help",
        parse_mode="Markdown")

async def watch_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /watch <address>")
        return
    address = context.args[0].strip()
    if not w3.is_address(address):
        await update.message.reply_text("❌ Invalid address.")
        return
    user_id = str(update.message.chat_id)
    upgrade_user(user_id)
    if address not in data[user_id]["addresses"]:
        data[user_id]["addresses"].append(address)
        await save_data()
        await update.message.reply_text(f"✅ Now watching {address}.")
    else:
        await update.message.reply_text(f"👀 Already watching {address}.")

async def list_addresses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.chat_id)
    upgrade_user(user_id)
    watched = data[user_id]["addresses"]
    if watched:
        await update.message.reply_text("📜 Your watched addresses:\n" + "\n".join(watched))
    else:
        await update.message.reply_text("❌ You're not watching any addresses yet.")

async def remove_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /remove <address>")
        return
    address = context.args[0].strip()
    user_id = str(update.message.chat_id)
    upgrade_user(user_id)
    if address in data[user_id]["addresses"]:
        data[user_id]["addresses"].remove(address)
        await save_data()
        await update.message.reply_text(f"🚫 Stopped watching {address}.")
    else:
        await update.message.reply_text("❌ You weren't watching that address.")

async def clear_addresses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.chat_id)
    upgrade_user(user_id)
    data[user_id]["addresses"] = []
    await save_data()
    await update.message.reply_text("🧹 Cleared all your watched addresses.")

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /balance <address>")
        return
    address = context.args[0].strip()
    if not w3.is_address(address):
        await update.message.reply_text("❌ Invalid address.")
        return
    balance = w3.eth.get_balance(address)
    await update.message.reply_text(f"💰 Balance: {w3.from_wei(balance, 'ether')} ZTC")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total_users = len(data)
    total_addresses = sum(len(d.get("addresses", [])) for d in data.values())
    await update.message.reply_text(f"📊 Users: {total_users}\nWatched addresses: {total_addresses}")

# ---------------- GIVEAWAY ----------------
async def giveaway_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = data["giveaway"]["config"]
    left = max(0, cfg["end_time"] - int(time()))
    mins = left // 60
    await update.message.reply_text(
        f"🎉 Giveaway:\nPrize: {w3.from_wei(cfg['prize'], 'ether')} ZTC\n"
        f"Winners: {cfg['num_winners']}\nTime left: {mins} min\nEntries: {len(data['giveaway']['entries'])}"
    )

async def join_giveaway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /join <wallet>")
        return
    wallet = context.args[0].strip()
    if not w3.is_address(wallet):
        await update.message.reply_text("❌ Invalid wallet.")
        return
    user_id = str(update.message.chat_id)
    if user_id in [e["user_id"] for e in data["giveaway"]["entries"]]:
        await update.message.reply_text("🚫 Already joined.")
        return
    data["giveaway"]["entries"].append({"user_id": user_id, "wallet": wallet})
    await save_data()
    await update.message.reply_text(f"✅ Joined giveaway with {wallet}!")

async def set_giveaway_prize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /giveaway_prize <amount>")
        return
    data["giveaway"]["config"]["prize"] = w3.to_wei(float(context.args[0]), 'ether')
    await save_data()
    await update.message.reply_text(f"Prize set.")

async def set_giveaway_winners(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /giveaway_winners <number>")
        return
    data["giveaway"]["config"]["num_winners"] = int(context.args[0])
    await save_data()
    await update.message.reply_text("Number of winners set.")

async def start_giveaway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /giveaway_start <minutes>")
        return
    data["giveaway"]["config"]["end_time"] = int(time()) + int(context.args[0]) * 60
    data["giveaway"]["entries"] = []
    await save_data()
    await update.message.reply_text("🚀 Giveaway started!")

FAUCET_AMOUNT = w3.to_wei(100, 'ether')

# ---------------- FAUCET ----------------
async def faucet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.chat_id)
    upgrade_user(user_id)
    now = int(time())
    last = data[user_id].get("last_faucet_time", 0)
    wait = 86400 - (now - last)
    if wait > 0:
        await update.message.reply_text(
            f"🕒 Wait {int(wait/3600)} hours before claiming again."
        )
        return

    if not context.args:
        await update.message.reply_text("Usage: /faucet <address>")
        return

    addr = context.args[0].strip()
    if not w3.is_address(addr):
        await update.message.reply_text("❌ Invalid address.")
        return

    try:
        nonce = w3.eth.get_transaction_count(FAUCET_ADDRESS)
        tx = {
            'to': addr,
            'value': FAUCET_AMOUNT,
            'gas': 21000,
            'gasPrice': w3.to_wei('2', 'gwei'),
            'nonce': nonce,
            'chainId': w3.eth.chain_id
        }
        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        data[user_id]["last_faucet_time"] = now
        await save_data()

        tx_hash_hex = tx_hash.hex()
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        await update.message.reply_text(
            f"🚀 Tx: {tx_hash_hex}\n"
            f"From: {FAUCET_ADDRESS}\n"
            f"To: {addr}\n"
            f"Amount: {Web3.from_wei(FAUCET_AMOUNT, 'ether')} ZTC\n"
            f"Time: {time_str}\n\n"
            f"[View on Explorer](https://zentrace.io/tx/{tx_hash_hex})",
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text(f"⚠️ Failed: {e}")

# ---------------- WATCHERS ----------------
async def watch_transactions(app):
    last_block = w3.eth.block_number
    while True:
        latest = w3.eth.block_number
        if latest > last_block:
            for b in range(last_block + 1, latest + 1):
                block = w3.eth.get_block(b, full_transactions=True)
                for tx in block.transactions:
                    await handle_tx(tx, app)
            last_block = latest
        await asyncio.sleep(5)

async def handle_tx(tx, app):
    to_addr = tx.to
    from_addr = tx['from']
    val = w3.from_wei(tx.value, 'ether')
    hash_ = tx.hash.hex()
    time_s = datetime.now().strftime("%Y-%m-%d %H:%M")
    for uid, user in data.items():
        if to_addr in user.get("addresses", []) or from_addr in user.get("addresses", []):
            try:
                await app.bot.send_message(
                    int(uid),
                    f"🚀 Tx: [{hash_}]({EXPLORER_URL}{hash_})\n"
                    f"From: {from_addr}\nTo: {to_addr}\n"
                    f"Amount: {val} ZTC\nTime: {time_s}",
                    parse_mode="Markdown"
                )
            except:
                pass

async def watch_giveaway(app):
    while True:
        cfg = data["giveaway"]["config"]
        now = int(time())
        if cfg["end_time"] and now >= cfg["end_time"]:
            await pick_winners(app)
            cfg["end_time"] = 0
            await save_data()
        await asyncio.sleep(10)

async def pick_winners(app):
    entries = data["giveaway"]["entries"]
    if not entries:
        return
    winners = random.sample(entries, min(len(entries), data["giveaway"]["config"]["num_winners"]))
    prize = data["giveaway"]["config"]["prize"]
    for w in winners:
        wallet, uid = w["wallet"], w["user_id"]
        try:
            nonce = w3.eth.get_transaction_count(FAUCET_ADDRESS)
            tx = {'to': wallet, 'value': prize, 'gas': 21000, 'gasPrice': w3.to_wei('2', 'gwei'),
                  'nonce': nonce, 'chainId': w3.eth.chain_id}
            signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
            tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
            await app.bot.send_message(
                int(uid),
                f"🎉 Won {w3.from_wei(prize,'ether')} ZTC!\n[{tx_hash.hex()}]({EXPLORER_URL}{tx_hash.hex()})",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Prize error: {e}")

async def after_start(app):
    asyncio.create_task(watch_transactions(app))
    asyncio.create_task(watch_giveaway(app))

# ---------------- ADDRESS MESSAGE HANDLER ----------------
async def add_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    addr = update.message.text.strip()
    if not w3.is_address(addr):
        await update.message.reply_text("❌ Invalid address.")
        return
    user_id = str(update.message.chat_id)
    upgrade_user(user_id)
    if addr not in data[user_id]["addresses"]:
        data[user_id]["addresses"].append(addr)
        await save_data()
        await update.message.reply_text(f"✅ Now watching {addr}.")
    else:
        await update.message.reply_text(f"👀 Already watching {addr}.")

# ---------------- MAIN ----------------
async def main():
    app = ApplicationBuilder().token(TOKEN).connect_timeout(30).read_timeout(60).post_init(after_start).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("list", list_addresses))
    app.add_handler(CommandHandler("watch", watch_address))
    app.add_handler(CommandHandler("remove", remove_address))
    app.add_handler(CommandHandler("clear", clear_addresses))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("faucet", faucet))
    app.add_handler(CommandHandler("giveawayinfo", giveaway_info))
    app.add_handler(CommandHandler("join", join_giveaway))
    app.add_handler(CommandHandler("giveaway_prize", set_giveaway_prize))
    app.add_handler(CommandHandler("giveaway_winners", set_giveaway_winners))
    app.add_handler(CommandHandler("giveaway_start", start_giveaway))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_address))

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
