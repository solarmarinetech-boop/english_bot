import os
import random
import asyncio
import tempfile
import httpx
from gtts import gTTS
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile,
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ══════════════════════════════════════════════════════
#  КОНФИГ
# ══════════════════════════════════════════════════════
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВСТАВЬ_ТОКЕН")
GROQ_KEY  = os.getenv("GROQ_API_KEY", "ВСТАВЬ_GROQ_KEY")

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

# ══════════════════════════════════════════════════════
#  СОСТОЯНИЯ
# ══════════════════════════════════════════════════════
class S(StatesGroup):
    enter_name  = State()   # ввод имени
    choose_hero = State()   # выбор героя
    on_map      = State()   # карта тем
    answering   = State()   # выбор ответа кнопкой
    speaking    = State()   # ждём голосовое

# ══════════════════════════════════════════════════════
#  ДАННЫЕ ИГРОКА
# ══════════════════════════════════════════════════════
players: dict[int, dict] = {}

def new_player() -> dict:
    return {
        "name": "", "hero": 0,
        "coins": 0, "correct": 0, "streak": 0, "xp": 0, "level": 1,
        "topic": "", "questions": [], "idx": 0,
        "round_coins": 0, "round_correct": 0,
    }

def P(uid: int) -> dict:
    if uid not in players:
        players[uid] = new_player()
    return players[uid]

HEROES  = ["🧒 STRIKER", "👦 WINGER", "👧 KEEPER", "🧑 CAPTAIN"]
H_EMOJI = ["🧒", "👦", "👧", "🧑"]
LEVELS  = ["ROOKIE", "PLAYER", "PRO", "LEGEND", "ICON"]

# ══════════════════════════════════════════════════════
#  ВОПРОСЫ
# ══════════════════════════════════════════════════════
QDB = {
"he_his": [
  {"coach":"🐐 MESSI",   "scene":"Посмотри! Это Лука. Лука — мальчик.",         "q":"Как сказать «кто это»?",            "choices":["He","She","They","It"],    "ans":"He",    "say":"He is a boy",        "tr":"Он — мальчик"},
  {"coach":"🐐 MESSI",   "scene":"У Луки есть рюкзак с эмблемой Месси!",        "q":"Чей это рюкзак? «Это ___ рюкзак»", "choices":["his","her","their","our"], "ans":"his",   "say":"It is his bag",      "tr":"Это его сумка"},
  {"coach":"🦁 RONALDO", "scene":"Лука бьёт по мячу. Мяч летит в ворота!",      "q":"Кто бьёт по мячу?",                "choices":["He","She","They","We"],    "ans":"He",    "say":"He kicks the ball",  "tr":"Он бьёт по мячу"},
  {"coach":"🦁 RONALDO", "scene":"У Луки новые бутсы, как у Роналду!",          "q":"Чьи это бутсы?",                   "choices":["his","her","my","your"],   "ans":"his",   "say":"It is his boot",     "tr":"Это его бутса"},
  {"coach":"🐐 MESSI",   "scene":"Лука выиграл кубок! Все хлопают!",            "q":"Кто выиграл кубок?",               "choices":["He","She","They","I"],     "ans":"He",    "say":"He won the cup",     "tr":"Он выиграл кубок"},
],
"she_her": [
  {"coach":"🦁 RONALDO", "scene":"Это Соня. Она обожает футбол!",                "q":"Как сказать «кто это»?",           "choices":["She","He","They","It"],    "ans":"She",   "say":"She is a girl",          "tr":"Она — девочка"},
  {"coach":"🦁 RONALDO", "scene":"У Сони есть майка любимой команды!",           "q":"Чья это майка?",                   "choices":["her","his","their","our"], "ans":"her",   "say":"It is her shirt",        "tr":"Это её майка"},
  {"coach":"🦁 RONALDO", "scene":"Соня делает финт как Роналду! Красиво!",       "q":"Кто делает финт?",                 "choices":["She","He","They","I"],     "ans":"She",   "say":"She dribbles the ball",  "tr":"Она дриблирует"},
  {"coach":"⚡ MBAPPÉ",  "scene":"Соня — вратарь. Она поймала мяч!",             "q":"Чьи это перчатки?",                "choices":["her","his","my","your"],   "ans":"her",   "say":"It is her glove",        "tr":"Это её перчатка"},
  {"coach":"🦁 RONALDO", "scene":"Соня получила медаль! Она настоящий чемпион!", "q":"Кто получил медаль?",              "choices":["She","He","They","We"],    "ans":"She",   "say":"She got the medal",      "tr":"Она получила медаль"},
],
"they_their": [
  {"coach":"⚡ MBAPPÉ",  "scene":"Это Лука и Соня. Они — лучшие друзья!",        "q":"Как сказать «кто они»?",           "choices":["They","He","She","We"],    "ans":"They",  "say":"They are friends",       "tr":"Они друзья"},
  {"coach":"⚡ MBAPPÉ",  "scene":"У Луки и Сони есть мяч. Они пасуют!",          "q":"Чей это мяч?",                     "choices":["their","his","her","our"], "ans":"their", "say":"It is their ball",       "tr":"Это их мяч"},
  {"coach":"⚡ MBAPPÉ",  "scene":"Лука и Соня бегут к воротам! Быстро!",         "q":"Кто бежит к воротам?",             "choices":["They","He","She","I"],     "ans":"They",  "say":"They run to the goal",   "tr":"Они бегут к воротам"},
  {"coach":"⚡ MBAPPÉ",  "scene":"Лука и Соня носят одинаковые майки.",          "q":"Чьи это майки?",                   "choices":["their","his","her","my"],  "ans":"their", "say":"It is their shirt",      "tr":"Это их майки"},
  {"coach":"⚡ MBAPPÉ",  "scene":"Лука и Соня вместе выиграли матч!",            "q":"Кто выиграл матч?",                "choices":["They","He","She","We"],    "ans":"They",  "say":"They won the match",     "tr":"Они выиграли матч"},
],
}

def make_mixed():
    return (random.sample(QDB["he_his"], 2) +
            random.sample(QDB["she_her"], 2) +
            random.sample(QDB["they_their"], 1))

# ══════════════════════════════════════════════════════
#  КЛАВИАТУРЫ
# ══════════════════════════════════════════════════════
def kb_heroes():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=HEROES[0], callback_data="hero_0"),
         InlineKeyboardButton(text=HEROES[1], callback_data="hero_1")],
        [InlineKeyboardButton(text=HEROES[2], callback_data="hero_2"),
         InlineKeyboardButton(text=HEROES[3], callback_data="hero_3")],
    ])

def kb_topics():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👦 HE / HIS",     callback_data="topic_he_his")],
        [InlineKeyboardButton(text="👧 SHE / HER",    callback_data="topic_she_her")],
        [InlineKeyboardButton(text="👥 THEY / THEIR", callback_data="topic_they_their")],
        [InlineKeyboardButton(text="🏆 CHAMPIONS CUP · x2 монеты", callback_data="topic_mixed")],
    ])

def kb_answers(choices: list[str]):
    rows = []
    for i in range(0, len(choices), 2):
        rows.append([
            InlineKeyboardButton(text=choices[j], callback_data=f"ans_{choices[j]}")
            for j in range(i, min(i + 2, len(choices)))
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_next():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Следующий вопрос", callback_data="next_q")]
    ])

def kb_end():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗺 На карту", callback_data="go_map"),
         InlineKeyboardButton(text="🔄 Ещё раз",  callback_data="replay")],
    ])

# ══════════════════════════════════════════════════════
#  КАРТОЧКА ИГРОКА
# ══════════════════════════════════════════════════════
def card(p: dict) -> str:
    lvl = LEVELS[min(p["level"] - 1, 4)]
    stars = "⭐" * min(p["level"], 5)
    filled = int(p["xp"] / (p["level"] * 100) * 10)
    xp_bar = "▓" * filled + "░" * (10 - filled)
    return (
        f"┌──────────────────────┐\n"
        f"│ {H_EMOJI[p['hero']]}  {p['name']:<15}│\n"
        f"│ LVL {p['level']}  {lvl:<13}│\n"
        f"│ {stars:<22}│\n"
        f"├──────────────────────┤\n"
        f"│ ⚽ Монеты:   {p['coins']:<9}│\n"
        f"│ ✅ Правильно: {p['correct']:<8}│\n"
        f"│ 🔥 Серия:   {p['streak']:<9}│\n"
        f"│ XP [{xp_bar}]        │\n"
        f"│    {p['xp']} / {p['level']*100:<16}│\n"
        f"└──────────────────────┘"
    )

def check_level(p: dict) -> bool:
    if p["xp"] >= p["level"] * 100:
        p["xp"] -= p["level"] * 100
        p["level"] += 1
        return True
    return False

# ══════════════════════════════════════════════════════
#  GOOGLE TTS — озвучка
# ══════════════════════════════════════════════════════
async def say(text: str, msg: Message, caption: str = ""):
    """Генерирует голосовое через Google TTS и отправляет его."""
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = f.name
        # gTTS в executor чтобы не блокировать event loop
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: gTTS(text=text, lang="en", slow=True).save(tmp_path)
        )
        await msg.answer_voice(FSInputFile(tmp_path), caption=caption, parse_mode="Markdown")
    except Exception as e:
        print(f"[TTS ERROR] {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

# ══════════════════════════════════════════════════════
#  GROQ WHISPER — распознавание речи
# ══════════════════════════════════════════════════════
async def transcribe(audio_bytes: bytes) -> str:
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name
        async with httpx.AsyncClient(timeout=30) as client:
            with open(tmp_path, "rb") as f:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {GROQ_KEY}"},
                    files={"file": ("voice.ogg", f, "audio/ogg")},
                    data={"model": "whisper-large-v3", "language": "en", "response_format": "json"},
                )
        if resp.status_code == 200:
            return resp.json().get("text", "").strip().lower()
        print(f"[GROQ ERROR] {resp.status_code}: {resp.text}")
        return ""
    except Exception as e:
        print(f"[TRANSCRIBE ERROR] {e}")
        return ""
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

def check_speech(transcript: str, target: str) -> tuple[bool, float]:
    t_words = target.lower().split()
    s_words = transcript.lower().split()
    hits = sum(1 for w in t_words if any(w.strip(".,!?") in s for s in s_words))
    ratio = hits / len(t_words) if t_words else 0
    return ratio >= 0.5, ratio

# ══════════════════════════════════════════════════════
#  ОТПРАВИТЬ ВОПРОС
# ══════════════════════════════════════════════════════
async def send_question(target: Message, p: dict, state: FSMContext):
    q     = p["questions"][p["idx"]]
    total = len(p["questions"])
    bar   = "⬛" * p["idx"] + "⬜" * (total - p["idx"])
    await target.answer(
        f"⚽ *Вопрос {p['idx'] + 1} из {total}*\n{bar}\n\n"
        f"{q['coach']} говорит:\n_{q['scene']}_\n\n"
        f"❓ *{q['q']}*",
        reply_markup=kb_answers(q["choices"]),
        parse_mode="Markdown",
    )
    await state.set_state(S.answering)

# ══════════════════════════════════════════════════════
#  /start
# ══════════════════════════════════════════════════════
@dp.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    players[msg.from_user.id] = new_player()
    await msg.answer(
        "⚽ *FOOTBALL ENGLISH QUEST* ⚽\n\n"
        "🦁 *RONALDO говорит:*\n"
        "_Йо, чемпион! Учим английский вместе!\n"
        "Как тебя зовут?_",
        parse_mode="Markdown",
    )
    await state.set_state(S.enter_name)

# ══════════════════════════════════════════════════════
#  ИМЯ
# ══════════════════════════════════════════════════════
@dp.message(S.enter_name)
async def got_name(msg: Message, state: FSMContext):
    p = P(msg.from_user.id)
    p["name"] = msg.text.strip()[:14].upper()
    await msg.answer(
        f"🔥 Отлично, *{p['name']}*!\n\n"
        f"🐐 *MESSI говорит:*\n_Выбери своего игрока!_",
        reply_markup=kb_heroes(),
        parse_mode="Markdown",
    )
    await state.set_state(S.choose_hero)

# ══════════════════════════════════════════════════════
#  ВЫБОР ГЕРОЯ
# ══════════════════════════════════════════════════════
@dp.callback_query(S.choose_hero, F.data.startswith("hero_"))
async def got_hero(cb: CallbackQuery, state: FSMContext):
    p = P(cb.from_user.id)
    p["hero"] = int(cb.data.split("_")[1])
    await cb.message.edit_reply_markup()
    await cb.message.answer(
        f"✅ Ты выбрал *{HEROES[p['hero']]}*!\n\n"
        f"```\n{card(p)}\n```\n\n"
        f"⚡ *MBAPPÉ говорит:*\n_Без тренировок нет голов! Выбирай тему:_",
        reply_markup=kb_topics(),
        parse_mode="Markdown",
    )
    await state.set_state(S.on_map)
    await cb.answer()

# ══════════════════════════════════════════════════════
#  КАРТА — /map или кнопка
# ══════════════════════════════════════════════════════
async def show_map(target: Message, p: dict, state: FSMContext):
    await target.answer(
        f"```\n{card(p)}\n```\n\n🗺 *Выбирай тему:*",
        reply_markup=kb_topics(),
        parse_mode="Markdown",
    )
    await state.set_state(S.on_map)

@dp.message(Command("map"))
async def cmd_map(msg: Message, state: FSMContext):
    await show_map(msg, P(msg.from_user.id), state)

@dp.callback_query(F.data == "go_map")
async def cb_map(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_reply_markup()
    await show_map(cb.message, P(cb.from_user.id), state)
    await cb.answer()

# ══════════════════════════════════════════════════════
#  ВЫБОР ТЕМЫ
# ══════════════════════════════════════════════════════
@dp.callback_query(F.data.startswith("topic_"))
async def got_topic(cb: CallbackQuery, state: FSMContext):
    p     = P(cb.from_user.id)
    topic = cb.data.replace("topic_", "")
    p["topic"]         = topic
    p["questions"]     = make_mixed() if topic == "mixed" else random.sample(QDB[topic], 5)
    p["idx"]           = 0
    p["round_coins"]   = 0
    p["round_correct"] = 0
    labels = {"he_his":"HE / HIS","she_her":"SHE / HER",
              "they_their":"THEY / THEIR","mixed":"CHAMPIONS CUP 🏆"}
    await cb.message.edit_reply_markup()
    await cb.message.answer(
        f"🚀 *{labels[topic]}* — поехали!\n"
        + ("🌟 _x2 монеты за этот раунд!_" if topic == "mixed" else ""),
        parse_mode="Markdown",
    )
    await send_question(cb.message, p, state)
    await cb.answer()

# ══════════════════════════════════════════════════════
#  ОТВЕТ КНОПКОЙ
# ══════════════════════════════════════════════════════
@dp.callback_query(S.answering, F.data.startswith("ans_"))
async def got_answer(cb: CallbackQuery, state: FSMContext):
    p   = P(cb.from_user.id)
    val = cb.data.replace("ans_", "")
    q   = p["questions"][p["idx"]]

    await cb.message.edit_reply_markup()

    if val.lower() == q["ans"].lower():
        # ── ПРАВИЛЬНО → просим повторить голосом ──
        await cb.message.answer(
            f"✅ *ПРАВИЛЬНО!* — *{val}*\n"
            f"_{q['tr']}_\n\n"
            f"🎤 *Повтори вслух голосовым сообщением:*\n"
            f"🟢 *{q['say']}*\n\n"
            f"_Держи кнопку 🎤 и говори по-английски_",
            parse_mode="Markdown",
        )
        await say(q["say"], cb.message, caption=f"🔊 *Слушай и повторяй:* `{q['say']}`")
        await state.set_state(S.speaking)

    else:
        # ── НЕПРАВИЛЬНО → озвучиваем и едем дальше ──
        p["streak"] = 0
        await cb.message.answer(
            f"❌ *Неправильно!*\n\n"
            f"{q['coach']}: _Правильный ответ: *{q['ans']}*_\n"
            f"_{q['tr']}_",
            parse_mode="Markdown",
        )
        await say(q["say"], cb.message, caption=f"🔊 *Правильно звучит так:* `{q['say']}`")
        await cb.message.answer("👇", reply_markup=kb_next())

    await cb.answer()

# ══════════════════════════════════════════════════════
#  ГОЛОСОВОЕ СООБЩЕНИЕ
# ══════════════════════════════════════════════════════
@dp.message(S.speaking, F.voice)
async def got_voice(msg: Message, state: FSMContext):
    p = P(msg.from_user.id)
    q = p["questions"][p["idx"]]

    wait = await msg.answer("🎧 Слушаю...")
    file  = await bot.get_file(msg.voice.file_id)
    audio = (await bot.download_file(file.file_path)).read()
    transcript = await transcribe(audio)
    await wait.delete()

    # Не расслышали — просим ещё раз, остаёмся в S.speaking
    if not transcript:
        await msg.answer(
            "😕 *Не расслышал!* Попробуй ещё раз.\n"
            "_Говори чётко, не слишком быстро_",
            parse_mode="Markdown",
        )
        await say(q["say"], msg, caption=f"🔊 Ещё раз: `{q['say']}`")
        return

    ok, ratio = check_speech(transcript, q["say"])
    bonus = 15 if p["topic"] == "mixed" else 10

    if ok:
        # ── ХОРОШЕЕ ПРОИЗНОШЕНИЕ ──
        p["coins"]         += bonus
        p["correct"]       += 1
        p["streak"]        += 1
        p["round_correct"] += 1
        p["round_coins"]   += bonus
        p["xp"]            += 15
        leveled = check_level(p)

        grade = "🌟 Супер произношение!" if ratio > 0.85 else "👍 Хорошо!"
        text = (
            f"✅ *{grade}*\n"
            f"Я услышал: _{transcript}_\n\n"
            f"⚽ *+{bonus} монет!* Всего: {p['coins']}\n"
            f"🔥 Серия: {p['streak']}"
        )
        if leveled:
            text += f"\n\n⭐ *LEVEL UP! LVL {p['level']} — {LEVELS[min(p['level']-1,4)]}!*"
        await msg.answer(text, parse_mode="Markdown")
        await say(q["say"], msg, caption=f"🔊 *Эталонное произношение:* `{q['say']}`")
        await msg.answer("👇", reply_markup=kb_next())

    else:
        # ── ПЛОХОЕ ПРОИЗНОШЕНИЕ → слушаем снова, остаёмся в S.speaking ──
        await msg.answer(
            f"🔁 *Почти! Попробуй ещё раз.*\n"
            f"Я услышал: _{transcript}_\n"
            f"Надо сказать: *{q['say']}*",
            parse_mode="Markdown",
        )
        await say(q["say"], msg, caption=f"🔊 *Слушай внимательно:* `{q['say']}`")
        # остаёмся в S.speaking — ждём новую попытку

# ══════════════════════════════════════════════════════
#  СЛЕДУЮЩИЙ ВОПРОС
# ══════════════════════════════════════════════════════
@dp.callback_query(F.data == "next_q")
async def next_q(cb: CallbackQuery, state: FSMContext):
    p = P(cb.from_user.id)
    p["idx"] += 1
    await cb.message.edit_reply_markup()

    if p["idx"] >= len(p["questions"]):
        await cb.message.answer(
            f"🏆 *ФИНАЛЬНЫЙ СВИСТОК!*\n\n"
            f"```\n{card(p)}\n```\n\n"
            f"📊 *Результат раунда:*\n"
            f"✅ Правильных: {p['round_correct']} / {len(p['questions'])}\n"
            f"⚽ Монет заработано: {p['round_coins']}\n"
            f"🔥 Серия: {p['streak']}",
            reply_markup=kb_end(),
            parse_mode="Markdown",
        )
        await state.set_state(S.on_map)
    else:
        await send_question(cb.message, p, state)

    await cb.answer()

# ══════════════════════════════════════════════════════
#  REPLAY
# ══════════════════════════════════════════════════════
@dp.callback_query(F.data == "replay")
async def replay(cb: CallbackQuery, state: FSMContext):
    p     = P(cb.from_user.id)
    topic = p["topic"]
    p["questions"]     = make_mixed() if topic == "mixed" else random.sample(QDB[topic], 5)
    p["idx"]           = 0
    p["round_coins"]   = 0
    p["round_correct"] = 0
    await cb.message.edit_reply_markup()
    await cb.message.answer("🔄 *Начинаем снова!*", parse_mode="Markdown")
    await send_question(cb.message, p, state)
    await cb.answer()

# ══════════════════════════════════════════════════════
#  /stats
# ══════════════════════════════════════════════════════
@dp.message(Command("stats"))
async def cmd_stats(msg: Message):
    await msg.answer(f"```\n{card(P(msg.from_user.id))}\n```", parse_mode="Markdown")

# ══════════════════════════════════════════════════════
#  FALLBACK
# ══════════════════════════════════════════════════════
@dp.message(S.speaking)
async def speaking_fallback(msg: Message):
    await msg.answer(
        "🎤 *Жду голосовое сообщение!*\n"
        "_Держи кнопку 🎤 в Телеграм и говори по-английски_",
        parse_mode="Markdown",
    )

@dp.message()
async def fallback(msg: Message):
    await msg.answer(
        "/start — начать игру\n"
        "/map — карта тем\n"
        "/stats — моя карточка"
    )

# ══════════════════════════════════════════════════════
#  ЗАПУСК
# ══════════════════════════════════════════════════════
async def main():
    print("✅ Football English Quest bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
