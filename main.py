import logging
import os
import asyncio
from datetime import datetime, timedelta
from telegram import Update, Bot
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackContext
)
import openai
import sqlite3

# --- Config ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))  # Reemplazar con tu user ID
DB_PATH = "usuarios.db"
GRATIS_LIMITE = 5

openai.api_key = OPENAI_API_KEY
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- DB Setup ---
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    plan TEXT,
    inicio TEXT,
    fin TEXT,
    usos_gratis INTEGER DEFAULT 0
)''')
conn.commit()

# --- Utilidades ---
def dividir_mensaje(texto, max_caracteres=4095):
    bloques = []
    parrafos = texto.split('\n')
    actual = ""
    for p in parrafos:
        if len(actual) + len(p) + 1 < max_caracteres:
            actual += p + "\n"
        else:
            bloques.append(actual.strip())
            actual = p + "\n"
    if actual:
        bloques.append(actual.strip())
    return bloques

def verificar_vencimiento(user_id):
    c.execute("SELECT fin FROM usuarios WHERE user_id = ?", (user_id,))
    resultado = c.fetchone()
    if resultado:
        fin = datetime.fromisoformat(resultado[0])
        if datetime.now() > fin:
            c.execute("UPDATE usuarios SET plan = 'vencido' WHERE user_id = ?", (user_id,))
            conn.commit()
            return True
    return False

def registrar_usuario(user_id, username):
    c.execute("SELECT * FROM usuarios WHERE user_id = ?", (user_id,))
    if not c.fetchone():
        hoy = datetime.now()
        c.execute("INSERT INTO usuarios (user_id, username, plan, inicio, fin, usos_gratis) VALUES (?, ?, 'gratis', ?, ?, 0)",
                  (user_id, username, hoy.isoformat(), (hoy + timedelta(days=7)).isoformat()))
        conn.commit()

async def notificar_admin(bot: Bot, mensaje: str):
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ ERROR:
{mensaje}")
    except Exception as e:
        logger.error("Fallo al notificar admin: %s", str(e))

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    registrar_usuario(user.id, user.username)
    nombre = user.first_name or ""

    saludo = (
        f"👋 ¡Hola {nombre}! Estoy acá para acompañarte.\n\n"
        "Podés contarme cómo te sentís, qué te preocupa o en qué querés trabajar hoy.\n"
        "No hay respuestas incorrectas.\n\n"
        "💬 Solo escribí lo que quieras compartir. Si sos una pareja, pueden hablar juntos también.\n"
        "Estoy para escucharte."
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=saludo)

async def ejercicios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    textos = [
        "🏋️ Ejercicio sugerido:\nClaro, aquí tienes un ejercicio breve y relajante que puedes intentar si te sientes en un estado neutral:\n\nEjercicio de Respiración Consciente y Escaneo Corporal",
        "1. Encuentra un Lugar Tranquilo: Busca un lugar donde puedas sentarte o recostarte sin interrupciones.",
        "2. Cierra los Ojos: Cierra suavemente los ojos y lleva tu atención a tu respiración.\nNo trates de cambiarla, solo obsérvala.",
        "3. Respira Profundamente: Inhala por la nariz contando hasta cuatro, sostené el aire cuatro segundos, y exhala por la boca contando hasta seis. Repite esto cinco veces.",
        "4. Escaneo Corporal: Lleva tu atención desde los pies hacia la cabeza, parte por parte, notando tensión o sensaciones."
    ]
    for t in textos:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=t)

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Comandos disponibles: /start /ayuda /ejercicios /planes")

async def planes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "🌐 Planes Disponibles:\n\n"
        "Plan Semanal: $2.000\nPlan Mensual: $6.500\nPlan Anual: $60.000\n\n"
        "Una vez que elijas tu plan, recibirás el enlace de pago por MercadoPago."
    )
    await update.message.reply_text(texto)

async def mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        if verificar_vencimiento(user.id):
            await update.message.reply_text("Tu plan ha vencido. Usá /planes para renovarlo.")
            return

        c.execute("SELECT usos_gratis, plan FROM usuarios WHERE user_id = ?", (user.id,))
        datos = c.fetchone()
        usos, plan = datos or (0, "gratis")

        if plan == "gratis" and usos >= GRATIS_LIMITE:
            await update.message.reply_text("❌ Alcanzaste el límite de interacciones gratuitas. Usá /planes para continuar.")
            return

        prompt = update.message.text
        respuesta = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        respuesta_texto = respuesta.choices[0].message.content
        bloques = dividir_mensaje(respuesta_texto)

        for b in bloques:
            await update.message.reply_text(b)

        if plan == "gratis":
            c.execute("UPDATE usuarios SET usos_gratis = usos_gratis + 1 WHERE user_id = ?", (user.id,))
            conn.commit()

    except Exception as e:
        logger.error("Fallo al responder mensaje: %s", str(e))
        await notificar_admin(context.bot, str(e))

# --- Main ---
if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ejercicios", ejercicios))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("planes", planes))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensaje))

    print("🤖 Bot iniciado y escuchando...")
    app.run_polling()}
