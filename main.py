
import os
import sqlite3
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN", "")
DB = "battle.db"
app = Flask(__name__)

@app.get("/")
def home():
    return "Ovoz Battle bot ishlayapti!"

def init_db():
    with sqlite3.connect(DB) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS battles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, owner INTEGER, active INTEGER DEFAULT 1)""")
        con.execute("""CREATE TABLE IF NOT EXISTS votes (
            battle INTEGER, user INTEGER, candidate TEXT,
            PRIMARY KEY (battle, user))""")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        try:
            battle_id = int(context.args[0].replace("v_", ""))
            await show_battle(update, context, battle_id)
            return
        except ValueError:
            pass
    await update.message.reply_text(
        "👋 Ovoz Battle botiga xush kelibsiz!\n\n"
        "/new Nominatsiya nomi — yangi battle yaratish\n"
        "/list — faol battellar ro‘yxati"
    )

async def new_battle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = " ".join(context.args).strip()
    if not title:
        await update.message.reply_text(
            "Nom yozing:\n/new Instagram Top sxema Heshteg"
        )
        return
    with sqlite3.connect(DB) as con:
        cur = con.execute(
            "INSERT INTO battles(title, owner) VALUES(?, ?)",
            (title, update.effective_user.id))
        bid = cur.lastrowid
    await update.message.reply_text(
        f"✅ Battle yaratildi: {title}\nID: {bid}\n"
        f"Nomzod qo‘shish: /candidate {bid} Ism"
    )

async def add_candidate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "/candidate 1 @foydalanuvchi"
        )
        return
    try:
        bid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Battle ID raqam bo‘lishi kerak.")
        return
    candidate = " ".join(context.args[1:])
    with sqlite3.connect(DB) as con:
        battle = con.execute(
            "SELECT owner, active FROM battles WHERE id=?", (bid,)
        ).fetchone()
        if not battle or battle[0] != update.effective_user.id:
            await update.message.reply_text("Battle topilmadi yoki siz egasi emassiz.")
            return
        con.execute(
            "INSERT OR IGNORE INTO votes(battle,user,candidate) VALUES(?,?,?)",
            (bid, -int(update.effective_user.id), candidate))
    await update.message.reply_text(
        f"Nomzod ro‘yxatga olindi: {candidate}"
    )

async def show_battle(update, context, bid):
    with sqlite3.connect(DB) as con:
        battle = con.execute(
            "SELECT title, active FROM battles WHERE id=?", (bid,)
        ).fetchone()
        candidates = con.execute(
            "SELECT candidate FROM votes WHERE battle=? AND user<0",
            (bid,)
        ).fetchall()
    if not battle:
        msg = "Battle topilmadi."
        if update.callback_query:
            await update.callback_query.answer(msg, show_alert=True)
        else:
            await update.effective_message.reply_text(msg)
        return
    buttons = [[InlineKeyboardButton(
        c[0], callback_data=f"vote:{bid}:{c[0]}")] for c in candidates]
    markup = InlineKeyboardMarkup(buttons)
    text = f"🏆 {battle[0]}\nNomzodlardan birini tanlang:"
    if update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=markup)
    else:
        await update.effective_message.reply_text(text, reply_markup=markup)

async def vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, bid_text, candidate = q.data.split(":", 2)
    bid = int(bid_text)
    uid = update.effective_user.id
    with sqlite3.connect(DB) as con:
        battle = con.execute(
            "SELECT active FROM battles WHERE id=?", (bid,)
        ).fetchone()
        if not battle or not battle[0]:
            await q.message.reply_text("Bu battle faol emas.")
            return
        try:
            con.execute(
                "INSERT INTO votes(battle,user,candidate) VALUES(?,?,?)",
                (bid, uid, candidate))
            con.commit()
        except sqlite3.IntegrityError:
            await q.message.reply_text("❌ Bu battleda oldin ovoz bergansiz!")
            return
        counts = con.execute(
            "SELECT candidate, COUNT(*) FROM votes "
            "WHERE battle=? AND user>0 GROUP BY candidate ORDER BY COUNT(*) DESC",
            (bid,)
        ).fetchall()
    result = "\n".join(f"{i}. {name} — {n} ta ovoz"
                       for i, (name, n) in enumerate(counts, 1))
    await q.message.reply_text("✅ Ovozingiz qabul qilindi!\n\n📊 Natijalar:\n" + result)

async def list_battles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with sqlite3.connect(DB) as con:
        rows = con.execute(
            "SELECT id, title FROM battles WHERE active=1 ORDER BY id DESC"
        ).fetchall()
    if not rows:
        await update.message.reply_text("Hozircha battle yo‘q.")
        return
    await update.message.reply_text("\n".join(
        f"{bid}. {title}\n/start v_{bid}" for bid, title in rows
    ))

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN sozlanmagan!")
    init_db()
    Thread(target=run_web, daemon=True).start()
    bot = Application.builder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("new", new_battle))
    bot.add_handler(CommandHandler("candidate", add_candidate))
    bot.add_handler(CommandHandler("list", list_battles))
    bot.add_handler(CallbackQueryHandler(vote, pattern=r"^vote:"))
    bot.run_polling()

if __name__ == "__main__":
    main()
