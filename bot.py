# -*- coding: utf-8 -*-
"""
GAME WORLD — Telegram Private Chat Multiplayer Bot
Files: bot.py + requirements.txt
Python 3.10+
"""
import asyncio
import json
import logging
import os
import random
import secrets
import string
from datetime import datetime, timezone

import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    BotCommand
)
from aiogram.utils.deep_linking import create_start_link, decode_payload
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

# ===================== CONFIG =====================
# BotFather ကရထားတဲ့ Token ကို ဒီနေရာမှာ ထည့်နိုင်ပါတယ်။
# ပိုလုံခြုံရန် Hosting Environment Variables ထဲတွင် BOT_TOKEN ထည့်သုံးပါ။
BOT_TOKEN = os.getenv("BOT_TOKEN", "8641144956:AAGPseypAPdpNcz-LTQ4QwfjUe3mxDn_REE").strip()
DB_PATH = os.getenv("DB_PATH", "game_world.sqlite3")
OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
log = logging.getLogger("game-world")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

GAMES = {
    "ttt": ("⭕ Tic-Tac-Toe", "သုံးကွက်တန်းအောင်လုပ်ပါ။"),
    "rps": ("✊ Rock Paper Scissors", "ရွေးချယ်မှုကို လျှို့ဝှက်ရွေးပြီး တစ်ပြိုင်နက်ရလဒ်ထုတ်မယ်။"),
    "coin": ("🪙 Coin Guess", "Heads/Tails ကို ခန့်မှန်းပါ။"),
    "dice": ("🎲 Dice Duel", "နှစ်ယောက်လုံး အန်စာတုံးပစ်ပြီး အမှတ်မြင့်သူနိုင်မယ်။"),
    "number": ("🔢 Number Duel", "1 မှ 10 အတွင်း နံပါတ်တစ်ခုရွေးပါ။ တူညီရင် သရေ၊ ပိုမြင့်သူနိုင်မယ်။"),
    "math": ("🧠 Math Duel", "သင်္ချာမေးခွန်းကို နှစ်ယောက်လုံး ဖြေပါ။"),
    "quiz": ("❓ Quick Quiz", "မေးခွန်းတစ်ခုကို ဖြေပြီး အမှတ်ယူပါ။"),
    "memory": ("🃏 Memory Match", "ကတ်အတွဲကို အလှည့်ကျရွေးပါ။ အတွဲတူရင် အမှတ်ရမယ်။"),
    "higher": ("📈 Higher or Lower", "လျှို့ဝှက်နံပါတ်ကို ခန့်မှန်းပါ။ ပိုနီးသူနိုင်မယ်။"),
    "word": ("🔤 Word Scramble", "ရောထားတဲ့ အင်္ဂလိပ်စာလုံးကို ဖြေပါ။"),
}
GAME_IDS = list(GAMES.keys())
RPS = {"rock": "✊ ကျောက်", "paper": "✋ စက္ကူ", "scissors": "✌️ ကတ်ကြေး"}
RPS_BEATS = {"rock": "scissors", "scissors": "paper", "paper": "rock"}

QUIZ = [
    ("မြန်မာနိုင်ငံ၏ မြို့တော်မှာ ဘယ်မြို့လဲ?", ["နေပြည်တော်", "ရန်ကုန်", "မန္တလေး"], 0),
    ("တစ်ပတ်မှာ ဘယ်နှစ်ရက်ရှိသလဲ?", ["၅ ရက်", "၇ ရက်", "၁၀ ရက်"], 1),
    ("2 + 5 = ?", ["6", "7", "8"], 1),
    ("ကမ္ဘာ့သဘာဝဂြိုဟ်တုက ဘာလဲ?", ["လ", "နေ", "အင်္ဂါ"], 0),
    ("ရေ၏ ဓာတုဖော်မြူလာက ဘာလဲ?", ["CO2", "H2O", "O2"], 1),
]
WORDS = ["PLANET", "FRIEND", "GAMING", "PYTHON", "ORANGE", "PUZZLE", "ROCKET"]
MEMORY_SYMBOLS = ["🍎", "🍋", "🍇", "⭐", "🐼", "🚀"]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def code6():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

def display_name(user):
    return (user.full_name or user.username or f"Player {user.id}")[:50]

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 ဂိမ်း ၁၀ မျိုး", callback_data="menu:games")],
        [InlineKeyboardButton(text="🏆 Leaderboard", callback_data="menu:leaderboard"),
         InlineKeyboardButton(text="👤 Profile", callback_data="menu:profile")],
        [InlineKeyboardButton(text="📖 ကစားနည်း", callback_data="menu:help")]
    ])

def game_menu():
    rows = []
    items = list(GAMES.items())
    for i in range(0, len(items), 2):
        row = []
        for gid, (title, _) in items[i:i+2]:
            row.append(InlineKeyboardButton(text=title, callback_data=f"game:{gid}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ ပင်မမီနူး", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY, name TEXT NOT NULL, username TEXT,
            wins INTEGER NOT NULL DEFAULT 0, losses INTEGER NOT NULL DEFAULT 0,
            draws INTEGER NOT NULL DEFAULT 0, games_played INTEGER NOT NULL DEFAULT 0,
            last_seen TEXT NOT NULL
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS matches(
            code TEXT PRIMARY KEY, game TEXT NOT NULL, p1 INTEGER NOT NULL,
            p2 INTEGER, state TEXT NOT NULL, status TEXT NOT NULL,
            winner INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS match_users(
            code TEXT NOT NULL, user_id INTEGER NOT NULL, chat_id INTEGER,
            message_id INTEGER, PRIMARY KEY(code,user_id)
        )""")
        await db.commit()

async def upsert_user(user):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""INSERT INTO users(user_id,name,username,last_seen)
        VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET
        name=excluded.name, username=excluded.username,last_seen=excluded.last_seen""",
        (user.id, display_name(user), user.username, now_iso()))
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id,name,username,wins,losses,draws,games_played FROM users WHERE user_id=?", (user_id,))
        return await cur.fetchone()

async def create_match(game, user_id):
    code = code6()
    state = initial_state(game)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO matches(code,game,p1,p2,state,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                         (code, game, user_id, None, json.dumps(state, ensure_ascii=False), "waiting", now_iso(), now_iso()))
        await db.commit()
    return code

def initial_state(game):
    if game == "ttt":
        return {"board": [""] * 9, "turn": 0}
    if game == "rps":
        return {"choices": {}, "round": 1, "score": [0, 0]}
    if game == "coin":
        return {"choices": {}, "secret": random.choice(["heads", "tails"])}
    if game == "dice":
        return {"rolled": {}, "values": {}}
    if game == "number":
        return {"choices": {}}
    if game == "math":
        a, b = random.randint(2, 12), random.randint(2, 12)
        return {"question": f"{a} × {b} = ?", "answer": a*b, "answers": {}, "scores": [0,0]}
    if game == "quiz":
        q = random.choice(QUIZ)
        return {"question": q[0], "options": q[1], "answer": q[2], "answers": {}, "scores": [0,0]}
    if game == "memory":
        cards = MEMORY_SYMBOLS * 2
        random.shuffle(cards)
        return {"cards": cards, "revealed": [], "matched": [], "turn": 0, "scores": [0,0], "last": []}
    if game == "higher":
        return {"target": random.randint(1, 100), "choices": {}}
    if game == "word":
        word = random.choice(WORDS)
        mixed = list(word)
        random.shuffle(mixed)
        while "".join(mixed) == word:
            random.shuffle(mixed)
        return {"word": word, "mixed": "".join(mixed), "answers": {}}
    return {}

async def load_match(code):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM matches WHERE code=?", (code,))
        row = await cur.fetchone()
        if not row:
            return None
        item = dict(row)
        item["state"] = json.loads(item["state"])
        cur = await db.execute("SELECT user_id,chat_id,message_id FROM match_users WHERE code=?", (code,))
        item["players"] = [dict(r) for r in await cur.fetchall()]
        return item

async def save_match(match):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE matches SET p2=?,state=?,status=?,winner=?,updated_at=? WHERE code=?",
            (match["p2"], json.dumps(match["state"], ensure_ascii=False), match["status"],
             match.get("winner"), now_iso(), match["code"]))
        await db.commit()

async def add_match_user(code, user_id, chat_id, message_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""INSERT INTO match_users(code,user_id,chat_id,message_id) VALUES(?,?,?,?)
        ON CONFLICT(code,user_id) DO UPDATE SET chat_id=excluded.chat_id,message_id=excluded.message_id""",
        (code, user_id, chat_id, message_id))
        await db.commit()

async def update_user_message(code, user_id, chat_id, message_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE match_users SET chat_id=?,message_id=? WHERE code=? AND user_id=?",
                         (chat_id, message_id, code, user_id))
        await db.commit()

async def bump_stats(p1, p2, winner):
    async with aiosqlite.connect(DB_PATH) as db:
        for uid in (p1, p2):
            if uid is None:
                continue
            if winner is None:
                await db.execute("UPDATE users SET draws=draws+1,games_played=games_played+1 WHERE user_id=?", (uid,))
            elif uid == winner:
                await db.execute("UPDATE users SET wins=wins+1,games_played=games_played+1 WHERE user_id=?", (uid,))
            else:
                await db.execute("UPDATE users SET losses=losses+1,games_played=games_played+1 WHERE user_id=?", (uid,))
        await db.commit()

def player_index(match, uid):
    if uid == match["p1"]:
        return 0
    if uid == match["p2"]:
        return 1
    return -1

def match_keyboard(match):
    g, s, code = match["game"], match["state"], match["code"]
    if match["status"] == "waiting":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔗 ဖိတ်ခေါ် Link ပြန်ယူမယ်", callback_data=f"invite:{code}")],
            [InlineKeyboardButton(text="❌ ပွဲဖျက်မယ်", callback_data=f"cancel:{code}")]
        ])
    if match["status"] == "finished":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Rematch", callback_data=f"rematch:{code}")],
            [InlineKeyboardButton(text="🎮 ဂိမ်းစာရင်း", callback_data="menu:games"),
             InlineKeyboardButton(text="🏠 မီနူး", callback_data="menu:home")]
        ])
    rows = []
    if g == "ttt":
        board = s["board"]
        for r in range(3):
            rows.append([InlineKeyboardButton(text=board[r*3+c] or "⬜", callback_data=f"move:{code}:ttt:{r*3+c}") for c in range(3)])
    elif g == "rps":
        for k, label in RPS.items():
            rows.append([InlineKeyboardButton(text=label, callback_data=f"move:{code}:rps:{k}")])
    elif g == "coin":
        rows = [[InlineKeyboardButton(text="🪙 Heads", callback_data=f"move:{code}:coin:heads"),
                 InlineKeyboardButton(text="🪙 Tails", callback_data=f"move:{code}:coin:tails")]]
    elif g == "dice":
        rows = [[InlineKeyboardButton(text="🎲 အန်စာတုံးပစ်မယ်", callback_data=f"move:{code}:dice:roll")]]
    elif g == "number":
        rows = [[InlineKeyboardButton(text=str(n), callback_data=f"move:{code}:number:{n}") for n in range(1,6)],
                [InlineKeyboardButton(text=str(n), callback_data=f"move:{code}:number:{n}") for n in range(6,11)]]
    elif g == "math":
        # Both players answer using four choices around the answer.
        ans = s["answer"]
        opts = list(dict.fromkeys([ans, ans+1, max(0, ans-1), ans+2]))
        random.Random(code).shuffle(opts)
        rows = [[InlineKeyboardButton(text=str(n), callback_data=f"move:{code}:math:{n}") for n in opts[:2]],
                [InlineKeyboardButton(text=str(n), callback_data=f"move:{code}:math:{n}") for n in opts[2:4]]]
    elif g == "quiz":
        rows = [[InlineKeyboardButton(text=f"{i+1}. {opt}", callback_data=f"move:{code}:quiz:{i}")]
                for i,opt in enumerate(s["options"])]
    elif g == "memory":
        cards = s["cards"]
        for r in range(3):
            row=[]
            for c in range(4):
                i=r*4+c
                label = cards[i] if i in s["matched"] or i in s["revealed"] else "❔"
                row.append(InlineKeyboardButton(text=label, callback_data=f"move:{code}:memory:{i}"))
            rows.append(row)
    elif g == "higher":
        rows = [[InlineKeyboardButton(text=f"{n}", callback_data=f"move:{code}:higher:{n}") for n in range(1, 26)],
                [InlineKeyboardButton(text=f"{n}", callback_data=f"move:{code}:higher:{n}") for n in range(26, 51)],
                [InlineKeyboardButton(text=f"{n}", callback_data=f"move:{code}:higher:{n}") for n in range(51, 76)],
                [InlineKeyboardButton(text=f"{n}", callback_data=f"move:{code}:higher:{n}") for n in range(76, 101)]]
    elif g == "word":
        rows = [[InlineKeyboardButton(text=letter, callback_data=f"move:{code}:word:{letter}") for letter in s["word"]]]
        rows.append([InlineKeyboardButton(text="💡 Hint", callback_data=f"hint:{code}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def match_text(match, viewer_id=None):
    g, s = match["game"], match["state"]
    p1, p2 = match["p1"], match["p2"]
    names = {p["user_id"]: f"Player {1 if p['user_id']==p1 else 2}" for p in match.get("players", [])}
    title = GAMES[g][0]
    if match["status"] == "waiting":
        return (f"🎮 <b>{title}</b>\n\nပွဲကုဒ်: <code>{match['code']}</code>\n"
                f"Player 1: <code>{p1}</code>\n\nသူငယ်ချင်းကို Invite Link ပို့ပါ။ သူ /start နှိပ်ပြီး ဝင်လာရင် ပွဲစမယ်။")
    if match["status"] == "finished":
        if match.get("winner") is None:
            result = "🤝 ပွဲသရေ!"
        else:
            result = f"🏆 အနိုင်ရသူ: Player {1 if match['winner']==p1 else 2}"
        return f"🏁 <b>{title}</b>\n\n{result}\n\n🔄 Rematch နှိပ်ပြီး နောက်တစ်ပွဲဆော့နိုင်ပါတယ်။"
    header = f"🎮 <b>{title}</b>\n👥 Player 1: <code>{p1}</code>\n👥 Player 2: <code>{p2}</code>\n"
    if g == "ttt":
        b=s["board"]
        board="\n".join(" ".join(b[r*3+c] or "⬜" for c in range(3)) for r in range(3))
        turn=f"အလှည့်: Player {s['turn']+1} ({'❌' if s['turn']==0 else '⭕'})"
        return f"{header}\n<pre>{board}</pre>\n{turn}"
    if g == "rps":
        chosen = len(s["choices"])
        return f"{header}\nရွေးချယ်မှု: {chosen}/2\nနှစ်ယောက်လုံး ရွေးပြီးမှ ရလဒ်ဖော်ပြမယ်။"
    if g == "coin":
        return f"{header}\n🪙 Heads သို့မဟုတ် Tails ကို ရွေးပါ။ နှစ်ယောက်လုံး ရွေးပြီးမှ အကြွေစေ့ရလဒ် ထွက်မယ်။"
    if g == "dice":
        return f"{header}\n🎲 အန်စာတုံးပစ်ရန် Button နှိပ်ပါ။ နှစ်ယောက်လုံးပစ်ပြီးမှ ရလဒ်ထွက်မယ်။"
    if g == "number":
        return f"{header}\n🔢 1–10 အတွင်း နံပါတ်ရွေးပါ။ ပိုမြင့်တဲ့နံပါတ်နိုင်ပြီး တူရင်သရေ။"
    if g == "math":
        return f"{header}\n🧠 <b>{s['question']}</b>\nနှစ်ယောက်လုံး အဖြေရွေးပါ။ မှန်သူနိုင်မယ်၊ နှစ်ယောက်လုံး မှန်ရင် အမြန်ဆုံးဖြေသူနိုင်မယ်။"
    if g == "quiz":
        return f"{header}\n❓ <b>{s['question']}</b>\nနှစ်ယောက်လုံး အဖြေရွေးပါ။ မှန်သူနိုင်မယ်၊ နှစ်ယောက်လုံး မှန်ရင် အမြန်ဆုံးဖြေသူနိုင်မယ်။"
    if g == "memory":
        return f"{header}\n🃏 ကတ် ၁၂ ကတ်ထဲမှ အလှည့်ကျရွေးပါ။ တူညီတဲ့အတွဲရရင် အမှတ်ရမယ်။\nအမှတ် — P1: {s['scores'][0]} | P2: {s['scores'][1]}"
    if g == "higher":
        return f"{header}\n📈 1–100 အတွင်း လျှို့ဝှက်နံပါတ်တစ်ခုရှိတယ်။ ကိုယ်ခန့်မှန်းထားတဲ့နံပါတ်က ပိုနီးသူနိုင်မယ်။"
    if g == "word":
        return f"{header}\n🔤 စာလုံးရောထားတာ: <b>{s['mixed']}</b>\nစာလုံးကို အစီအစဉ်မှန်အောင် စဉ်းစားပြီး ရွေးပါ။"
    return header

async def render_match(code):
    match = await load_match(code)
    if not match:
        return
    text = match_text(match)
    kb = match_keyboard(match)
    for p in match["players"]:
        if not p["chat_id"]:
            continue
        try:
            if p["message_id"]:
                await bot.edit_message_text(text, chat_id=p["chat_id"], message_id=p["message_id"],
                                            reply_markup=kb, parse_mode="HTML")
            else:
                msg = await bot.send_message(p["chat_id"], text, reply_markup=kb, parse_mode="HTML")
                await update_user_message(code, p["user_id"], p["chat_id"], msg.message_id)
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e).lower():
                log.warning("Render error for %s: %s", p["user_id"], e)
        except TelegramForbiddenError:
            log.info("User %s has not opened bot or blocked it", p["user_id"])

async def finish_match(match, winner):
    if match["status"] == "finished":
        return
    match["status"] = "finished"
    match["winner"] = winner
    await save_match(match)
    await bump_stats(match["p1"], match["p2"], winner)
    await render_match(match["code"])

async def start_joining(code, user, chat_id):
    match = await load_match(code)
    if not match:
        return "ဒီ Invite Link မမှန်တော့ပါ။ ပွဲအသစ်ဖန်တီးပါ။"
    if match["status"] != "waiting":
        return "ဒီပွဲက စပြီးသား သို့မဟုတ် ပြီးသွားပါပြီ။"
    if user.id == match["p1"]:
        return "ဒီပွဲကို သင်ကိုယ်တိုင် ဖန်တီးထားတာပါ။ သူငယ်ချင်းကို Invite Link ပို့ပါ။"
    await upsert_user(user)
    match["p2"] = user.id
    match["status"] = "playing"
    await save_match(match)
    msg = await bot.send_message(chat_id, "ချိတ်ဆက်နေပါတယ်…")
    await add_match_user(code, user.id, chat_id, msg.message_id)
    await render_match(code)
    return None

async def create_invite_message(message, game):
    code = await create_match(game, message.from_user.id)
    placeholder = await message.answer("🎮 ပွဲဖန်တီးနေပါတယ်…")
    await add_match_user(code, message.from_user.id, message.chat.id, placeholder.message_id)
    link = await create_start_link(bot, f"join_{code}", encode=True)
    await placeholder.edit_text(
        f"🎮 <b>{GAMES[game][0]}</b>\n\n"
        f"ပွဲကုဒ်: <code>{code}</code>\n"
        f"သူငယ်ချင်းကို အောက်က Invite Link ပို့ပါ။\n"
        f"သူငယ်ချင်းက Bot ကို အရင် /start လုပ်ထားရပါမယ်။",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 သူငယ်ချင်းကို ဖိတ်မယ်", url=link)],
            [InlineKeyboardButton(text="🔄 ဂိမ်းစာရင်း", callback_data="menu:games")]
        ]), parse_mode="HTML")
    return code

@dp.message(CommandStart())
async def start(message: Message, command: CommandStart):
    await upsert_user(message.from_user)
    arg = command.args or ""
    if arg:
        try:
            arg = decode_payload(arg)
        except Exception:
            pass
    if arg.startswith("join_"):
        code = arg[5:]
        err = await start_joining(code, message.from_user, message.chat.id)
        if err:
            await message.answer(err, reply_markup=main_menu())
        return
    await message.answer(
        f"🎮 မင်္ဂလာပါ {display_name(message.from_user)}!\n\n"
        "GAME WORLD မှ ကြိုဆိုပါတယ်။\n"
        "Website မလိုဘဲ Private Chat ကနေ သူငယ်ချင်းနဲ့ ဂိမ်းဆော့နိုင်ပါတယ်။\n\n"
        "📌 သူငယ်ချင်းနှစ်ယောက်စလုံး Bot ကို /start လုပ်ထားပါ။",
        reply_markup=main_menu()
    )

@dp.message(Command("games"))
async def games_cmd(message: Message):
    await upsert_user(message.from_user)
    await message.answer("🎮 ဆော့ချင်တဲ့ဂိမ်းကို ရွေးပါ။", reply_markup=game_menu())

@dp.message(Command("play"))
async def play_cmd(message: Message):
    await message.answer("🎮 ဂိမ်းရွေးပါ။", reply_markup=game_menu())

@dp.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "📖 <b>ကစားနည်း</b>\n\n"
        "1. နှစ်ယောက်စလုံး /start လုပ်ပါ။\n"
        "2. Player 1 က /games နှိပ်ပြီး ဂိမ်းရွေးပါ။\n"
        "3. Invite Link ကို သူငယ်ချင်းဆီ ပို့ပါ။\n"
        "4. သူငယ်ချင်းက Link ကိုနှိပ်ပြီး Start လုပ်ပါ။\n"
        "5. နှစ်ယောက်လုံး ကိုယ့် Private Chat ထဲက Button တွေကို နှိပ်ဆော့ပါ။\n\n"
        "ဂိမ်းအများစုက အလှည့်/ရွေးချယ်မှုကို Server က စစ်ဆေးပါတယ်။",
        parse_mode="HTML", reply_markup=main_menu()
    )

@dp.message(Command("leaderboard"))
async def leaderboard_cmd(message: Message):
    await show_leaderboard(message)

async def show_leaderboard(message=None, callback=None):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT name,wins,losses,draws,games_played FROM users ORDER BY wins DESC, games_played DESC LIMIT 10")
        rows = await cur.fetchall()
    text = "🏆 <b>GAME WORLD LEADERBOARD</b>\n\n"
    if not rows:
        text += "အခုထိ ကစားထားသူ မရှိသေးပါ။"
    else:
        for i, row in enumerate(rows, 1):
            text += f"{i}. {row[0]} — 🏆 {row[1]} | 🎮 {row[4]} ပွဲ\n"
    if callback:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu())
    elif message:
        await message.answer(text, parse_mode="HTML", reply_markup=main_menu())

@dp.message(Command("profile"))
async def profile_cmd(message: Message):
    await upsert_user(message.from_user)
    row = await get_user(message.from_user.id)
    if row:
        await message.answer(
            f"👤 <b>{row[1]}</b>\n\n🎮 ကစားပွဲ: {row[6]}\n🏆 နိုင်: {row[3]}\n❌ ရှုံး: {row[4]}\n🤝 သရေ: {row[5]}",
            parse_mode="HTML", reply_markup=main_menu()
        )

@dp.message(Command("cancel"))
async def cancel_cmd(message: Message):
    await message.answer("လက်ရှိ Button ကနေ ပွဲတစ်ခုချင်းစီကို ဖျက်နိုင်ပါတယ်။", reply_markup=main_menu())

@dp.message(Command("admin"))
async def admin_cmd(message: Message):
    if OWNER_ID and message.from_user.id == OWNER_ID:
        async with aiosqlite.connect(DB_PATH) as db:
            u = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
            m = (await (await db.execute("SELECT COUNT(*) FROM matches")).fetchone())[0]
            active = (await (await db.execute("SELECT COUNT(*) FROM matches WHERE status IN ('waiting','playing')")).fetchone())[0]
        await message.answer(f"🛠 Admin Status\nUsers: {u}\nMatches: {m}\nActive: {active}")
    else:
        await message.answer("ဒီ Command ကို Owner သာ အသုံးပြုနိုင်ပါတယ်။")

@dp.callback_query(F.data.startswith("menu:"))
async def menu_callback(call: CallbackQuery):
    await call.answer()
    action = call.data.split(":",1)[1]
    if action == "games":
        await call.message.edit_text("🎮 ဆော့ချင်တဲ့ဂိမ်းကို ရွေးပါ။", reply_markup=game_menu())
    elif action == "leaderboard":
        await show_leaderboard(callback=call)
    elif action == "profile":
        row = await get_user(call.from_user.id)
        if not row:
            await call.message.edit_text("Profile မတွေ့ပါ။ /start ကိုနှိပ်ပါ။", reply_markup=main_menu())
        else:
            await call.message.edit_text(
                f"👤 <b>{row[1]}</b>\n\n🎮 ကစားပွဲ: {row[6]}\n🏆 နိုင်: {row[3]}\n❌ ရှုံး: {row[4]}\n🤝 သရေ: {row[5]}",
                parse_mode="HTML", reply_markup=main_menu())
    elif action == "help":
        await call.message.edit_text("📖 /start နှစ်ယောက်စလုံးလုပ်ပါ → /games → ဂိမ်းရွေး → Invite Link ပို့ → သူငယ်ချင်း Join လုပ်ပါ။", reply_markup=main_menu())
    else:
        await call.message.edit_text("🎮 GAME WORLD ပင်မမီနူး", reply_markup=main_menu())

@dp.callback_query(F.data.startswith("game:"))
async def choose_game(call: CallbackQuery):
    await call.answer()
    game = call.data.split(":",1)[1]
    if game not in GAMES:
        return
    await create_invite_message(call.message, game)

@dp.callback_query(F.data.startswith("invite:"))
async def invite_again(call: CallbackQuery):
    await call.answer()
    code = call.data.split(":",1)[1]
    match = await load_match(code)
    if not match or call.from_user.id != match["p1"]:
        await call.answer("ပွဲဖန်တီးသူသာ Invite ပြန်ယူနိုင်ပါတယ်။", show_alert=True)
        return
    link = await create_start_link(bot, f"join_{code}", encode=True)
    await call.message.answer("သူငယ်ချင်းကို ဒီ Invite Link ပို့ပါ။", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Invite Friend", url=link)]
    ]))

@dp.callback_query(F.data.startswith("cancel:"))
async def cancel_match(call: CallbackQuery):
    code = call.data.split(":",1)[1]
    match = await load_match(code)
    if not match or call.from_user.id != match["p1"] or match["status"] != "waiting":
        await call.answer("ဒီပွဲကို ဖျက်လို့မရပါ။", show_alert=True)
        return
    match["status"] = "finished"
    match["winner"] = None
    await save_match(match)
    await render_match(code)
    await call.answer("ပွဲဖျက်ပြီးပါပြီ။")

def decide_ttt(board):
    lines = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for a,b,c in lines:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    if all(board):
        return "draw"
    return None

@dp.callback_query(F.data.startswith("move:"))
async def move_callback(call: CallbackQuery):
    parts = call.data.split(":")
    if len(parts) != 4:
        await call.answer("Move မမှန်ပါ။", show_alert=True)
        return
    _, code, game, value = parts
    match = await load_match(code)
    if not match or match["status"] != "playing":
        await call.answer("ဒီပွဲ မရှိတော့ပါ သို့မဟုတ် ပြီးသွားပါပြီ။", show_alert=True)
        return
    idx = player_index(match, call.from_user.id)
    if idx < 0:
        await call.answer("ဒီပွဲမှာ သင်မပါဝင်ပါ။", show_alert=True)
        return
    if game != match["game"]:
        await call.answer("Game မကိုက်ညီပါ။", show_alert=True)
        return
    s = match["state"]
    winner = "continue"
    message = "ရွေးချယ်မှု လက်ခံပြီးပါပြီ။"
    if game == "ttt":
        cell = int(value)
        if cell < 0 or cell > 8 or s["board"][cell]:
            await call.answer("ဒီကွက်ကို ရွေးလို့မရပါ။", show_alert=True); return
        if s["turn"] != idx:
            await call.answer("အခု သင့်အလှည့်မဟုတ်ပါ။", show_alert=True); return
        s["board"][cell] = "❌" if idx == 0 else "⭕"
        result = decide_ttt(s["board"])
        if result:
            winner = None if result == "draw" else match["p1"] if result == "❌" else match["p2"]
        else:
            s["turn"] = 1 - idx
    elif game in ("rps","coin","number","higher","word","quiz","math"):
        bucket = "choices" if game in ("rps","coin","number","higher") else "answers"
        if game == "word":
            # စာလုံးကို တစ်လုံးချင်းရွေးပြီး ကိုယ့်အဖြေကို တည်ဆောက်ပါ။
            current = s["answers"].get(str(call.from_user.id), "")
            if len(current) >= len(s["word"]):
                await call.answer("ဒီပွဲမှာ သင့်အဖြေ ပြီးသွားပါပြီ။", show_alert=True); return
            current += value
            s["answers"][str(call.from_user.id)] = current
            if current == s["word"]:
                winner = call.from_user.id
            elif len(current) >= len(s["word"]):
                # မှားသွားလျှင် ပြန်ကြိုးစားခွင့်ပေးပါ။
                s["answers"][str(call.from_user.id)] = ""
                await save_match(match)
                await call.answer("မမှန်သေးပါ။ ထပ်ရွေးကြည့်ပါ။", show_alert=True)
                await render_match(code)
                return
            await save_match(match)
            await call.answer("စာလုံးရွေးပြီးပါပြီ။")
            await render_match(code)
            if winner != "continue":
                await finish_match(match, winner)
            return
        if str(call.from_user.id) in s[bucket]:
            await call.answer("ဒီပွဲမှာ သင်ရွေးပြီးပါပြီ။", show_alert=True); return
        if game == "rps" and value not in RPS: return
        if game == "coin" and value not in ("heads","tails"): return
        if game in ("number","higher"):
            value_int = int(value)
            if not (1 <= value_int <= (10 if game == "number" else 100)): return
            value = value_int
        if game == "quiz": value = int(value)
        if game == "math": value = int(value)
        s[bucket][str(call.from_user.id)] = value
        if len(s[bucket]) == 2:
            v1, v2 = s[bucket][str(match["p1"])], s[bucket][str(match["p2"])]
            if game == "rps":
                if v1 == v2: winner = None
                elif RPS_BEATS[v1] == v2: winner = match["p1"]
                elif RPS_BEATS[v2] == v1: winner = match["p2"]
            elif game == "coin":
                secret = s["secret"]
                score1, score2 = (v1 == secret), (v2 == secret)
                winner = match["p1"] if score1 and not score2 else match["p2"] if score2 and not score1 else None
                s["reveal"] = secret
            elif game == "number":
                winner = match["p1"] if v1 > v2 else match["p2"] if v2 > v1 else None
            elif game == "higher":
                d1, d2 = abs(v1-s["target"]), abs(v2-s["target"])
                winner = match["p1"] if d1 < d2 else match["p2"] if d2 < d1 else None
                s["reveal"] = s["target"]
            elif game == "math":
                c1, c2 = v1 == s["answer"], v2 == s["answer"]
                winner = match["p1"] if c1 and not c2 else match["p2"] if c2 and not c1 else None
            elif game == "quiz":
                c1, c2 = v1 == s["answer"], v2 == s["answer"]
                winner = match["p1"] if c1 and not c2 else match["p2"] if c2 and not c1 else None
    elif game == "dice":
        if str(call.from_user.id) in s["rolled"]:
            await call.answer("သင် အန်စာတုံးပစ်ပြီးပါပြီ။", show_alert=True); return
        s["rolled"][str(call.from_user.id)] = True
        s["values"][str(call.from_user.id)] = random.randint(1,6)
        if len(s["rolled"]) == 2:
            v1, v2 = s["values"][str(match["p1"])], s["values"][str(match["p2"])]
            winner = match["p1"] if v1 > v2 else match["p2"] if v2 > v1 else None
    elif game == "memory":
        cell = int(value)
        if cell < 0 or cell >= 12 or cell in s["matched"]:
            await call.answer("ဒီကတ်ကို မရွေးနိုင်ပါ။", show_alert=True); return
        if s["turn"] != idx:
            await call.answer("အခု သင့်အလှည့်မဟုတ်ပါ။", show_alert=True); return
        # အရင်အလှည့်မှာ မတူညီခဲ့သော ကတ် ၂ ကတ်ကို နောက်အလှည့်စတင်ချိန်တွင် ဖုံးပါ။
        if len(s["revealed"]) == 2:
            s["revealed"] = []
            s["last"] = []
        if cell in s["revealed"]:
            await call.answer("ဒီကတ်ကို ရွေးပြီးပါပြီ။", show_alert=True); return
        s["revealed"].append(cell)
        s["last"].append(cell)
        if len(s["revealed"]) == 2:
            a,b = s["revealed"]
            if s["cards"][a] == s["cards"][b]:
                s["matched"].extend([a,b])
                s["scores"][idx] += 1
                s["revealed"] = []
                s["last"] = []
            else:
                # Keep both visible until the next player's click, then hide them.
                s["last"] = [a,b]
                s["turn"] = 1-idx
        if len(s["matched"]) == 12:
            winner = match["p1"] if s["scores"][0] > s["scores"][1] else match["p2"] if s["scores"][1] > s["scores"][0] else None
    else:
        await call.answer("ဒီဂိမ်း Move ကို မပံ့ပိုးသေးပါ။", show_alert=True); return

    await save_match(match)
    await call.answer(message)
    if winner != "continue":
        await finish_match(match, winner)
    else:
        await render_match(code)

@dp.callback_query(F.data.startswith("hint:"))
async def hint_callback(call: CallbackQuery):
    code = call.data.split(":",1)[1]
    match = await load_match(code)
    if not match or match["game"] != "word" or player_index(match, call.from_user.id) < 0:
        await call.answer("ဒီဂိမ်း မရှိပါ။", show_alert=True); return
    await call.answer(f"အရင်စာလုံး: {match['state']['word'][0]}", show_alert=True)

@dp.callback_query(F.data.startswith("rematch:"))
async def rematch_callback(call: CallbackQuery):
    code = call.data.split(":",1)[1]
    old = await load_match(code)
    if not old or call.from_user.id not in (old["p1"], old["p2"]):
        await call.answer("ဒီပွဲမှာ သင်မပါဝင်ပါ။", show_alert=True); return
    if old["status"] != "finished":
        await call.answer("ပွဲမပြီးသေးပါ။", show_alert=True); return
    # New match invite is created for the caller; the other player joins by link.
    new_code = await create_match(old["game"], call.from_user.id)
    link = await create_start_link(bot, f"join_{new_code}", encode=True)
    sent = await call.message.answer(
        f"🔄 Rematch ဖန်တီးပြီးပါပြီ။\nပွဲကုဒ်: <code>{new_code}</code>\nသူငယ်ချင်းကို Link ပြန်ပို့ပါ။",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👥 Rematch Invite", url=link)]])
    )
    await add_match_user(new_code, call.from_user.id, call.message.chat.id, sent.message_id)
    await call.answer()

@dp.message()
async def fallback(message: Message):
    if message.from_user:
        await upsert_user(message.from_user)
    await message.answer("🎮 ဂိမ်းဆော့ရန် /games ကိုနှိပ်ပါ။\nProfile: /profile\nLeaderboard: /leaderboard", reply_markup=main_menu())

async def main():
    if not BOT_TOKEN or BOT_TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE":
        raise RuntimeError("BOT_TOKEN မထည့်ရသေးပါ။ bot.py ထဲတွင် Token ထည့်ပါ သို့မဟုတ် BOT_TOKEN Environment Variable သတ်မှတ်ပါ။")
    await init_db()
    await bot.set_my_commands([
        BotCommand(command="start", description="Game World စတင်ရန်"),
        BotCommand(command="games", description="ဂိမ်းစာရင်း"),
        BotCommand(command="play", description="ဂိမ်းဆော့ရန်"),
        BotCommand(command="profile", description="ကိုယ့် Profile"),
        BotCommand(command="leaderboard", description="အနိုင်ရသူစာရင်း"),
        BotCommand(command="help", description="ကစားနည်း"),
        BotCommand(command="cancel", description="အကူအညီ"),
    ])
    log.info("GAME WORLD bot starting")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
