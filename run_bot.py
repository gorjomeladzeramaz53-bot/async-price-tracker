import os
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler
from app.telegram import start_command, list_command, add_command, delete_command, check_command

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        print("შეცდომა: TELEGRAM_TOKEN ვერ მოიძებნა .env ფაილში!")
        exit(1)
        
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CommandHandler("delete", delete_command))
    app.add_handler(CommandHandler("check", check_command))
    
    print("🤖 Telegram ბოტი წარმატებით გააქტიურდა და უსმენს ბრძანებებს...")
    app.run_polling()