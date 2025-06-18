import logging
import os
import openai
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# --- Configuración ---
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# --- Servidor Flask para mantener Railway activo ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot activo desde Railway ✅", 200

def keep_alive():
    Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

# --- Comandos ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hola 👋 Soy tu terapeuta IA. Estoy funcionando desde Railway ✅")

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": user_input}],
        )
        reply = response.choices[0].message.content
        await update.message.reply_text(reply)
    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text("⚠️ Ocurrió un error al procesar tu mensaje.")

# --- Inicialización del bot ---
if __name__ == "__main__":
    keep_alive()

    app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Eliminar webhook previo para evitar conflictos con getUpdates
    async def setup():
        await app_bot.bot.delete_webhook(drop_pending_updates=True)

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

    app_bot.post_init = setup

    print("🤖 Bot iniciado en Railway y esperando mensajes...")
    app_bot.run_polling()
