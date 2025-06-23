import logging
import os
import openai
import asyncio
import sqlite3
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, CallbackQueryHandler
)

# --- Configuración inicial ---
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DB_FILE = "usuarios.db"

# --- Configuración de logs ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Inicializar BD ---
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            user_id INTEGER PRIMARY KEY,
            nombre TEXT,
            interacciones INTEGER,
            plan TEXT,
            inicio_plan TEXT,
            fin_plan TEXT,
            ultima_interaccion TEXT
        )""")

# --- Servidor Flask ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot activo desde Railway ✅", 200

def keep_alive():
    Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

# --- Utilidades de usuario ---
def obtener_usuario(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute("SELECT * FROM usuarios WHERE user_id = ?", (user_id,))
        return cursor.fetchone()

def crear_o_actualizar_usuario(user):
    with sqlite3.connect(DB_FILE) as conn:
        existente = obtener_usuario(user.id)
        if not existente:
            conn.execute("""
                INSERT INTO usuarios (user_id, nombre, interacciones, plan, inicio_plan, fin_plan, ultima_interaccion)
                VALUES (?, ?, 0, 'free', NULL, NULL, ?)
            """, (user.id, user.first_name, datetime.utcnow().isoformat()))

# --- Comandos y lógica ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    crear_o_actualizar_usuario(update.effective_user)
    mensaje = (
        f"Hola {update.effective_user.first_name} 👋\n\n"
        "Soy tu terapeuta IA. Funciono 24/7 para ayudarte emocionalmente de forma accesible y confidencial.\n\n"
        "👉 Tienes 5 consultas gratuitas. Luego podrás elegir un plan.\n"
        "👉 Escribime cuando quieras para empezar.\n\n"
        "💬 /ayuda para conocer más sobre cómo funciona."
    )
    await update.message.reply_text(mensaje)

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Este bot funciona como terapeuta IA para ayudarte emocionalmente.\n"
        "Puedes escribir lo que sientas y recibirás una respuesta empática, clara y guiada.\n\n"
        "- 5 primeras consultas gratuitas.\n"
        "- Luego puedes suscribirte con MercadoPago.\n"
        "- /estado para ver tu plan y vencimiento.\n"
        "- /resumen para guardar tu conversación (cuando se active)."
    )

async def estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = obtener_usuario(user_id)
    if u:
        plan, inicio, fin = u[3], u[4], u[5]
        if plan == "free":
            msg = "🆓 Estás en el plan gratuito. Te quedan 5 consultas."
        else:
            msg = f"✅ Plan activo: {plan}\nDesde: {inicio}\nHasta: {fin}"
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("Usuario no registrado. Escribí /start para comenzar.")

async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    crear_o_actualizar_usuario(update.effective_user)
    u = obtener_usuario(user_id)

    interacciones, plan, fin_plan = u[2], u[3], u[5]
    ahora = datetime.utcnow()
    puede_continuar = False

    if plan == "free" and interacciones < 5:
        puede_continuar = True
    elif plan != "free" and fin_plan and datetime.fromisoformat(fin_plan) > ahora:
        puede_continuar = True

    if puede_continuar:
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": update.message.text}],
            )
            reply = response.choices[0].message.content
            await update.message.reply_text(reply)
            with sqlite3.connect(DB_FILE) as conn:
                conn.execute(
                    "UPDATE usuarios SET interacciones = interacciones + 1, ultima_interaccion = ? WHERE user_id = ?",
                    (ahora.isoformat(), user_id)
                )

        except Exception as e:
            logger.error(f"Error al procesar mensaje: {e}")
            await update.message.reply_text("⚠️ Ocurrió un error al procesar tu mensaje.")
    else:
        await update.message.reply_text(
            "🛑 Has alcanzado el límite de uso gratuito o tu plan ha expirado.\n"
            "Por favor, suscribite para continuar."
        )

# --- Inactividad (simulada por verificación manual) ---
async def resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔄 ¿Querés continuar la conversación o generar un resumen para retomarla luego?\n\n"
        "(Esta función está en desarrollo)"
    )

# --- Inicialización ---
if __name__ == "__main__":
    init_db()
    keep_alive()
    
    app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    async def setup():
        await app_bot.bot.delete_webhook(drop_pending_updates=True)

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("ayuda", ayuda))
    app_bot.add_handler(CommandHandler("estado", estado))
    app_bot.add_handler(CommandHandler("resumen", resumen))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_mensaje))

    app_bot.post_init = setup

    print("🤖 Bot terapeuta IA funcionando desde Railway...")
    app_bot.run_polling()
