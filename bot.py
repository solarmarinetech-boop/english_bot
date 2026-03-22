import os
import json
import random
import asyncio
import tempfile
import httpx
from gtts import gTTS
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    Voice, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    FSInputFile,
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ══════════════════════════════════════
#  CONFIG — вставь свои ключи сюда
# ══════════════════════════════════════
BOT_TOKEN  = os.getenv("BOT_TOKEN",  "ВСТАВЬ_TELEGRAM_TOKEN")
GROQ_KEY   = os.getenv("GROQ_API_KEY", "ВСТАВЬ_GROQ_KEY")

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

# ══════════════════════════════════════
#  STATES
# ══════════════════════════════════════
class Game(StatesGroup):
    enter_name  = State()
    choose_hero = State()
    map_screen  = State()
    answering   = State()
    speaking    = State()

# ══════════════════════════════════════
#  PLAYER DATA  (in-memory, per user)
# ══════════════════════════════════════
players: dict[int, dict] = {}

def get_player(uid: int) -> dict:
    if uid not in players:
        players[uid] = {
            "name": "", "hero": 0, "coins": 0,
            "correct": 0, "streak": 0, "xp": 0, "level": 1,
            "topic": "", "questions": [], "q_idx": 0,
            "round_coins": 0, "round_correct": 0,
            "locked": False,
        }
    return players[uid]

HEROES = ["🧒 STRIKER", "👦 WINGER", "👧 KEEPER", "🧑 CAPTAIN"]
HERO_EMOJI = ["🧒","👦","👧","🧑"]
LEVELS = ["ROOKIE","PLAYER","PRO","LEGEND","ICON"]

# ══════════════════════════════════════
#  QUESTIONS
# ══════════════════════════════════════
QUESTIONS = {
"he_his": [
  {"coach":"🐐 MESSI",   "scene":"Посмотри! Это Лука. Лука — мальчик.",          "q":"Как сказать «кто это»?",           "choices":["He","She","They","It"],       "ans":"He",    "say":"He is a boy",       "tr":"Он — мальчик"},
  {"coach":"🐐 MESSI",   "scene":"У Луки есть крутой рюкзак с Месси!",            "q":"Чей это рюкзак? «Это ___ рюкзак»", "choices":["his","her","their","our"],    "ans":"his",   "say":"It is his bag",     "tr":"Это его сумка"},
  {"coach":"🦁 RONALDO", "scene":"Лука бьёт по мячу. Мяч летит в ворота!",       "q":"Кто бьёт?",                        "choices":["He","She","They","We"],       "ans":"He",    "say":"He kicks the ball", "tr":"Он бьёт по мячу"},
  {"coach":"🦁 RONALDO", "scene":"У Луки новые бутсы. Как у Роналду!",            "q":"Чьи бутсы?",                       "choices":["his","her","my","your"],      "ans":"his",   "say":"It is his boot",    "tr":"Это его бутса"},
  {"coach":"🐐 MESSI",   "scene":"Лука выиграл кубок! Все хлопают!",              "q":"Кто выиграл?",                     "choices":["He","She","They","I"],        "ans":"He",    "say":"He won the cup",    "tr":"Он выиграл кубок"},
],
"she_her": [
  {"coach":"🦁 RONALDO", "scene":"Это Соня. Она любит футбол!",                   "q":"Как сказать «кто это»?",           "choices":["She","He","They","It"],       "ans":"She",   "say":"She is a girl",          "tr":"Она — девочка"},
  {"coach":"🦁 RONALDO", "scene":"У Сони есть майка её любимой команды!",         "q":"Чья это майка?",                   "choices":["her","his","their","our"],    "ans":"her",   "say":"It is her shirt",        "tr":"Это её майка"},
  {"coach":"🦁 RONALDO", "scene":"Соня финтит как Роналду! Красиво!",             "q":"Кто финтит?",                      "choices":["She","He","They","I"],        "ans":"She",   "say":"She dribbles the ball",  "tr":"Она дриблирует"},
  {"coach":"⚡ MBAPPÉ",  "scene":"Соня — вратарь. Она поймала мяч!",              "q":"Чьи перчатки?",                    "choices":["her","his","my","your"],      "ans":"her",   "say":"It is her glove",        "tr":"Это её перчатка"},
  {"coach":"🦁 RONALDO", "scene":"Соня получила медаль! Она чемпион!",            "q":"Кто получил медаль?",              "choices":["She","He","They","We"],       "ans":"She",   "say":"She got the medal",      "tr":"Она получила медаль"},
],
"they_their": [
  {"coach":"⚡ MBAPPÉ",  "scene":"Это Лука и Соня. Они играют вместе!",           "q":"Как сказать «кто они»?",           "choices":["They","He","She","We"],       "ans":"They",  "say":"They are friends",       "tr":"Они друзья"},
  {"coach":"⚡ MBAPPÉ",  "scene":"У Луки и Сони есть мяч. Они пасуют!",           "q":"Чей мяч? «Это ___ мяч»",          "choices":["their","his","her","our"],    "ans":"their", "say":"It is their ball",       "tr":"Это их мяч"},
  {"coach":"⚡ MBAPPÉ",  "scene":"Лука и Соня бегут к воротам! Быстро!",          "q":"Кто бежит?",                       "choices":["They","He","She","I"],        "ans":"They",  "say":"They run to the goal",   "tr":"Они бегут к воротам"},
  {"coach":"⚡ MBAPPÉ",  "scene":"Лука и Соня носят одинаковые майки.",           "q":"Чьи это майки?",                   "choices":["their","his","her","my"],     "ans":"their", "say":"It is their shirt",      "tr":"Это их майки"},
  {"coach":"⚡ MBAPPÉ",  "scene":"Лука и Соня выиграли! Команда радуется!",       "q":"Кто выиграл?",                     "choices":["They","He","She","We"],       "ans":"They",  "say":"They won the match",     "tr":"Они выиграли матч"},
],
}

def get_mixed():
    return random.sample(QUESTIONS["he_his"],2) + \
           random.sample(QUESTIONS["she_her"],2) + \
           random.sample(QUESTIONS["they_their"],1)

# ══════════════════════════════════════
#  KEYBOARDS
# ══════════════════════════════════════
def kb_heroes():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=h, callback_data=f"hero_{i}") for i,h in enumerate(HEROES[:2])],
        [InlineKeyboardButton(text=h, callback_data=f"hero_{i}") for i,h in enumerate(HEROES[2:], 2)],
    ])

def kb_topics():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👦 HE / HIS",       callback_data="topic_he_his")],
        [InlineKeyboardButton(text="👧 SHE / HER",      callback_data="topic_she_her")],
        [InlineKeyboardButton(text="👥 THEY / THEIR",   callback_data="topic_they_their")],
        [InlineKeyboardButton(text="🏆 CHAMPIONS CUP (x2 монеты)", callback_data="topic_mixed")],
    ])

def kb_choices(choices: list[str]):
    rows = []
    for i in range(0, len(choices), 2):
        row = [InlineKeyboardButton(text=choices[j], callback_data=f"ans_{choices[j]}")
               for j in range(i, min(i+2, len(choices)))]
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_after_speech():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Следующий вопрос", callback_data="next_q")],
    ])

def kb_round_end():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗺 На карту",   callback_data="go_map")],
        [InlineKeyboardButton(text="🔄 Ещё раз",    callback_data="replay")],
    ])

# ══════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════
def player_card(p: dict) -> str:
    hero  = HERO_EMOJI[p["hero"]]
    lvl   = LEVELS[min(p["level"]-1, 4)]
    stars = "⭐" * min(p["level"], 5)
    return (
        f"┌─────────────────────┐\n"
        f"│  {hero}  {p['name']:<14}│\n"
        f"│  LVL {p['level']}  {lvl:<12}│\n"
        f"│  {stars:<21}│\n"
        f"├─────────────────────┤\n"
        f"│ ⚽ Монеты:  {p['coins']:<9}│\n"
        f"│ ✅ Правильно: {p['correct']:<7}│\n"
        f"│ 🔥 Серия:  {p['streak']:<9}│\n"
        f"│ 📊 XP: {p['xp']}/{p['level']*100:<11}│\n"
        f"└─────────────────────┘"
    )

def xp_bar(p: dict) -> str:
    pct = int(p["xp"] / (p["level"] * 100) * 10)
    return "▓" * pct + "░" * (10 - pct)

def check_level(p: dict) -> bool:
    need = p["level"] * 100
    if p["xp"] >= need:
        p["xp"] -= need
        p["level"] += 1
        return True
    return False

async def send_question(message_or_cb, p: dict, state: FSMContext):
    q = p["questions"][p["q_idx"]]
    total = len(p["questions"])
    prog = int((p["q_idx"] / total) * 10)
    bar  = "⬛" * prog + "⬜" * (10 - prog)

    text = (
        f"⚽ *Вопрос {p['q_idx']+1} из {total}*\n"
        f"{bar}\n\n"
        f"{q['coach']} говорит:\n"
        f"_{q['scene']}_\n\n"
        f"❓ *{q['q']}*"
    )

    if isinstance(message_or_cb, CallbackQuery):
        await message_or_cb.message.answer(text, reply_markup=kb_choices(q["choices"]), parse_mode="Markdown")
    else:
        await message_or_cb.answer(text, reply_markup=kb_choices(q["choices"]), parse_mode="Markdown")

    await state.set_state(Game.answering)

# ══════════════════════════════════════
#  GROQ WHISPER — распознавание голоса
# ══════════════════════════════════════
async def transcribe_voice(file_bytes: bytes, filename: str = "voice.ogg") -> str:
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {GROQ_KEY}"}
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(file_bytes)
        tmp_path = f.name
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            with open(tmp_path, "rb") as audio:
                resp = await client.post(
                    url,
                    headers=headers,
                    files={"file": (filename, audio, "audio/ogg")},
                    data={"model": "whisper-large-v3", "language": "en", "response_format": "json"},
                )
            if resp.status_code == 200:
                return resp.json().get("text", "").strip().lower()
            return ""
    finally:
        os.unlink(tmp_path)

# ══════════════════════════════════════
#  GOOGLE TTS — озвучка правильного ответа
# ══════════════════════════════════════
async def speak_english(text: str, message: Message, caption: str = ""):
    """Генерирует голосовое сообщение с английской фразой и отправляет его."""
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = f.name
        tts = gTTS(text=text, lang="en", slow=True)  # slow=True — медленнее, чётче для детей
        tts.save(tmp_path)
        audio = FSInputFile(tmp_path)
        await message.answer_voice(audio, caption=caption, parse_mode="Markdown")
        os.unlink(tmp_path)
    except Exception as e:
        print(f"TTS error: {e}")

def eval_speech(transcript: str, target: str) -> tuple[bool, float]:
    t_words = target.lower().split()
    s_words = transcript.lower().split()
    hits = sum(1 for w in t_words if any(w.strip(".,!?") in sw for sw in s_words))
    ratio = hits / len(t_words) if t_words else 0
    return ratio >= 0.5, ratio

# ══════════════════════════════════════
#  /start
# ══════════════════════════════════════
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    uid = message.from_user.id
    players[uid] = {
        "name": "", "hero": 0, "coins": 0,
        "correct": 0, "streak": 0, "xp": 0, "level": 1,
        "topic": "", "questions": [], "q_idx": 0,
        "round_coins": 0, "round_correct": 0, "locked": False,
    }
    await message.answer(
        "⚽ *FOOTBALL ENGLISH QUEST* ⚽\n\n"
        "🦁 *RONALDO говорит:*\n"
        "_Йо! Хочешь стать звездой как я?\n"
        "Сначала нужно выучить английский!\n\n"
        "Как тебя зовут, чемпион?_",
        parse_mode="Markdown"
    )
    await state.set_state(Game.enter_name)

# ══════════════════════════════════════
#  ENTER NAME
# ══════════════════════════════════════
@dp.message(Game.enter_name)
async def enter_name(message: Message, state: FSMContext):
    name = message.text.strip()[:14].upper()
    p = get_player(message.from_user.id)
    p["name"] = name
    await message.answer(
        f"🔥 Отлично, *{name}*!\n\n"
        f"🐐 *MESSI говорит:*\n"
        f"_Теперь выбери своего игрока!_",
        reply_markup=kb_heroes(),
        parse_mode="Markdown"
    )
    await state.set_state(Game.choose_hero)

# ══════════════════════════════════════
#  CHOOSE HERO
# ══════════════════════════════════════
@dp.callback_query(Game.choose_hero, F.data.startswith("hero_"))
async def choose_hero(cb: CallbackQuery, state: FSMContext):
    idx = int(cb.data.split("_")[1])
    p = get_player(cb.from_user.id)
    p["hero"] = idx
    await cb.message.edit_reply_markup()
    await cb.message.answer(
        f"✅ Ты выбрал *{HEROES[idx]}*!\n\n"
        f"```\n{player_card(p)}\n```\n"
        f"XP: [{xp_bar(p)}] {p['xp']}/{p['level']*100}\n\n"
        f"⚡ *MBAPPÉ говорит:*\n_Без разминки не бывает голов!\nВыбирай тему и вперёд!_",
        reply_markup=kb_topics(),
        parse_mode="Markdown"
    )
    await state.set_state(Game.map_screen)
    await cb.answer()

# ══════════════════════════════════════
#  /map  — вернуться на карту
# ══════════════════════════════════════
@dp.message(Command("map"))
@dp.callback_query(F.data == "go_map")
async def go_map(event, state: FSMContext):
    if isinstance(event, CallbackQuery):
        uid = event.from_user.id
        msg = event.message
        await event.answer()
    else:
        uid = event.from_user.id
        msg = event

    p = get_player(uid)
    await msg.answer(
        f"```\n{player_card(p)}\n```\n"
        f"XP: [{xp_bar(p)}] {p['xp']}/{p['level']*100}\n\n"
        f"🗺 Выбирай тему:",
        reply_markup=kb_topics(),
        parse_mode="Markdown"
    )
    await state.set_state(Game.map_screen)

# ══════════════════════════════════════
#  CHOOSE TOPIC
# ══════════════════════════════════════
@dp.callback_query(F.data.startswith("topic_"))
async def choose_topic(cb: CallbackQuery, state: FSMContext):
    topic = cb.data.replace("topic_", "")
    p = get_player(cb.from_user.id)
    p["topic"] = topic

    if topic == "mixed":
        qs = get_mixed()
    else:
        qs = random.sample(QUESTIONS[topic], 5)

    p["questions"]     = qs
    p["q_idx"]         = 0
    p["round_coins"]   = 0
    p["round_correct"] = 0
    p["locked"]        = False

    labels = {"he_his":"HE / HIS","she_her":"SHE / HER","they_their":"THEY / THEIR","mixed":"CHAMPIONS CUP 🏆"}
    await cb.message.edit_reply_markup()
    await cb.message.answer(
        f"🚀 Начинаем *{labels.get(topic,topic)}*!\n"
        f"{'🌟 x2 монеты за этот раунд!' if topic=='mixed' else ''}",
        parse_mode="Markdown"
    )
    await send_question(cb, p, state)
    await cb.answer()

# ══════════════════════════════════════
#  ANSWER
# ══════════════════════════════════════
@dp.callback_query(Game.answering, F.data.startswith("ans_"))
async def handle_answer(cb: CallbackQuery, state: FSMContext):
    p = get_player(cb.from_user.id)
    if p["locked"]:
        await cb.answer("Подожди!")
        return

    p["locked"] = True
    val = cb.data.replace("ans_", "")
    q   = p["questions"][p["q_idx"]]

    await cb.message.edit_reply_markup()

    if val.lower() == q["ans"].lower():
        await cb.message.answer(
            f"✅ *ПРАВИЛЬНО!* — *{val}*\n\n"
            f"_{q['tr']}_\n\n"
            f"🎤 *Теперь повтори это вслух голосовым сообщением:*\n\n"
            f"🟢  *{q['say']}*\n\n"
            f"_Запиши голосовое — держи кнопку 🎤 в Телеграм_",
            parse_mode="Markdown"
        )
        # Отправляем эталонное произношение
        await speak_english(
            q["say"],
            cb.message,
            caption=f"🔊 *Слушай как правильно:* _{q['say']}_"
        )
        await state.set_state(Game.speaking)
    else:
        p["streak"] = 0
        coach = q["coach"]
        await cb.message.answer(
            f"❌ *Неправильно!*\n\n"
            f"{coach} говорит: _«Не так! Правильно: *{q['ans']}*»_\n\n"
            f"_{q['tr']}_",
            parse_mode="Markdown"
        )
        # Озвучиваем правильный ответ
        await speak_english(
            q["say"],
            cb.message,
            caption=f"🔊 *Правильно звучит так:* _{q['say']}_"
        )
        await cb.message.answer("", reply_markup=kb_after_speech())

    await cb.answer()

# ══════════════════════════════════════
#  VOICE MESSAGE
# ══════════════════════════════════════
@dp.message(Game.speaking, F.voice)
async def handle_voice(message: Message, state: FSMContext):
    p = get_player(message.from_user.id)
    q = p["questions"][p["q_idx"]]

    wait_msg = await message.answer("🎧 Слушаю твой ответ...")

    # Скачать голосовое
    file = await bot.get_file(message.voice.file_id)
    file_bytes = await bot.download_file(file.file_path)
    audio_data = file_bytes.read()

    # Распознать через Groq Whisper
    transcript = await transcribe_voice(audio_data)

    await wait_msg.delete()

    if not transcript:
        await message.answer(
            "😕 Не смог расслышать. Попробуй ещё раз!\n"
            "_Говори чётко и не слишком быстро_",
            reply_markup=kb_after_speech(),
            parse_mode="Markdown"
        )
        return

    ok, ratio = eval_speech(transcript, q["say"])
    bonus = 15 if p["topic"] == "mixed" else 10

    if ok:
        p["coins"]        += bonus
        p["correct"]      += 1
        p["streak"]       += 1
        p["round_correct"]+= 1
        p["round_coins"]  += bonus
        p["xp"]           += 15

        leveled = check_level(p)
        stars = "🌟" if ratio > 0.85 else "👍"

        text = (
            f"{stars} *Отлично!*\n\n"
            f"Я услышал: _{transcript}_\n\n"
            f"{'🌟 Супер произношение!' if ratio > 0.85 else '👍 Хорошо!'}\n\n"
            f"⚽ *+{bonus} монет!*  Всего: {p['coins']}\n"
            f"🔥 Серия: {p['streak']}"
        )
        if leveled:
            text += f"\n\n⭐ *LEVEL UP! Теперь ты LVL {p['level']} — {LEVELS[min(p['level']-1,4)]}!*"

        await message.answer(text, parse_mode="Markdown")
        # Эталонное произношение после похвалы
        await speak_english(
            q["say"],
            message,
            caption=f"🔊 *А вот идеальное произношение:* _{q['say']}_"
        )
    else:
        text = (
            f"🔁 Почти! Попробуй ещё раз!\n\n"
            f"Я услышал: _{transcript}_\n"
            f"Надо сказать: *{q['say']}*"
        )
        await message.answer(text, parse_mode="Markdown")
        # Озвучиваем правильный вариант чтобы ребёнок услышал
        await speak_english(
            q["say"],
            message,
            caption=f"🔊 *Слушай ещё раз и повтори:* _{q['say']}_"
        )

    await message.answer("", reply_markup=kb_after_speech())

# ══════════════════════════════════════
#  NEXT QUESTION
# ══════════════════════════════════════
@dp.callback_query(F.data == "next_q")
async def next_question(cb: CallbackQuery, state: FSMContext):
    p = get_player(cb.from_user.id)
    p["q_idx"] += 1
    p["locked"]  = False
    await cb.message.edit_reply_markup()

    if p["q_idx"] >= len(p["questions"]):
        # Round complete
        await cb.message.answer(
            f"🏆 *ФИНАЛЬНЫЙ СВИСТОК!*\n\n"
            f"```\n{player_card(p)}\n```\n"
            f"XP: [{xp_bar(p)}] {p['xp']}/{p['level']*100}\n\n"
            f"📊 *Результат раунда:*\n"
            f"✅ Правильных: {p['round_correct']} / {len(p['questions'])}\n"
            f"⚽ Монет заработано: {p['round_coins']}\n"
            f"🔥 Серия: {p['streak']}",
            reply_markup=kb_round_end(),
            parse_mode="Markdown"
        )
        await state.set_state(Game.map_screen)
    else:
        await send_question(cb, p, state)

    await cb.answer()

# ══════════════════════════════════════
#  REPLAY
# ══════════════════════════════════════
@dp.callback_query(F.data == "replay")
async def replay(cb: CallbackQuery, state: FSMContext):
    p = get_player(cb.from_user.id)
    topic = p["topic"]
    if topic == "mixed":
        qs = get_mixed()
    else:
        qs = random.sample(QUESTIONS[topic], 5)
    p["questions"]     = qs
    p["q_idx"]         = 0
    p["round_coins"]   = 0
    p["round_correct"] = 0
    p["locked"]        = False
    await cb.message.edit_reply_markup()
    await cb.message.answer("🔄 Начинаем снова!")
    await send_question(cb, p, state)
    await cb.answer()

# ══════════════════════════════════════
#  /stats
# ══════════════════════════════════════
@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    p = get_player(message.from_user.id)
    await message.answer(
        f"```\n{player_card(p)}\n```\n"
        f"XP: [{xp_bar(p)}] {p['xp']}/{p['level']*100}",
        parse_mode="Markdown"
    )

# ══════════════════════════════════════
#  FALLBACK
# ══════════════════════════════════════
@dp.message(Game.speaking)
async def speaking_fallback(message: Message):
    await message.answer(
        "🎤 Отправь *голосовое сообщение*!\n"
        "_Держи кнопку 🎤 в Телеграм и говори_",
        parse_mode="Markdown"
    )

@dp.message()
async def fallback(message: Message, state: FSMContext):
    await message.answer(
        "Напиши /start чтобы начать игру\n"
        "или /map чтобы вернуться на карту\n"
        "или /stats чтобы посмотреть статистику"
    )

# ══════════════════════════════════════
#  RUN
# ══════════════════════════════════════
async def main():
    print("✅ Bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
