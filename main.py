import asyncio
import html
import logging
import os
import re
import time
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from google import genai 

# --- [ КОНФИГУРАЦИЯ ] ---
TG_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
PORT = int(os.getenv("PORT", 10000))

current_model = "gemini-2.5-flash"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация клиента
client = genai.Client(api_key=GEMINI_KEY)

# --- [ ПРОФЕССИОНАЛЬНЫЙ ПРОМТ ] ---
SYSTEM_INSTRUCTION = (
    "Ты — элитный ассистент и справочник, созданный разработчиком Mildred. "
    "Твои правила:\n"
    "1. Стиль: Профессиональный, четкий, но дружелюбный.\n"
    "2. Оформление: Используй эмодзи для акцентов. Для удобства в списках используй ★.\n"
    "3. Форматирование: Код всегда оборачивай в блоки ```. Жирный текст используй для заголовков.\n"
    "4. Лимит: Твой ответ должен быть информативным, но строго до 3500 символов.\n"
    "5. Контекст: Ты эксперт в любой области, давай только проверенные данные (и без воды)."
)

bot = Bot(token=TG_TOKEN)
dp = Dispatcher()

# --- [ КОНВЕРТЕР MARKDOWN -> TELEGRAM HTML ] ---
def markdown_to_telegram_html(text: str) -> str:
    """Конвертирует Markdown-разметку от Gemini в валидный Telegram HTML"""
    if not text:
        return ""

    # 1. Обработка блоков кода (```код```), чтобы они не ломались внутри
    def replace_code_block(match):
        code_content = html.escape(match.group(1))
        return f"<pre><code>{code_content}</code></pre>"
    text = re.sub(r'```(?:[\w]*\n)?(.*?)```', replace_code_block, text, flags=re.DOTALL)

    # 2. Обработка инлайн-кода (`код`)
    def replace_inline_code(match):
        return f"<code>{html.escape(match.group(1))}</code>"
    text = re.sub(r'`([^`]+)`', replace_inline_code, text)

    # 3. Жирный текст (**текст** или __текст__) -> <b>текст</b>
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.*?)__', r'<b>\1</b>', text)

    # 4. Курсив (*текст* или _текст_) -> <i>текст</i>
    text = re.sub(r'(?<!\w)\*(.*?)\*(?!\w)', r'<i>\1</i>', text)
    text = re.sub(r'(?<!\w)_(.*?)_(?!\w)', r'<i>\1</i>', text)

    # 5. Заголовки (### Текст) -> преобразуем в жирный текст с новой строки
    text = re.sub(r'^#{1,6}\s+(.*?)$', r'<b>\1</b>', text, flags=re.MULTILINE)

    return text

# --- [ КОМАНДЫ ] ---

@dp.message(Command("start"))
async def start(message: types.Message):
    welcome_text = (
        f"🤖 <b>UnivoxAI</b>\n"
        f"————————————————————\n"
        f"★ <b>Статус:</b> <i>Online</i>\n"
        f"★ <b>Движок:</b> <code>{current_model}</code>\n"
        f"★ <b>Dev:</b> Mildred\n"
        f"————————————————————\n"
        f"Я настроен на профессиональную помощь. Чем могу быть полезен?"
    )
    await message.answer(welcome_text, parse_mode=ParseMode.HTML)

@dp.message(Command("change"))
async def change_model(message: types.Message):
    global current_model
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(f"⚠️ Укажите модель. Текущая: <code>{current_model}</code>", parse_mode=ParseMode.HTML)
        return
    current_model = args[1].strip()
    await message.answer(f"🔄 Модель переключена на: <code>{current_model}</code>", parse_mode=ParseMode.HTML)

@dp.message(Command("info"))
async def get_info(message: types.Message):
    info_text = (
        f"📊 <b>Техническая сводка:</b>\n"
        f"★ <b>Версия:</b> 6.4 Stable\n"
        f"★ <b>Библиотека:</b> Aiogram 3.17.0\n"
        f"★ <b>Платформа:</b> Render Cloud\n"
        f"★ <b>Форматирование:</b> Auto-HTML Parser"
    )
    await message.answer(info_text, parse_mode=ParseMode.HTML)

@dp.message()
async def chat_handler(message: types.Message):
    if not message.text: 
        return
    
    await bot.send_chat_action(message.chat.id, "typing")
    start_time = time.time()
    
    try:
        response = client.models.generate_content(
            model=current_model, 
            contents=message.text,
            config={'system_instruction': SYSTEM_INSTRUCTION}
        )
        
        raw_answer = response.text if response.text else "⚠️ Извините, не удалось сформировать ответ."
        duration = round(time.time() - start_time, 2)
        
        # Превращаем Markdown от ИИ в чистый HTML для Telegram
        formatted_answer = markdown_to_telegram_html(raw_answer)
        
        # Собираем итоговое сообщение
        final_answer = f"{formatted_answer}\n\n⏱ <i>Ответ сформирован за {duration}с</i>"

        try:
            await message.answer(final_answer, parse_mode=ParseMode.HTML)
        except Exception as html_err:
            logger.warning(f"HTML render error, falling back to plain text: {html_err}")
            # Если разметка всё же вызовет ошибку, отправляем как чистый текст без тегов
            await message.answer(raw_answer)
            
    except Exception as e:
        error_msg = html.escape(str(e))
        logger.error(f"AI Error: {str(e)}")
        await message.answer(f"❌ <b>Ошибка системы:</b>\n<code>{error_msg[:100]}</code>", parse_mode=ParseMode.HTML)

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
    logger.info(f"UnivoxAI стартовал на {current_model}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("UnivoxAI остановлен.")
