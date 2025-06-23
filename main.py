from pathlib import Path

# Script actualizado con:
# - División de mensajes para /ejercicios
# - Eliminación de **negrita**
# - Inclusión de todos los planes de suscripción

script_code = """
import logging
import os
import json
import openai
import time
import datetime
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

# --- Configuración de claves ---
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- Logging ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# --- Inicialización de Flask para mantener Railway activo ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot activo desde Railway ✅", 200

def keep_alive():
    Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

# --- Base de datos JSON ---
USUARIOS_DB = "usuarios.json"

def cargar_usuarios():
    if os.path.exists(USUARIOS_DB):
        with open(USUARIOS_DB, "r") as f:
            return json.load(f)
    return {}

def guardar_usuarios(data):
    with open(USUARIOS_DB, "w") as f:
        json.dump(data, f, indent=2)

usuarios = cargar_usuarios()
interacciones_temporales = {}

# --- Verificación de plan activo ---
def plan_activo(user_id):
    usuario = usuarios.get(str(user_id))
    if not usuario:
        return False
    if "expira" in usuario:
        return datetime.datetime.now().timestamp() < usuario["expira"]
    return False

# --- Planes de suscripción ---
async def mostrar_planes(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

# --- Comando /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if str(user_id) not in usuarios:
        usuarios[str(user_id)] = {"inicio": time.time(), "interacciones": 0}
        guardar_usuarios(usuarios)

    mensaje = (
        "Hola 👋 Bienvenido/a a *Mi Terapeuta IA*.\n\n"
        "Estoy acá para escucharte, acompañarte y ayudarte a reflexionar.\n"
        "Disponés de 5 interacciones gratuitas. Luego, podés elegir un plan para seguir conversando.\n\n"
        "📌 Para ayuda, escribí /ayuda\n"
        "🧘 Para ejercicios guiados, escribí /ejercicios\n"
    )
    await update.message.reply_text(mensaje, parse_mode="Markdown")

# --- Comando /ayuda ---
async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📍 Comandos disponibles:\n/start – Iniciar\n/ayuda – Ver ayuda\n/ejercicios – Ver ejercicios guiados")

# --- Comando /ejercicios ---
async def ejercicios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "🧘 Ejercicio sugerido:\n"
        "Claro, aquí tienes un ejercicio breve y relajante que puede ayudarte a reconectar contigo mismo cuando te sientes neutro:\n\n"
        "Ejercicio de Respiración y Conexión con el Momento Presente\n\n"
        "1. Encuentra un Lugar Tranquilo: Siéntate en una posición cómoda, ya sea en una silla con los pies apoyados en el suelo o en el suelo con las piernas cruzadas. Asegúrate de que tu espalda esté recta pero relajada.\n\n"
        "2. Cierra los Ojos: Cierra suavemente los ojos y lleva tu atención hacia adentro.\n\n"
        "3. Respira Profundamente: Inhala lentamente por la nariz contando hasta cuatro, sostené la respiración por un momento, y luego exhala suavemente por la boca contando hasta cuatro. Repite este ciclo de respiración tres veces.\n\n"
        "4. Conciencia Corporal: Tras las respiraciones profundas, lleva tu atención a diferentes partes de tu cuerpo, comenzando por los pies y subiendo lentamente hasta la cabeza, notando cualquier sensación sin juzgar.\n\n"
        "5. Regreso Suave: Cuando estés listo, abre lentamente los ojos y tómate un momento antes de volver a tus actividades."
    )

    partes = dividir_texto(texto)
    for parte in partes:
        await update.message.reply_text(parte)

# --- División de texto sin cortar frases ---
def dividir_texto(texto, max_chars=4095):
    lineas = texto.splitlines(keepends=True)
    bloques = []
    actual = ""
    for linea in lineas:
        if len(actual) + len(linea) > max_chars:
            bloques.append(actual)
            actual = ""
        actual += linea
    if actual:
        bloques.append(actual)
    return bloques

# --- Respuesta IA con control de interacciones ---
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in usuarios:
        usuarios[user_id] = {"inicio": time.time(), "interacciones": 0}
    if not plan_activo(user_id):
        if usuarios[user_id]["interacciones"] >= 5:
            await mostrar_planes(update, context)
            return
        usuarios[user_id]["interacciones"] += 1
        guardar_usuarios(usuarios)

    try:
        mensaje = update.message.text
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Responde de forma empática, clara y concisa."},
                {"role": "user", "content": mensaje}
            ]
        )
        reply = response.choices[0].message.content
        partes = dividir_texto(reply)
        for parte in partes:
            await update.message.reply_text(parte)
    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text("⚠️ Ocurrió un error al procesar tu mensaje.")

# --- Inicialización del bot ---
if __name__ == "__main__":
    keep_alive()
    app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    async def setup():
        await app_bot.bot.delete_webhook(drop_pending_updates=True)

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("ayuda", ayuda))
    app_bot.add_handler(CommandHandler("ejercicios", ejercicios))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

    app_bot.post_init = setup
    print("🤖 Bot iniciado y esperando mensajes...")
    app_bot.run_polling()
"""

# Guardar el script
script_path = "/mnt/data/bot_main_final_telegram.py"
Path(script_path).write_text(script_code)
script_path
