import os
import json
import logging
import datetime
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler,
                          filters, CallbackContext)
from openai import AsyncOpenAI
from flask import Flask
from threading import Thread

# Configuración de logs
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Cargar claves de entorno
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Inicializar clientes
openai = AsyncOpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__)

# Base de datos
DB_PATH = "db.json"
def cargar_db():
    if not os.path.exists(DB_PATH):
        with open(DB_PATH, "w") as f:
            json.dump({}, f)
    with open(DB_PATH, "r") as f:
        return json.load(f)

def guardar_db(db):
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=4)

def dividir_texto(texto, max_len=4095):
    oraciones = texto.split('. ')
    partes = []
    actual = ""
    for o in oraciones:
        if len(actual) + len(o) + 2 <= max_len:
            actual += o + ". "
        else:
            partes.append(actual.strip())
            actual = o + ". "
    if actual:
        partes.append(actual.strip())
    return partes

async def enviar_largo(update: Update, texto: str):
    partes = dividir_texto(texto)
    for parte in partes:
        await update.message.reply_text(parte)

# Manejo de comandos
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    db = cargar_db()

    if user_id not in db:
        db[user_id] = {"inicio": str(datetime.date.today()), "plan": "free", "usos": 0}
        guardar_db(db)

    mensaje = (
        "👋 ¡Hola! Soy tu terapeuta virtual.
"
        "Podés contarme lo que te pasa, y te responderé con empatía, claridad y de forma concisa.
"
        "Las primeras 5 consultas son gratis.
"
        "Cuando se terminen, podés elegir un plan con /planes
"
        "Si necesitás ayuda, escribí /ayuda"
    )
    await update.message.reply_text(mensaje)

async def planes(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = "Este bot está diseñado para ayudarte emocionalmente usando inteligencia artificial. \n"
    texto += "Funciona las 24 hs, no reemplaza a un terapeuta humano. \n"
    texto += "Podés usarlo escribiendo normalmente y te responderé."
    await update.message.reply_text(texto)

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    db = cargar_db()

    if user_id not in db:
        await start(update, context)
        return

    if db[user_id]['plan'] == 'free' and db[user_id]['usos'] >= 5:
        await planes(update, context)
        return

    consulta = update.message.text

    try:
        response = await openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Actuá como terapeuta empático, claro y conciso."},
                {"role": "user", "content": consulta},
            ]
        )
        respuesta = response.choices[0].message.content
        db[user_id]['usos'] += 1
        guardar_db(db)
        await enviar_largo(update, respuesta)
    except Exception as e:
        await update.message.reply_text("❌ Error al procesar la consulta. Intentalo más tarde.")
        logging.error(f"Error con OpenAI: {e}")

# Servidor Flask para mantener vivo
@app.route('/')
def home():
    return "Bot activo."

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# Ejecutar bot
if __name__ == '__main__':
    Thread(target=run_flask).start()

    app_teleg
