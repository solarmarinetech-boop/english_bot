# ⚽ Football English Quest — Telegram Bot

## Файлы
- `bot.py` — основной код бота
- `requirements.txt` — зависимости
- `railway.toml` — настройки сервера

---

## 🚀 Запуск на Railway (шаг за шагом)

### 1. Залей код на GitHub

1. Зайди на https://github.com и создай аккаунт (если нет)
2. Нажми «+» → «New repository»
3. Назови: `football-english-bot`
4. Нажми «Create repository»
5. Нажми «uploading an existing file»
6. Перетащи все 3 файла: `bot.py`, `requirements.txt`, `railway.toml`
7. Нажми «Commit changes»

### 2. Задеплой на Railway

1. Зайди на https://railway.app
2. Нажми «New Project» → «Deploy from GitHub repo»
3. Выбери репозиторий `football-english-bot`
4. Railway начнёт билд — подожди 1-2 минуты

### 3. Добавь секретные ключи

В Railway открой свой проект → вкладка **Variables** → добавь:

| Name | Value |
|------|-------|
| `BOT_TOKEN` | твой токен от @BotFather |
| `GROQ_API_KEY` | твой ключ от console.groq.com |

Нажми «Deploy» — бот запустится!

### 4. Проверь

Открой своего бота в Телеграм и напиши `/start`

---

## 🎮 Команды бота

| Команда | Что делает |
|---------|-----------|
| `/start` | Начать игру заново |
| `/map` | Вернуться на карту тем |
| `/stats` | Посмотреть свою карточку |

---

## 🎤 Как работает голос

1. Ребёнок отвечает на вопрос кнопкой
2. Если правильно — бот просит сказать фразу вслух
3. Ребёнок держит кнопку 🎤 в Телеграм и говорит
4. Бот отправляет аудио в Groq Whisper AI
5. Whisper распознаёт речь и бот проверяет произношение
6. За правильный ответ + хорошее произношение — монеты!
