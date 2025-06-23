import os
import logging
import asyncio
import openai
import json
import sqlite3
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, filters,
                          ContextTypes, CallbackQueryHandler)

# --- Configuración ---
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "00000000"))  # Reemplazar por tu ID real
DB_PATH = "usuarios.db"

# --- Logging ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- Flask para mantener Railway activo ---
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot activo"
Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': 8080}).start()

# --- DB ---
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY,
            username TEXT,
            nombre TEXT,
            fecha_inicio TEXT,
            fecha_vencimiento TEXT,
            interacciones_gratis INTEGER DEFAULT 0,
            plan_activo INTEGER DEFAULT 0
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS actividad (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            mensaje TEXT,
            respuesta TEXT,
            fecha TEXT,
            ia BOOLEAN
        )''')
init_db()

# --- Funciones de ayuda ---
def registrar_usuario(user):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM usuarios WHERE id=?", (user.id,))
        if not c.fetchone():
            inicio = datetime.now().strftime("%Y-%m-%d")
            vencimiento = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            c.execute("INSERT INTO usuarios (id, username, nombre, fecha_inicio, fecha_vencimiento) VALUES (?, ?, ?, ?, ?)",
                      (user.id, user.username, user.first_name, inicio, vencimiento))

async def enviar_grande(update, text):
    partes = text.split('\n\n')
    buffer = ""
    for parte in partes:
        if len(buffer) + len(parte) < 4095:
            buffer += parte + "\n\n"
        else:
            await update.message.reply_text(buffer.strip())
            buffer = parte + "\n\n"
    if buffer:
        await update.message.reply_text(buffer.strip())

# --- Comandos ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    registrar_usuario(update.effective_user)
    await update.message.reply_text(
        f"Hola {update.effective_user.first_name}! Bienvenido a Mi Terapeuta IA.\n"
        "Podés consultar libremente. Luego de 5 interacciones, deberás suscribirte.\n"
        "Comandos útiles: /ayuda /planes"
    )

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Este bot te acompaña emocionalmente mediante IA.\n"
        "Puedes interactuar libremente. Si necesitas ayuda, envíame un mensaje."
    )

async def planes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Planes disponibles:\n\n"
        "📅 Semanal: $2.000\n"
        "📅 Mensual: $6.000\n"
        "📅 Anual: $49.000\n\n"
        "Solicitá tu plan para seguir usando el bot sin límites."
    )

async def ejercicios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "🧘‍♀️ Ejercicio sugerido:\n"
        "Claro, aquí tienes un ejercicio breve y relajante que puedes intentar si te sientes neutral:\n\n"
        "Ejercicio de Respiración Consciente y Sensación Corporal\n\n"
        "1. Encuentra un Lugar Tranquilo: Busca un lugar donde puedas sentarte o recostarte cómodamente.\n\n"
        "2. Cierra los Ojos: Cierra los ojos suavemente y lleva tu atención a tu respiración.\n\n"
        "3. Respira Profundamente: Inhala por la nariz contando 4, sostené, y exhalá por la boca contando 6. Repetí 3 veces.\n\n"
        "4. Escaneo Corporal: Llevá tu atención desde los pies hacia la cabeza, lentamente. Observá cada parte sin juzgar.\n\n"
        "5. Cierre: Tomate unos segundos finales para agradecerte por el tiempo tomado."
    )
    await enviar_grande(update, texto)

# --- Inactividad ---
usuarios_ultima_interaccion = {}
async def detectar_inactividad():
    while True:
        ahora = datetime.now()
        for user_id, ultima in list(usuarios_ultima_interaccion.items()):
            if (ahora - ultima).total_seconds() > 600:
                app_bot = context_global.bot
                await app_bot.send_message(chat_id=user_id,
                    text="¿Querés que te prepare un resumen de lo que hablamos? Podés guardarlo o revisarlo más tarde.")
                usuarios_ultima_interaccion[user_id] = ahora  # Evita spam
        await asyncio.sleep(60)

# --- Chat principal ---
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    registrar_usuario(user)
    usuarios_ultima_interaccion[user.id] = datetime.now()
    mensaje = update.message.text

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT interacciones_gratis, plan_activo, fecha_vencimiento FROM usuarios WHERE id=?", (user.id,))
        data = c.fetchone()

        if data:
            interacciones, plan_activo, vencimiento = data
            if plan_activo == 0 and interacciones >= 5:
                await update.message.reply_text("Has superado el límite gratuito. Suscribite con /planes.")
                return

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": mensaje}]
        )
        respuesta = response.choices[0].message['content']
    except Exception as e:
        logging.error(f"Error OpenAI: {e}")
        await update.message.reply_text("Hubo un error procesando tu mensaje.")
        return

    await enviar_grande(update, respuesta)

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO actividad (user_id, mensaje, respuesta, fecha, ia) VALUES (?, ?, ?, ?, ?)",
                  (user.id, mensaje, respuesta, datetime.now().isoformat(), True))
        if plan_activo == 0:
            c.execute("UPDATE usuarios SET interacciones_gratis = interacciones_gratis + 1 WHERE id=?", (user.id,))

# --- Main ---
if __name__ == '__main__':
    app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    context_global = app_bot

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("ayuda", ayuda))
    app_bot.add_handler(CommandHandler("planes", planes))
    app_bot.add_handler(CommandHandler("ejercicios", ejercicios))
    app_bot.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), responder))

    loop = asyncio.get_event_loop()
    loop.create_task(detectar_inactividad())
    print("🤖 Bot iniciado y esperando mensajes...")
    app_bot.run_polling()
