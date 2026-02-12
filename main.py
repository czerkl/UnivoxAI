import os
import asyncio
import logging
import time
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.utils.markdown import hbold, hcode, hitalic
from google import genai 
from aiohttp import web

# --- [ КОНФИГУРАЦИЯ ] ---
TG_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
PORT = int(os.getenv("PORT", 10000))

current_model = "gemini-3-flash-preview"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация клиента
client = genai.Client(api_key=GEMINI_KEY)

# --- [ ПРОФЕССИОНАЛЬНЫЙ ПРОМТ ] ---
SYSTEM_INSTRUCTION = (
    "Ты — UnivoxAI v6.2, элитный ассистент и справочник, созданный разработчиком dev. Czerkl. "
    "Твои правила:\n"
    "1. Стиль: Профессиональный, четкий, но дружелюбный.\n"
    "2. Оформление: Используй эмодзи для акцентов. Списки оформляй через символ ★.\n"
    "3. Форматирование: Код всегда оборачивай в блоки ```. Жирный текст используй для заголовков.\n"
    "4. Лимит: Твой ответ должен быть информативным, но строго до 3500 символов.\n"
    "5. Контекст: Ты эксперт в любой области, давай только проверенные данные."
)

bot = Bot(token=TG_TOKEN)
dp = Dispatcher()

# --- [ КОМАНДЫ ] ---

@dp.message(Command("start"))
async def start(message: types.Message):
    # Исправлено: Чистый HTML без лишних символов
    welcome_text = (
        f"🤖 {hbold('UnivoxAI v6.2')}\n"
        f"————————————————————\n"
        f"★ {hbold('Статус:')} {hitalic('Online')}\n"
        f"★ {hbold('Движок:')} {hcode(current_model)}\n"
        f"★ {hbold('Dev:')} dev. Czerkl\n"
        f"————————————————————\n"
        f"Я настроен на профессиональную помощь. Чем могу быть полезен?"
    )
    await message.answer(welcome_text, parse_mode=ParseMode.HTML)

@dp.message(Command("change"))
async def change_model(message: types.Message):
    global current_model
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(f"⚠️ Укажите модель. Текущая: {hcode(current_model)}", parse_mode=ParseMode.HTML)
        return
    current_model = args[1].strip()
    await message.answer(f"🔄 Модель переключена на: {hcode(current_model)}", parse_mode=ParseMode.HTML)

# --- [ НОВАЯ ФИЧА: /info ] ---
@dp.message(Command("info"))
async def get_info(message: types.Message):
    info_text = (
        f"📊 {hbold('Техническая сводка:')}\n"
        f"★ {hbold('Версия:')} 6.2 Stable\n"
        f"★ {hbold('Библиотека:')} Aiogram 3.17.0\n"
        f"★ {hbold('Платформа:')} Render Cloud\n"
        f"★ {hbold('Форматирование:')} Smart Markdown/HTML"
    )
    await message.answer(info_text, parse_mode=ParseMode.HTML)

@dp.message()
async def chat_handler(message: types.Message):
    if not message.text: return
    
    await bot.send_chat_action(message.chat.id, "typing")
    start_time = time.time() # Фича: замер скорости
    
    try:
        response = client.models.generate_content(
            model=current_model, 
            contents=message.text,
            config={'system_instruction': SYSTEM_INSTRUCTION}
        )
        
        answer = response.text if response.text else "⚠️ Извините, не удалось сформировать ответ."
        duration = round(time.time() - start_time, 2)
        
        # Добавляем подпись в конце для профессионального вида
        final_answer = f"{answer}\n\n⏱ {hitalic(f'Ответ сформирован за {duration}с')}"

        try:
            # Пробуем отправить с MarkdownV2 (он мощнее, но капризнее)
            await message.answer(final_answer, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            # Fallback: если ИИ накосячил с символами, отправляем как обычный текст
            logger.warning("Markdown error, sending as plain text")
            await message.answer(final_answer)
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"AI Error: {error_msg}")
        await message.answer(f"❌ {hbold('Ошибка системы:')}\n{hcode(error_msg[:100])}", parse_mode=ParseMode.HTML)

# --- [ СЕРВЕР ДЛЯ ПИНГЕРА ] ---
async def handle_ping(request):
    return web.Response(text="UNIVOX_ALIVE", status=200)

async def main():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info(f"UnivoxAI v6.2 стартовал на {current_model}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("UnivoxAI остановлен.")
        