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
    enter_name  = State()
    choose_hero = State()
    on_map      = State()
    lesson      = State()   # показ урока (объяснение)
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
#  УРОКИ — объяснение правил перед темой
#  text_ru  = текст на русском (показываем в чате)
#  tts_text = что произносит TTS (на английском, медленно)
#  tts_ru   = голосовое объяснение на русском
# ══════════════════════════════════════════════════════
LESSONS = {
    # ── Местоимения ──────────────────────────────────
    "he_his": {
        "coach": "🐐 MESSI",
        "title": "HE / HIS",
        "text": (
            "📖 *Урок: HE и HIS*\n\n"
            "👦 *HE* — это «он». Говорим про мальчика или мужчину.\n"
            "   Пример: _He is a boy._ — Он мальчик.\n\n"
            "🎒 *HIS* — это «его». Говорим про вещи мальчика.\n"
            "   Пример: _It is his bag._ — Это его сумка.\n\n"
            "💡 Запомни: *HE* — кто? *HIS* — чей?"
        ),
        "tts_ru": (
            "Привет! Я Месси. Сегодня учим два слова. "
            "Первое слово — HE. Это значит ОН. "
            "Мы говорим HE когда говорим про мальчика. "
            "Например: He is a boy. Он мальчик. "
            "Второе слово — HIS. Это значит ЕГО. "
            "Мы говорим HIS когда говорим про вещи мальчика. "
            "Например: It is his bag. Это его сумка. "
            "Запомни: HE — это кто? А HIS — это чей? "
            "Поехали тренироваться!"
        ),
    },
    "she_her": {
        "coach": "🦁 RONALDO",
        "title": "SHE / HER",
        "text": (
            "📖 *Урок: SHE и HER*\n\n"
            "👧 *SHE* — это «она». Говорим про девочку или женщину.\n"
            "   Пример: _She is a girl._ — Она девочка.\n\n"
            "👗 *HER* — это «её». Говорим про вещи девочки.\n"
            "   Пример: _It is her shirt._ — Это её майка.\n\n"
            "💡 Запомни: *SHE* — кто? *HER* — чей?"
        ),
        "tts_ru": (
            "Привет! Я Роналду. Сегодня учим два слова. "
            "Первое слово — SHE. Это значит ОНА. "
            "Мы говорим SHE когда говорим про девочку. "
            "Например: She is a girl. Она девочка. "
            "Второе слово — HER. Это значит ЕЁ. "
            "Мы говорим HER когда говорим про вещи девочки. "
            "Например: It is her shirt. Это её майка. "
            "Запомни: SHE — это кто? А HER — это чей? "
            "Вперёд на тренировку!"
        ),
    },
    "they_their": {
        "coach": "⚡ MBAPPÉ",
        "title": "THEY / THEIR",
        "text": (
            "📖 *Урок: THEY и THEIR*\n\n"
            "👫 *THEY* — это «они». Говорим про двух и более людей.\n"
            "   Пример: _They are friends._ — Они друзья.\n\n"
            "🎽 *THEIR* — это «их». Говорим про вещи группы людей.\n"
            "   Пример: _It is their ball._ — Это их мяч.\n\n"
            "💡 Запомни: *THEY* — кто? *THEIR* — чей?"
        ),
        "tts_ru": (
            "Привет! Я Мбаппе. Сегодня учим два слова. "
            "Первое слово — THEY. Это значит ОНИ. "
            "Мы говорим THEY когда говорим про нескольких людей. "
            "Например: They are friends. Они друзья. "
            "Второе слово — THEIR. Это значит ИХ. "
            "Мы говорим THEIR когда говорим про вещи этих людей. "
            "Например: It is their ball. Это их мяч. "
            "Запомни: THEY — это кто? А THEIR — это чей? "
            "Быстро на поле!"
        ),
    },
    # ── Времена ──────────────────────────────────────
    "present_simple": {
        "coach": "🐐 MESSI",
        "title": "PRESENT SIMPLE",
        "text": (
            "📖 *Урок: Present Simple — настоящее время*\n\n"
            "⚽ Используем когда говорим о том, что происходит *всегда* или *регулярно*.\n\n"
            "📌 *Формула:*\n"
            "   I / You / We / They + глагол\n"
            "   He / She / It + глагол *+s*\n\n"
            "📝 *Примеры:*\n"
            "   _I play football._ — Я играю в футбол.\n"
            "   _He plays football._ — Он играет в футбол.\n"
            "   _They play every day._ — Они играют каждый день.\n\n"
            "💡 Ключевые слова: *every day, always, usually, often*"
        ),
        "tts_ru": (
            "Привет! Я Месси. Сегодня учим Present Simple. "
            "Это настоящее время. Мы его используем когда говорим о том, что происходит всегда или регулярно. "
            "Например, каждый день, всегда, обычно. "
            "Формула простая. Я говорю: I play football. Я играю в футбол. "
            "Если говорю про него, добавляю букву S в конце глагола: He plays football. Он играет в футбол. "
            "Запомни: если это HE, SHE, или IT — добавляй S к глаголу! "
            "Например: She runs. He kicks. It bounces. "
            "Вперёд практиковаться!"
        ),
    },
    "past_simple": {
        "coach": "🦁 RONALDO",
        "title": "PAST SIMPLE",
        "text": (
            "📖 *Урок: Past Simple — прошедшее время*\n\n"
            "⚽ Используем когда говорим о том, что уже *произошло*.\n\n"
            "📌 *Формула:*\n"
            "   глагол + *ed* (для правильных глаголов)\n"
            "   или особая форма (для неправильных)\n\n"
            "📝 *Примеры:*\n"
            "   _I played football._ — Я играл в футбол.\n"
            "   _He scored a goal._ — Он забил гол.\n"
            "   _They won the match._ — Они выиграли матч.\n\n"
            "💡 Ключевые слова: *yesterday, last week, ago*"
        ),
        "tts_ru": (
            "Привет! Я Роналду. Сегодня учим Past Simple. "
            "Это прошедшее время. Мы его используем когда говорим о том, что уже случилось. "
            "Например, вчера, на прошлой неделе, давно. "
            "Для большинства глаголов просто добавляем ED в конце. "
            "Например: play становится played. Я играл — I played. "
            "Он сыграл — He played. "
            "Но некоторые глаголы особенные! Они меняются полностью. "
            "Например: win становится won. Они выиграли — They won. "
            "score становится scored. Он забил — He scored. "
            "Запомни ключевые слова: yesterday — вчера, last week — на прошлой неделе. "
            "Тренируемся!"
        ),
    },
    "future_simple": {
        "coach": "⚡ MBAPPÉ",
        "title": "FUTURE SIMPLE",
        "text": (
            "📖 *Урок: Future Simple — будущее время*\n\n"
            "⚽ Используем когда говорим о том, что *произойдёт*.\n\n"
            "📌 *Формула:*\n"
            "   *will* + глагол (одинаково для всех!)\n\n"
            "📝 *Примеры:*\n"
            "   _I will play tomorrow._ — Я буду играть завтра.\n"
            "   _He will score a goal._ — Он забьёт гол.\n"
            "   _They will win._ — Они выиграют.\n\n"
            "💡 Ключевые слова: *tomorrow, next week, soon*\n"
            "🔑 *Will* не меняется! Для всех одинаково."
        ),
        "tts_ru": (
            "Привет! Я Мбаппе. Сегодня учим Future Simple. "
            "Это будущее время. Мы его используем когда говорим о том, что произойдёт. "
            "Например, завтра, на следующей неделе, скоро. "
            "Формула очень простая! Перед глаголом всегда ставим слово WILL. "
            "И это слово никогда не меняется! Для всех одинаково. "
            "Я буду играть — I will play. "
            "Он забьёт гол — He will score. "
            "Они выиграют — They will win. "
            "Запомни: WILL плюс глагол — и ты говоришь о будущем! "
            "Давай практиковаться!"
        ),
    },
    "present_continuous": {
        "coach": "🌟 NEYMAR",
        "title": "PRESENT CONTINUOUS",
        "text": (
            "📖 *Урок: Present Continuous — действие прямо сейчас*\n\n"
            "⚽ Используем когда говорим о том, что происходит *прямо сейчас*.\n\n"
            "📌 *Формула:*\n"
            "   *am / is / are* + глагол *+ing*\n"
            "   I am, He/She/It is, We/You/They are\n\n"
            "📝 *Примеры:*\n"
            "   _I am playing._ — Я играю (сейчас).\n"
            "   _He is running._ — Он бежит (сейчас).\n"
            "   _They are winning._ — Они побеждают (сейчас).\n\n"
            "💡 Ключевые слова: *now, right now, look!*"
        ),
        "tts_ru": (
            "Привет! Я Неймар. Сегодня учим Present Continuous. "
            "Это время для действий, которые происходят прямо сейчас! "
            "Прямо в эту секунду. "
            "Формула: берём am, is или are, и добавляем ING к глаголу. "
            "Я сейчас играю — I am playing. "
            "Он сейчас бежит — He is running. "
            "Они сейчас побеждают — They are winning. "
            "Как запомнить? "
            "Я — всегда I am. "
            "Он, она, оно — всегда is. "
            "Мы, вы, они — всегда are. "
            "И не забудь добавить ING к глаголу! "
            "Поехали!"
        ),
    },
    "mixed": {
        "coach": "🏆 ALL STARS",
        "title": "CHAMPIONS CUP",
        "text": (
            "🏆 *CHAMPIONS CUP — всё вместе!*\n\n"
            "Здесь будут вопросы на все темы:\n"
            "👦 HE / HIS · 👧 SHE / HER · 👥 THEY / THEIR\n"
            "⏰ Present Simple · Past Simple\n"
            "🔮 Future Simple · Present Continuous\n\n"
            "💰 *x2 монеты за каждый правильный ответ!*"
        ),
        "tts_ru": (
            "Чемпионы! Это финальный раунд. "
            "Здесь вопросы на все темы которые ты учил. "
            "Местоимения и все четыре времени. "
            "За каждый правильный ответ ты получаешь двойные монеты! "
            "Покажи всё что умеешь. Удачи!"
        ),
    },
}

# ══════════════════════════════════════════════════════
#  ВОПРОСЫ
# ══════════════════════════════════════════════════════
QDB = {
# ── Местоимения ──────────────────────────────────────
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

# ── Present Simple ────────────────────────────────────
"present_simple": [
  {"coach":"🐐 MESSI",   "scene":"Лука каждый день тренируется на поле.",        "q":"Выбери правильную форму:",         "choices":["He plays","He play","He playing","He played"],      "ans":"He plays",      "say":"He plays every day",       "tr":"Он играет каждый день"},
  {"coach":"🐐 MESSI",   "scene":"Соня всегда приходит на тренировку первой.",   "q":"Выбери правильную форму:",         "choices":["She runs","She run","She running","She runned"],    "ans":"She runs",      "say":"She runs very fast",       "tr":"Она бегает очень быстро"},
  {"coach":"🐐 MESSI",   "scene":"Команда обычно побеждает дома.",               "q":"Выбери правильную форму:",         "choices":["They win","They wins","They winning","They winned"], "ans":"They win",     "say":"They win every game",      "tr":"Они выигрывают каждую игру"},
  {"coach":"🐐 MESSI",   "scene":"Вратарь всегда ловит мяч.",                   "q":"Выбери правильную форму:",         "choices":["He catches","He catch","He catched","He catching"],  "ans":"He catches",   "say":"He catches the ball",      "tr":"Он ловит мяч"},
  {"coach":"🐐 MESSI",   "scene":"Месси говорит: я всегда забиваю голы!",        "q":"Выбери правильную форму:",         "choices":["I score","I scores","I scoring","I scored"],        "ans":"I score",      "say":"I score many goals",       "tr":"Я забиваю много голов"},
],

# ── Past Simple ───────────────────────────────────────
"past_simple": [
  {"coach":"🦁 RONALDO", "scene":"Вчера Лука забил потрясающий гол!",            "q":"Выбери правильную форму:",         "choices":["He scored","He scores","He scoring","He score"],    "ans":"He scored",    "say":"He scored yesterday",      "tr":"Он забил вчера"},
  {"coach":"🦁 RONALDO", "scene":"На прошлой неделе команда выиграла финал.",    "q":"Выбери правильную форму:",         "choices":["They won","They win","They wins","They winning"],   "ans":"They won",     "say":"They won the final",       "tr":"Они выиграли финал"},
  {"coach":"🦁 RONALDO", "scene":"Соня сыграла отличный матч вчера.",            "q":"Выбери правильную форму:",         "choices":["She played","She plays","She play","She playing"],  "ans":"She played",   "say":"She played great",         "tr":"Она сыграла отлично"},
  {"coach":"🦁 RONALDO", "scene":"Два дня назад Роналду пробежал 12 км!",        "q":"Выбери правильную форму:",         "choices":["He ran","He runs","He run","He running"],           "ans":"He ran",       "say":"He ran twelve kilometers",  "tr":"Он пробежал 12 километров"},
  {"coach":"🦁 RONALDO", "scene":"Прошлым летом я тренировался каждый день.",    "q":"Выбери правильную форму:",         "choices":["I trained","I train","I trains","I training"],      "ans":"I trained",    "say":"I trained every day",      "tr":"Я тренировался каждый день"},
],

# ── Future Simple ─────────────────────────────────────
"future_simple": [
  {"coach":"⚡ MBAPPÉ",  "scene":"Завтра Мбаппе выйдет на поле!",               "q":"Выбери правильную форму:",         "choices":["He will play","He plays","He played","He playing"],      "ans":"He will play",   "say":"He will play tomorrow",    "tr":"Он сыграет завтра"},
  {"coach":"⚡ MBAPPÉ",  "scene":"На следующей неделе команда выиграет кубок.",  "q":"Выбери правильную форму:",         "choices":["They will win","They win","They wins","They won"],        "ans":"They will win",  "say":"They will win the cup",    "tr":"Они выиграют кубок"},
  {"coach":"⚡ MBAPPÉ",  "scene":"Скоро Соня станет лучшим игроком!",           "q":"Выбери правильную форму:",         "choices":["She will become","She becomes","She became","She become"], "ans":"She will become","say":"She will be the best",    "tr":"Она станет лучшей"},
  {"coach":"⚡ MBAPPÉ",  "scene":"Завтра я забью три гола — обещаю!",           "q":"Выбери правильную форму:",         "choices":["I will score","I score","I scored","I scoring"],          "ans":"I will score",   "say":"I will score three goals", "tr":"Я забью три гола"},
  {"coach":"⚡ MBAPPÉ",  "scene":"Следующий матч будет очень сложным.",         "q":"Выбери правильную форму:",         "choices":["It will be","It is","It was","It being"],                "ans":"It will be",    "say":"It will be very hard",     "tr":"Это будет очень сложно"},
],

# ── Present Continuous ────────────────────────────────
"present_continuous": [
  {"coach":"🌟 NEYMAR",  "scene":"Смотри! Лука прямо сейчас бежит к воротам!",  "q":"Выбери правильную форму:",         "choices":["He is running","He runs","He ran","He run"],              "ans":"He is running",  "say":"He is running now",        "tr":"Он сейчас бежит"},
  {"coach":"🌟 NEYMAR",  "scene":"Соня сейчас тренируется на поле.",            "q":"Выбери правильную форму:",         "choices":["She is training","She trains","She trained","She train"],  "ans":"She is training","say":"She is training now",       "tr":"Она сейчас тренируется"},
  {"coach":"🌟 NEYMAR",  "scene":"Команда прямо сейчас побеждает!",             "q":"Выбери правильную форму:",         "choices":["They are winning","They win","They won","They wins"],      "ans":"They are winning","say":"They are winning now",     "tr":"Они сейчас побеждают"},
  {"coach":"🌟 NEYMAR",  "scene":"Неймар прямо сейчас делает финт!",            "q":"Выбери правильную форму:",         "choices":["He is dribbling","He dribbles","He dribbled","He dribble"],"ans":"He is dribbling","say":"He is dribbling the ball",  "tr":"Он сейчас дриблирует"},
  {"coach":"🌟 NEYMAR",  "scene":"Я сейчас играю! Не мешай!",                  "q":"Выбери правильную форму:",         "choices":["I am playing","I play","I played","I plays"],             "ans":"I am playing",   "say":"I am playing right now",   "tr":"Я сейчас играю"},
],
}

def make_mixed():
    return (
        random.sample(QDB["he_his"], 1) +
        random.sample(QDB["she_her"], 1) +
        random.sample(QDB["present_simple"], 1) +
        random.sample(QDB["past_simple"], 1) +
        random.sample(QDB["future_simple"], 1) +
        random.sample(QDB["present_continuous"], 1)
    )

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
        [InlineKeyboardButton(text="👦 HE / HIS",           callback_data="topic_he_his")],
        [InlineKeyboardButton(text="👧 SHE / HER",          callback_data="topic_she_her")],
        [InlineKeyboardButton(text="👥 THEY / THEIR",       callback_data="topic_they_their")],
        [InlineKeyboardButton(text="━━━━━━━━━━━━━━━━━━━",   callback_data="noop")],
        [InlineKeyboardButton(text="⏰ Present Simple",     callback_data="topic_present_simple")],
        [InlineKeyboardButton(text="⏪ Past Simple",        callback_data="topic_past_simple")],
        [InlineKeyboardButton(text="⏩ Future Simple",      callback_data="topic_future_simple")],
        [InlineKeyboardButton(text="▶️ Present Continuous", callback_data="topic_present_continuous")],
        [InlineKeyboardButton(text="━━━━━━━━━━━━━━━━━━━",   callback_data="noop")],
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

def kb_start_quiz():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚽ Поехали! Начать вопросы", callback_data="start_quiz")]
    ])

def kb_next():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Следующий вопрос", callback_data="next_q")]
    ])

def kb_end():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗺 На карту", callback_data="go_map"),
         InlineKeyboardButton(text="🔄 Ещё раз",  callback_data="replay")],
    ])

def kb_noop():
    return InlineKeyboardMarkup(inline_keyboard=[])

# ══════════════════════════════════════════════════════
#  КАРТОЧКА ИГРОКА
# ══════════════════════════════════════════════════════
def card(p: dict) -> str:
    lvl    = LEVELS[min(p["level"] - 1, 4)]
    stars  = "⭐" * min(p["level"], 5)
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
#  GOOGLE TTS
# ══════════════════════════════════════════════════════
async def say(text: str, msg: Message, caption: str = "", lang: str = "en", slow: bool = True):
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = f.name
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: gTTS(text=text, lang=lang, slow=slow).save(tmp_path)
        )
        await msg.answer_voice(FSInputFile(tmp_path), caption=caption, parse_mode="Markdown")
    except Exception as e:
        print(f"[TTS ERROR] {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

# ══════════════════════════════════════════════════════
#  GROQ WHISPER
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
#  ПОКАЗАТЬ УРОК (объяснение + голосовое)
# ══════════════════════════════════════════════════════
async def show_lesson(target: Message, topic: str, state: FSMContext):
    lesson = LESSONS[topic]
    # 1. Текст урока
    await target.answer(lesson["text"], parse_mode="Markdown")
    # 2. Голосовое объяснение на русском
    await say(
        lesson["tts_ru"], target,
        caption=f"🎙 *{lesson['coach']} объясняет правило*",
        lang="ru", slow=False,
    )
    # 3. Кнопка начать
    await target.answer(
        "👇 *Готов? Начинаем вопросы!*",
        reply_markup=kb_start_quiz(),
        parse_mode="Markdown",
    )
    await state.set_state(S.lesson)

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
#  КАРТА
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

@dp.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()

# ══════════════════════════════════════════════════════
#  ВЫБОР ТЕМЫ → сначала урок
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
    await cb.message.edit_reply_markup()
    await show_lesson(cb.message, topic, state)
    await cb.answer()

# ══════════════════════════════════════════════════════
#  КНОПКА "НАЧАТЬ ВОПРОСЫ" после урока
# ══════════════════════════════════════════════════════
@dp.callback_query(S.lesson, F.data == "start_quiz")
async def start_quiz(cb: CallbackQuery, state: FSMContext):
    p = P(cb.from_user.id)
    await cb.message.edit_reply_markup()
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
        await cb.message.answer(
            f"✅ *ПРАВИЛЬНО!* — *{val}*\n"
            f"_{q['tr']}_\n\n"
            f"🎤 *Повтори вслух голосовым:*\n"
            f"🟢 *{q['say']}*\n\n"
            f"_Держи кнопку 🎤 и говори по-английски_",
            parse_mode="Markdown",
        )
        await say(q["say"], cb.message, caption=f"🔊 *Слушай и повторяй:* `{q['say']}`")
        await state.set_state(S.speaking)
    else:
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
        await msg.answer(
            f"🔁 *Почти! Попробуй ещё раз.*\n"
            f"Я услышал: _{transcript}_\n"
            f"Надо сказать: *{q['say']}*",
            parse_mode="Markdown",
        )
        await say(q["say"], msg, caption=f"🔊 *Слушай внимательно:* `{q['say']}`")

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
    await msg.answer("/start — начать\n/map — карта тем\n/stats — моя карточка")

# ══════════════════════════════════════════════════════
#  ЗАПУСК
# ══════════════════════════════════════════════════════
async def main():
    print("✅ Football English Quest bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
