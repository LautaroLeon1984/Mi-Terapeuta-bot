import logging
import os
import json
import time
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
import openai

# --- Configuraciones ---
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USUARIOS_JSON = "usuarios.json"

# --- Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# --- Activador de Railway ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot funcionando correctamente desde Railway ✅", 200

def keep_alive():
    Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

# --- Funciones base de usuarios ---
def cargar_usuarios():
    if os.path.exists(USUARIOS_JSON):
        with open(USUARIOS_JSON, "r") as f:
            return json.load(f)
    return {}

def guardar_usuarios(data):
    with open(USUARIOS_JSON, "w") as f:
        json.dump(data, f, indent=2)

def es_plan_activo(user):
    if user not in usuarios:
        return False
    if usuarios[user].get("plan"):
        fin = datetime.fromisoformat(usuarios[user]["fin"])
        return datetime.now() < fin
    return False

# --- Manejo de planes ---
async def mostrar_planes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    botones = [
        [InlineKeyboardButton("🗓️ Plan Semanal – $4.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=21746b5ae9c94be08c0b9abcb9484f0b")],
        [InlineKeyboardButton("📆 Plan Quincenal – $7.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=32e17d17ce334234ac3d5577bfc3fea0")],
        [InlineKeyboardButton("🗓️ Plan Mensual – $12.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=1a92e8b1e31d44b99188505cf835483d")],
        [InlineKeyboardButton("📅 Plan Trimestral – $30.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=9a17a9ac63844309ab87119b56f6f71e")],
        [InlineKeyboardButton("📅 Plan Semestral – $55.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=cff15077ebe84fb88ccd0e20afa29437")],
        [InlineKeyboardButton("📅 Plan Anual – $99.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=3f7b1e3b69d544f78c7d9862e1391228")]
    ]
    await update.message.reply_text(
        "🚫 Tu acceso gratuito ha finalizado. Seleccioná un plan para continuar:",
        reply_markup=InlineKeyboardMarkup(botones)
    )

# --- Comandos ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hola 👋 Soy tu terapeuta IA. Estoy acá para acompañarte emocionalmente.\n\nTenés 5 consultas gratuitas. Luego podrás elegir un plan para seguir.\n\nUsá /ayuda para ver más opciones."
    )

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Comandos disponibles:\n/start - Inicio\n/ayuda - Ver ayuda\n/ejercicios - Ejercicio emocional sugerido")

# --- Ejercicio con división inteligente ---
def dividir_mensaje(texto, max_chars=4095):
    partes = []
    bloque = ""
    for linea in texto.splitlines(keepends=True):
        linea_sin_asteriscos = linea.replace("**", "")
        if len(bloque) + len(linea_sin_asteriscos) <= max_chars:
            bloque += linea_sin_asteriscos
        else:
            partes.append(bloque)
            bloque = linea_sin_asteriscos
    if bloque:
        partes.append(bloque)
    return partes

async def ejercicios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = (
        "🧘 Ejercicio sugerido:\n"
        "Claro, aquí tienes un ejercicio breve y relajante que puede ayudarte a reconectar contigo mismo cuando te sientes neutro:\n\n"
        "Ejercicio de Escaneo Corporal de 5 Minutos\n\n"
        "1. Encuentra un Lugar Tranquilo: Siéntate o acuéstate en un lugar cómodo donde no te vayan a interrumpir.\n"
        "2. Cierra los Ojos y Respira Profundamente: Inhala lenta y profundamente por la nariz, mantén el aire por un momento, y luego exhala suavemente por la boca. Repite esto 3 veces.\n"
        "3. Escaneo Corporal:\n  - Comienza enfocándote en la parte superior de tu cabeza. Nota cualquier sensación que sientas, sin juzgar ni tratar de cambiar nada.\n  - Lentamente, mueve tu atención hacia abajo, pasando por tu frente, ojos, mejillas, mandíbula, cuello.\n  - Continúa hacia los hombros, brazos, pecho, abdomen, caderas, piernas, y pies.\n  - Si te distraes, suavemente vuelve tu atención a la parte del cuerpo en la que estabas.\n"
    )
    partes = dividir_mensaje(mensaje)
    for parte in partes:
        await update.message.reply_text(parte)
        time.sleep(1)

# --- Respuesta por IA ---
usuarios = cargar_usuarios()
interacciones_gratis = 5
ultima_interaccion = {}

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    texto = update.message.text.strip()

    if not es_plan_activo(user_id):
        usuario = usuarios.get(user_id, {"usos": 0})
        if usuario["usos"] >= interacciones_gratis:
            await mostrar_planes(update, context)
            return
        else:
            usuario["usos"] += 1
            usuarios[user_id] = usuario
            guardar_usuarios(usuarios)

    ultima_interaccion[user_id] = time.time()

    try:
        respuesta = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "Responde como terapeuta empático, claro y conciso."},
                     {"role": "user", "content": texto}]
        )
        reply = respuesta.choices[0].message.content.strip()
        partes = dividir_mensaje(reply)
        for parte in partes:
            await update.message.reply_text(parte)
            time.sleep(1)

    except Exception as e:
        logging.error(f"Error con OpenAI: {e}")
        await update.message.reply_text("⚠️ Hubo un problema al procesar tu mensaje. Intenta más tarde.")

# --- Bot principal ---
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
