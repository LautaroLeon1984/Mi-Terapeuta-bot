import os
import json
import logging
import asyncio
import datetime
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from openai import OpenAI, OpenAIError

# --- Configuración de logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# --- Cargar claves de entorno ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- Cliente OpenAI ---
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# --- Base de datos local (usuarios) ---
USER_DB = "usuarios.json"

if not os.path.exists(USER_DB):
    with open(USER_DB, 'w') as f:
        json.dump({}, f)

def cargar_usuarios():
    with open(USER_DB, 'r') as f:
        return json.load(f)

def guardar_usuarios(data):
    with open(USER_DB, 'w') as f:
        json.dump(data, f, indent=2)

# --- Servidor Flask para mantener Railway activo ---
app = Flask(__name__)
@app.route("/")
def home():
    return "Bot activo desde Railway ✅", 200

def keep_alive():
    Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

# --- Mostrar planes ---
async def mostrar_planes(update, context):
    botones = [
        [InlineKeyboardButton("🗓️ Plan Semanal – $4.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=21746b5ae9c94be08c0b9abcb9484f0b")],
        [InlineKeyboardButton("📆 Plan Quincenal – $7.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=32e17d17ce334234ac3d5577bfc3fea0")],
        [InlineKeyboardButton("🗓️ Plan Mensual – $12.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=1a92e8b1e31d44b99188505cf835483d")],
        [InlineKeyboardButton("📅 Plan Trimestral – $30.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=9a17a9ac63844309ab87119b56f6f71e")],
        [InlineKeyboardButton("📅 Plan Semestral – $55.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=cff15077ebe84fb88ccd0e20afa29437")],
        [InlineKeyboardButton("📅 Plan Anual – $99.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=3f7b1e3b69d544f78c7d9862e1391228")],
    ]
    await update.message.reply_text("🚫 Tu acceso gratuito ha finalizado.\nSeleccioná uno de los planes para seguir usando el bot:",
                                    reply_markup=InlineKeyboardMarkup(botones))

# --- Manejo de usuarios y planes ---
def usuario_activo(user_id):
    usuarios = cargar_usuarios()
    if str(user_id) not in usuarios:
        return False
    datos = usuarios[str(user_id)]
    if 'inicio' not in datos or 'fin' not in datos:
        return False
    hoy = datetime.datetime.now().date()
    return datetime.datetime.strptime(datos['fin'], '%Y-%m-%d').date() >= hoy

def registrar_usuario(user_id):
    usuarios = cargar_usuarios()
    if str(user_id) not in usuarios:
        hoy = datetime.datetime.now().date()
        usuarios[str(user_id)] = {
            "inicio": str(hoy),
            "fin": str(hoy + datetime.timedelta(days=7)),
            "interacciones": 0
        }
        guardar_usuarios(usuarios)

# --- Inicio /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    registrar_usuario(update.effective_user.id)
    texto = (
        "Hola, soy tu terapeuta IA 🌟\n\n"
        "Estoy disponible 24/7 para escucharte, orientarte y acompañarte emocionalmente.\n"
        "Tenés 5 consultas gratuitas para probar el servicio. Luego podés elegir un plan.\n\n"
        "Usá /ayuda para ver más comandos disponibles."
    )
    await update.message.reply_text(texto)

# --- Ayuda ---
async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Comandos disponibles:\n/start - Iniciar\n/ayuda - Ver comandos\n/estado - Ver estado del bot\n/ejercicios - Obtener ejercicio de relajación")

# --- Estado ---
async def estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot funcionando correctamente desde Railway 🚀")

# --- Ejercicios (dividir correctamente) ---
def dividir_mensaje(texto, max_len=4095):
    partes = []
    actual = ""
    for linea in texto.split("\n"):
        if len(actual) + len(linea) + 1 <= max_len:
            actual += linea + "\n"
        else:
            partes.append(actual.strip())
            actual = linea + "\n"
    if actual:
        partes.append(actual.strip())
    return partes

async def ejercicios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "🧘‍♀️ Ejercicio sugerido:\n"
        "Claro, aquí tienes un ejercicio breve y relajante que puede ayudar a reconectar con tus emociones:\n\n"
        "Ejercicio de Escaneo Corporal y Respiración Consciente\n\n"
        "1. Encuentra un Lugar Tranquilo: Siéntate o acéstate en un lugar cómodo donde no te molesten.\n\n"
        "2. Cierra los Ojos: Cierra los ojos suavemente y dirigí tu atención hacia adentro.\n\n"
        "3. Respira Profundamente: Inhalá por la nariz contando hasta 4, sostené un momento y exhalá por la boca contando hasta 6. Repetí 3 veces.\n\n"
        "4. Escaneo Corporal: Empezá por los pies y subí la atención lentamente hasta la cabeza, notando cada parte sin juzgar."
    )
    partes = dividir_mensaje(texto)
    for parte in partes:
        await update.message.reply_text(parte)

# --- Procesar mensajes generales ---
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mensaje = update.message.text

    registrar_usuario(user_id)
    usuarios = cargar_usuarios()

    if not usuario_activo(user_id):
        await mostrar_planes(update, context)
        return

    if mensaje.lower() in ["hola", "hi", "buenas"]:
        return

    if usuarios[str(user_id)]["interacciones"] >= 5:
        await mostrar_planes(update, context)
        return

    try:
        respuesta = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Sé un terapeuta empático, claro y conciso."},
                {"role": "user", "content": mensaje}
            ]
        )
        texto = respuesta.choices[0].message.content.strip()
        usuarios[str(user_id)]["interacciones"] += 1
        guardar_usuarios(usuarios)
        for parte in dividir_mensaje(texto):
            await update.message.reply_text(parte)
    except OpenAIError as e:
        await update.message.reply_text("Ocurrió un error procesando tu mensaje. Intentalo más tarde.")
        logging.error(f"Error OpenAI: {e}")

# --- Ejecutar bot ---
if __name__ == '__main__':
    keep_alive()

    app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("ayuda", ayuda))
    app_bot.add_handler(CommandHandler("estado", estado))
    app_bot.add_handler(CommandHandler("ejercicios", ejercicios))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

    async def setup():
        await app_bot.bot.delete_webhook(drop_pending_updates=True)

    app_bot.post_init = setup

    print("🤖 Bot iniciado y esperando mensajes...")
    app_bot.run_polling()
