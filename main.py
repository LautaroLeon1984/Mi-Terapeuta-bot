import logging
import os
import json
import datetime
import openai
import asyncio
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, ContextTypes, CommandHandler,
                          MessageHandler, filters)

# Configuración básica
logging.basicConfig(level=logging.INFO)
ADMIN_ID = 818432829
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Base de datos local
BASE_DATOS = "usuarios.json"
if not os.path.exists(BASE_DATOS):
    with open(BASE_DATOS, "w") as f:
        json.dump({}, f)

def cargar_usuarios():
    with open(BASE_DATOS, "r") as f:
        return json.load(f)

def guardar_usuarios(usuarios):
    with open(BASE_DATOS, "w") as f:
        json.dump(usuarios, f, indent=2)

# ----------------------------- Funciones auxiliares -----------------------------

def dividir_mensaje_por_puntos(texto, max_len=4095):
    partes = []
    parrafos = texto.replace("**", "").split("\n\n")
    actual = ""
    for p in parrafos:
        if len(actual) + len(p) + 2 <= max_len:
            actual += p + "\n\n"
        else:
            partes.append(actual.strip())
            actual = p + "\n\n"
    if actual:
        partes.append(actual.strip())
    return partes

async def notificar_admin(context, mensaje):
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 ADMIN ALERT:\n{mensaje}")
    except Exception as e:
        logging.error(f"Fallo al notificar al admin: {e}")

# ----------------------------- Manejo de usuarios -----------------------------

def verificar_usuario(user_id):
    usuarios = cargar_usuarios()
    usuario = usuarios.get(str(user_id))
    if not usuario:
        usuarios[str(user_id)] = {
            "interacciones": 0,
            "fecha_inicio": None,
            "plan": None
        }
        guardar_usuarios(usuarios)
        return usuarios[str(user_id)]
    return usuario

def tiene_plan_activo(user_data):
    if not user_data.get("plan") or not user_data.get("fecha_inicio"):
        return False
    dias = {
        "semanal": 7,
        "quincenal": 15,
        "mensual": 30,
        "trimestral": 90,
        "semestral": 180,
        "anual": 365
    }
    inicio = datetime.datetime.strptime(user_data["fecha_inicio"], "%Y-%m-%d")
    vigencia = dias.get(user_data["plan"], 0)
    return (datetime.datetime.now() - inicio).days < vigencia

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
        "🚫 Tu acceso gratuito ha finalizado.\nSeleccioná un plan para seguir usando el bot:",
        reply_markup=InlineKeyboardMarkup(botones)
    )

# ----------------------------- Comandos -----------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        nombre = update.effective_user.first_name or "Usuario"
        await update.message.reply_text(
            f"¡Hola {nombre}! Soy tu terapeuta IA. Estoy disponible 24/7 para acompañarte emocionalmente.\n" +
            "Podés escribirme cuando quieras. Usá /ayuda para conocer mis funciones."
        )
    except Exception as e:
        await notificar_admin(context, f"Error en /start: {e}")

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Este bot ofrece contención emocional, ejercicios de respiración y acompañamiento. \nEscribí cómo te sentís y te responderé.")

async def planes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await mostrar_planes(update, context)

async def ejercicios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        respuesta = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{
                "role": "system",
                "content": "Sos un terapeuta empático. Da ejercicios guiados para calmar la mente."
            }, {
                "role": "user",
                "content": "Dame un ejercicio breve y relajante para reconectar emocionalmente."
            }]
        )
        texto = respuesta.choices[0].message.content.replace("**", "")
        partes = dividir_mensaje_por_puntos(texto)
        for parte in partes:
            await update.message.reply_text(parte)
    except Exception as e:
        await notificar_admin(context, f"Error en /ejercicios: {e}")
        await update.message.reply_text("⚠️ Ocurrió un error. Intenta nuevamente más tarde.")

# ----------------------------- Mensajes -----------------------------

async def mensaje_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = str(update.effective_user.id)
        usuarios = cargar_usuarios()
        user_data = verificar_usuario(user_id)

        if not tiene_plan_activo(user_data):
            if user_data["interacciones"] >= 5:
                await mostrar_planes(update, context)
                return

        # Consulta a OpenAI
        prompt = update.message.text.strip()
        respuesta = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Sos un terapeuta empático, claro y conciso. Respondé sin juicios."},
                {"role": "user", "content": prompt}
            ]
        )
        texto = respuesta.choices[0].message.content.replace("**", "")
        partes = dividir_mensaje_por_puntos(texto)
        for parte in partes:
            await update.message.reply_text(parte)

        # Registrar interacción útil
        user_data["interacciones"] += 1
        usuarios[user_id] = user_data
        guardar_usuarios(usuarios)

    except Exception as e:
        await notificar_admin(context, f"Error procesando mensaje: {e}")
        await update.message.reply_text("⚠️ Ocurrió un error inesperado. Por favor, intenta más tarde.")

# ----------------------------- Flask para mantener activo -----------------------------

app = Flask(__name__)
@app.route('/')
def index():
    return 'Bot activo.'

def run():
    app.run(host='0.0.0.0', port=8080)

# ----------------------------- Main -----------------------------

if __name__ == '__main__':
    Thread(target=run).start()

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ayuda", ayuda))
    application.add_handler(CommandHandler("planes", planes))
    application.add_handler(CommandHandler("ejercicios", ejercicios))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensaje_handler))

    logging.info("🤖 Bot iniciado y esperando mensajes...")
    application.run_polling()
