import os
import json
import logging
import openai
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

# --- Configuración de logs ---
logging.basicConfig(
    filename='bot.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- Claves ---
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DB_PATH = "usuarios.json"

# --- Base de datos local ---
if not os.path.exists(DB_PATH):
    with open(DB_PATH, 'w') as f:
        json.dump({}, f)

def cargar_db():
    with open(DB_PATH, 'r') as f:
        return json.load(f)

def guardar_db(data):
    with open(DB_PATH, 'w') as f:
        json.dump(data, f, indent=2)

# --- Sistema de planes y suscripciones ---
PLANES = {
    "semanal": 7,
    "quincenal": 15,
    "mensual": 30,
    "trimestral": 90,
    "semestral": 180,
    "anual": 365
}

ENLACES_PLANES = [
    [InlineKeyboardButton("🗓️ Plan Semanal – $4.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=21746b5ae9c94be08c0b9abcb9484f0b")],
    [InlineKeyboardButton("📆 Plan Quincenal – $7.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=32e17d17ce334234ac3d5577bfc3fea0")],
    [InlineKeyboardButton("🗓️ Plan Mensual – $12.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=1a92e8b1e31d44b99188505cf835483d")],
    [InlineKeyboardButton("📅 Plan Trimestral – $30.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=9a17a9ac63844309ab87119b56f6f71e")],
    [InlineKeyboardButton("📅 Plan Semestral – $55.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=cff15077ebe84fb88ccd0e20afa29437")],
    [InlineKeyboardButton("📅 Plan Anual – $99.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=3f7b1e3b69d544f78c7d9862e1391228")]
]

# --- Flask para mantener Railway activo ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot activo desde Railway ✅", 200

def keep_alive():
    Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

# --- Funciones del bot ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario_id = str(update.effective_user.id)
    usuarios = cargar_db()

    if usuario_id not in usuarios:
        usuarios[usuario_id] = {
            "inicio": str(datetime.now()),
            "plan": None,
            "usos": 0,
            "ultimo_mensaje": None
        }
        guardar_db(usuarios)

    mensaje = (
        "Hola 👋 Soy tu terapeuta IA. Estoy disponible las 24 horas para acompañarte.\n"
        "🧠 Respuestas empáticas, claras y concisas.\n"
        "Tienes 5 mensajes gratuitos antes de elegir un plan.\n"
        "Usá /ayuda para más información."
    )
    await update.message.reply_text(mensaje)
    logging.info(f"/start recibido de {usuario_id}")

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Este bot brinda orientación emocional usando inteligencia artificial.\n"
        "No reemplaza un tratamiento profesional. Podés escribir cuando lo necesites."
    )

async def estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ El bot está funcionando correctamente.")

async def mostrar_planes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚫 Tu acceso gratuito ha finalizado.\nSeleccioná uno de los planes para seguir usando el bot:",
        reply_markup=InlineKeyboardMarkup(ENLACES_PLANES)
    )

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario_id = str(update.effective_user.id)
    texto = update.message.text.strip()
    usuarios = cargar_db()

    if usuario_id not in usuarios:
        await update.message.reply_text("Usá /start para comenzar ✨")
        return

    usuario = usuarios[usuario_id]
    ahora = datetime.now()

    # Inactividad
    if usuario.get("ultimo_mensaje"):
        ultima = datetime.fromisoformat(usuario["ultimo_mensaje"])
        if ahora - ultima > timedelta(minutes=10):
            await update.message.reply_text("¿Querés seguir esta conversación o que te envíe un resumen para retomarla más adelante?")
            usuario["ultimo_mensaje"] = str(ahora)
            guardar_db(usuarios)
            return

    # Plan activo o gratis
    plan_activo = usuario.get("plan")
    usos = usuario.get("usos", 0)

    if not plan_activo and usos >= 5:
        await mostrar_planes(update, context)
        return

    try:
        respuesta = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Sos un terapeuta empático, claro y conciso."},
                {"role": "user", "content": texto}
            ]
        )
        reply = respuesta.choices[0].message.content
        await update.message.reply_text(reply)
        usuario["usos"] = usos + 1
        usuario["ultimo_mensaje"] = str(ahora)
        guardar_db(usuarios)
        print(f"Mensaje respondido a {usuario_id}: {texto}")
    except Exception as e:
        logging.error(f"Error al responder: {e}")
        await update.message.reply_text("⚠️ Ocurrió un error al procesar tu mensaje.")

# --- Main ---
if __name__ == "__main__":
    keep_alive()
    app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    async def setup():
        await app_bot.bot.delete_webhook(drop_pending_updates=True)

    app_bot.post_init = setup
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("ayuda", ayuda))
    app_bot.add_handler(CommandHandler("estado", estado))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

    print("🤖 Bot iniciado y esperando mensajes...")
    app_bot.run_polling()
