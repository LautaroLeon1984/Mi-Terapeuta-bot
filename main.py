import logging
import os
import openai
import json
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# --- Configuración de API Keys ---
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# --- Flask para mantener Railway activo ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot activo desde Railway ✅", 200

def keep_alive():
    Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

# --- Base de datos ---
DB_FILE = "usuarios.json"
def cargar_db():
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def guardar_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f)

usuarios = cargar_db()

# --- Contadores de mensajes y suscripción ---
def registrar_usuario(user_id):
    if str(user_id) not in usuarios:
        usuarios[str(user_id)] = {
            "inicio_plan": None,
            "fin_plan": None,
            "uso_gratuito": 0,
            "ultimo_mensaje": None
        }
        guardar_db(usuarios)

# --- Mostrar planes de suscripción ---
async def mostrar_planes(update, context):
    botones = [
        [InlineKeyboardButton("🗓️ Plan Semanal – $4.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=21746b5ae9c94be08c0b9abcb9484f0b")],
        [InlineKeyboardButton("📆 Plan Quincenal – $7.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=32e17d17ce334234ac3d5577bfc3fea0")],
        [InlineKeyboardButton("🗓️ Plan Mensual – $12.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=1a92e8b1e31d44b99188505cf835483d")],
        [InlineKeyboardButton("📅 Plan Trimestral – $30.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=9a17a9ac63844309ab87119b56f6f71e")],
        [InlineKeyboardButton("📅 Plan Semestral – $55.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=cff15077ebe84fb88ccd0e20afa29437")],
        [InlineKeyboardButton("📅 Plan Anual – $99.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=3f7b1e3b69d544f78c7d9862e1391228")],
    ]

    await update.message.reply_text(
        "🚫 Tu acceso gratuito ha finalizado.\nSeleccioná uno de los planes para seguir usando el bot:",
        reply_markup=InlineKeyboardMarkup(botones)
    )

# --- Enviar respuestas largas dividiendo correctamente ---
async def enviar_texto_largo(update, texto):
    partes = []
    while len(texto) > 4095:
        corte = texto.rfind("\n\n", 0, 4095)
        if corte == -1:
            corte = texto.rfind(". ", 0, 4095)
        if corte == -1:
            corte = texto.rfind(" ", 0, 4095)
        if corte == -1:
            corte = 4095
        partes.append(texto[:corte].strip())
        texto = texto[corte:].strip()
    partes.append(texto)

    for parte in partes:
        await update.message.reply_text(parte)

# --- Comando /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    registrar_usuario(user_id)
    await update.message.reply_text(
        "Hola 👋 Soy tu terapeuta IA. Estoy disponible 24/7 para ayudarte a reflexionar o sentirte mejor.\n\nPodés escribirme lo que necesites o usar /ayuda para conocer más."
    )

# --- Comando /ayuda ---
async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await enviar_texto_largo(update, """💬 Este bot es un espacio de acompañamiento emocional con IA.\n\n✅ Puedes hablar libremente.\n⏳ Luego de 10 minutos sin actividad, se te ofrecerá un resumen.\n📅 Tendrás 5 mensajes gratuitos con IA, luego deberás elegir un plan.\n⚡ Todo lo que digas es confidencial y sin juicio alguno.\n\nUsa /estado para ver tu situación actual. Usa /planes para suscribirte.""")

# --- Comando /estado ---
async def estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    registrar_usuario(user_id)
    datos = usuarios[user_id]
    if datos['fin_plan']:
        fin = datetime.fromisoformat(datos['fin_plan'])
        dias_restantes = (fin - datetime.now()).days
        mensaje = f"📅 Tu suscripción está activa hasta el {fin.date()} ({dias_restantes} días restantes)."
    else:
        mensaje = f"❌ No tenés un plan activo. Consultas gratuitas usadas: {datos['uso_gratuito']}/5"
    await update.message.reply_text(mensaje)

# --- Lógica de Respuesta ---
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    registrar_usuario(user_id)
    ahora = datetime.now()
    texto = update.message.text

    datos = usuarios[user_id]
    datos['ultimo_mensaje'] = ahora.isoformat()

    if datos['fin_plan']:
        if datetime.fromisoformat(datos['fin_plan']) < ahora:
            datos['fin_plan'] = None
            datos['uso_gratuito'] = 5
    
    if not datos['fin_plan'] and datos['uso_gratuito'] >= 5:
        guardar_db(usuarios)
        return await mostrar_planes(update, context)

    if not datos['fin_plan']:
        datos['uso_gratuito'] += 1

    guardar_db(usuarios)

    try:
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un terapeuta emocional empático, claro y conciso."},
                {"role": "user", "content": texto},
            ]
        )
        respuesta = completion.choices[0].message.content
        await enviar_texto_largo(update, respuesta)
    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text("⚠️ Ocurrió un error al procesar tu mensaje.")

# --- Inicialización ---
if __name__ == "__main__":
    keep_alive()

    app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    async def setup():
        await app_bot.bot.delete_webhook(drop_pending_updates=True)

    app_bot.post_init = setup

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("ayuda", ayuda))
    app_bot.add_handler(CommandHandler("estado", estado))
    app_bot.add_handler(CommandHandler("planes", mostrar_planes))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

    print("🤖 Bot iniciado y esperando mensajes...")
    app_bot.run_polling()
