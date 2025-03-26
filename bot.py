import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
import requests
from io import BytesIO
import openpyxl
from datetime import datetime

# Настройка логов
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = "7781191769:AAFr2wEY9dx_-HhWVw-rYgGNIv9DFSZcw4E"
EXCEL_FILE_URL = "https://disk.yandex.ru/i/2M6hS8Hyx1BU_Q"

# Кэш данных
data_cache = {
    'last_update': None,
    'data': None
}

# Соответствие кнопок и листов Excel
sheet_map = {
    "raw_powerrise": "Сырьё Powerrise",
    "raw_nutropro": "Сырьё NUTROPRO",
    "ready_powerrise": "Готовая Powerrise", 
    "ready_nutropro": "Готовая NUTROPRO"
}

def get_excel_data():
    """Загрузка и парсинг Excel с Яндекс.Диска"""
    try:
        # Получаем ссылку для скачивания через API Яндекс.Диска
        api_url = f"https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key={EXCEL_FILE_URL}"
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        download_url = response.json().get('href')
        
        # Скачиваем файл
        file_response = requests.get(download_url, timeout=15)
        file_response.raise_for_status()
        
        return openpyxl.load_workbook(BytesIO(file_response.content), data_only=True)
    except Exception as e:
        logger.error(f"Ошибка загрузки Excel: {e}")
        raise

def create_menu():
    """Генерация клавиатуры меню"""
    keyboard = [
        [InlineKeyboardButton("✅ Сырьё POWERRISE", callback_data="raw_powerrise")],
        [InlineKeyboardButton("✅ Сырьё NUTROPRO", callback_data="raw_nutropro")],
        [InlineKeyboardButton("✅ Готовая POWERRISE", callback_data="ready_powerrise")],
        [InlineKeyboardButton("✅ Готовая NUTROPRO", callback_data="ready_nutropro")],
        [InlineKeyboardButton("🔄 Обновить данные", callback_data="refresh")]
    ]
    return InlineKeyboardMarkup(keyboard)

def start(update: Update, context: CallbackContext):
    """Обработчик команды /start"""
    update.message.reply_text(
        "📊 Выберите раздел для просмотра остатков:",
        reply_markup=create_menu()
    )

def button_handler(update: Update, context: CallbackContext):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    query.answer()

    try:
        if query.data == "refresh":
            data_cache['data'] = None
            query.edit_message_text(
                text="⏳ Обновляю данные...",
                reply_markup=create_menu()
            )
        
        # Получаем актуальные данные (кеш на 30 минут)
        if not data_cache['data'] or (datetime.now() - data_cache['last_update']).seconds > 1800:
            wb = get_excel_data()
            data_cache['data'] = wb
            data_cache['last_update'] = datetime.now()

        sheet_name = sheet_map.get(query.data)
        if not sheet_name:
            query.edit_message_text(
                text="❌ Раздел не найден",
                reply_markup=create_menu()
            )
            return

        sheet = data_cache['data'][sheet_name]
        items = []
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if row and row[0]:
                items.append(f"{row[0]} — {row[1] if len(row)>1 else 0} кг")

        if not items:
            text = f"📭 Раздел '{sheet_name}' пуст"
        else:
            text = f"📦 {sheet_name} (обновлено: {data_cache['last_update'].strftime('%H:%M %d.%m.%Y')})\n\n" + "\n".join(items)

        query.edit_message_text(
            text=text,
            reply_markup=create_menu()
        )

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        query.edit_message_text(
            text=f"⚠️ Ошибка: {str(e)}",
            reply_markup=create_menu()
        )

def main():
    """Запуск бота"""
    try:
        updater = Updater(BOT_TOKEN, use_context=True)
        dp = updater.dispatcher

        dp.add_handler(CommandHandler("start", start))
        dp.add_handler(CallbackQueryHandler(button_handler))

        # Проверка режима запуска (Render или локально)
        if 'RENDER' in os.environ:
            PORT = int(os.environ.get('PORT', 10000))
            updater.start_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path=BOT_TOKEN,
                webhook_url=f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}"
            )
            logger.info("Бот запущен в режиме Webhook")
        else:
            updater.start_polling()
            logger.info("Бот запущен в режиме Polling")

        updater.idle()
    except Exception as e:
        logger.critical(f"Фатальная ошибка: {e}")

if __name__ == '__main__':
    main()
