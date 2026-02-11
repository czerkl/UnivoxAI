import os
import asyncio
import logging
import textwrap
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.utils.markdown import hbold, hcode
from google import genai 
from aiohttp import web

# --- [ КОНФИГУРАЦИЯ ] ---
TG_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
PORT = int(os.getenv("PORT", 10000))

# Твоя "тайная" модель по умолчанию
current_model = "gemini-3-flash-preview"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация клиента Gemini
client = genai.Client(api_key=GEMINI_KEY)

# Бот с поддержкой HTML форматирования (самый надежный способ для ИИ)
bot = Bot(token=TG_TOKEN)
dp = Dispatcher()

# --- [ УТИЛИТЫ ] ---

def split_message(text, limit=4000):
    """Нарезает текст на куски, чтобы Telegram не выдавал ошибку длины"""
    if len(text) <= limit:
        return [text]
    return textwrap.wrap(text, limit, break_long_words=False, replace_whitespace=False)

# --- [ КОМАНДЫ ] ---

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        f"💎 **UnivoxAI v6.1**\n"
        f"Статус: {hbold('Online')}\n"
        f"Движок: {hcode(current_model)}\n\n",
        parse_mode=ParseMode.HTML
    )

@dp.message(Command("change"))
async def change_model(message: types.Message):
    global current_model
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Формат: `/change gemini-2.5-flash`", parse_mode=ParseMode.MARKDOWN)
        return
    current_model = args[1].strip()
    await message.answer(f"✅ Модель изменена на: {hcode(current_model)}", parse_mode=ParseMode.HTML)

@dp.message()
async def chat_handler(message: types.Message):
    if not message.text: return
    
    await bot.send_chat_action(message.chat.id, "typing")
    
    try:
        # Запрос к Gemini
        response = client.models.generate_content(
            model=current_model, 
            contents=message.text
        )
        
        full_text = response.text if response.text else "⚠️ Модель не выдала текст."

        # ЛОГИКА: Нарезаем сообщение и отправляем по частям
        parts = split_message(full_text)
        for part in parts:
            # Используем Markdown (V1), он лучше всего жует стандартный вывод ИИ
            await message.answer(part, parse_mode=ParseMode.MARKDOWN)
            await asyncio.sleep(0.1) # Микропауза для защиты от спам-фильтра
            
    except Exception as e:
        error_str = str(e)
        logger.error(f"Ошибка: {error_str}")
        await message.answer(f"❌ **Ошибка Gemini:**\n`{error_str[:150]}`", parse_mode=ParseMode.MARKDOWN)

# --- [ СЕРВЕР ДЛЯ ПИНГЕРА ] ---
async def handle_ping(request):
    return web.Response(text="BOT_ACTIVE", status=200)

async def main():
    # Настройка сервера для Render
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"Веб-сервер активен на порту {PORT}")

    # Запуск бота
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info(f"UnivoxAI v6.1 запущен на модели {current_model}")
    
    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот выключен")