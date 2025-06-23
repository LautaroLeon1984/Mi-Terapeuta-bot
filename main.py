import logging
import openai
import os
import json
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# --- Configuración ---
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = 818432829
USUARIOS_DB = "usuarios.json"

# --- Logging ---
logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Cargar base de datos local ---
def cargar_usuarios():
    if os.path.exists(USUARIOS_DB):
        with open(USUARIOS_DB, 'r') as f:
            return json.load(f)
    return {}

def guardar_usuarios(data):
    with open(USUARIOS_DB, 'w') as f:
        json.dump(data, f, indent=2)

usuarios = cargar_usuarios()

# --- Planes ---
PLANES = {
    "semanal": 7,
    "quincenal": 15,
    "mensual": 30,
    "trimestral": 90,
    "semestral": 180,
    "anual": 365
}

URL_PLANES = [
    ["Plan Semanal – $4.000", "https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=21746b5ae9c94be08c0b9abcb9484f0b"],
    ["Plan Quincenal – $7.000", "https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=32e17d17ce334234ac3d5577bfc3fea0"],
    ["Plan Mensual – $12.000", "https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=1a92e8b1e31d44b99188505cf835483d"],
    ["Plan Trimestral – $30.000", "https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=9a17a9ac63844309ab87119b56f6f71e"],
    ["Plan Semestral – $55.000", "https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=cff15077ebe84fb88ccd0e20afa29437"],
    ["Plan Anual – $99.000", "https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=3f7b1e3b69d544f78c7d9862e1391228"]
]

# --- Utilidades ---
def plan_activo(usuario):
    datos = usuarios.get(str(usuario.id), {})
    if 'inicio_plan' in datos and 'duracion' in datos:
        vencimiento = datetime.fromisoformat(datos['inicio_plan']) + timedelta(days=datos['duracion'])
        return datetime.now() < vencimiento
    return False

def registrar_usuario(usuario):
    uid = str(usuario.id)
    if uid not in usuarios:
        usuarios[uid] = {
            "nombre": usuario.first_name,
            "interacciones": 0,
            "inicio_plan": None,
            "duracion": 0
        }
        guardar_usuarios(usuarios)

def contar_interaccion(usuario):
    uid = str(usuario.id)
    if uid not in usuarios:
        registrar_usuario(usuario)
    if not plan_activo(usuario):
        usuarios[uid]["interacciones"] += 1
        guardar_usuarios(usuarios)

    return usuarios[uid]["interacciones"]

def notificar_admin(mensaje):
    try:
        application.bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ ERROR: {mensaje}")
    except Exception as e:
        logger.error(f"No se pudo notificar al admin: {e}")

# --- ChatGPT ---
async def responder_con_chatgpt(mensaje_usuario):
    try:
        respuesta = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Actuá como un terapeuta empático, claro y conciso. Tu rol es acompañar emocionalmente con sensibilidad."},
                {"role": "user", "content": mensaje_usuario}
            ]
        )
        return respuesta.choices[0].message.content.strip()
    except Exception as e:
        notificar_admin(f"Fallo al generar respuesta IA: {e}")
        return "Ocurrió un error al procesar tu mensaje. Intentalo nuevamente en unos minutos."

# --- Funciones principales ---
async def saludo_personalizado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.effective_user.first_name or "Hola"
    mensaje = (
        f"👋 ¡Hola, {nombre}! Estoy acá para acompañarte.\n\n"
        "Podés contarme cómo te sentís, qué te preocupa o en qué querés trabajar hoy.\n"
        "No hay respuestas incorrectas.\n\nEstoy para escucharte."
    )
    await update.message.reply_text(mensaje)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await saludo_personalizado(update, context)

async def planes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    botones = [[InlineKeyboardButton(titulo, url=url)] for titulo, url in URL_PLANES]
    await update.message.reply_text("Elegí un plan para continuar usando el bot:", reply_markup=InlineKeyboardMarkup(botones))

async def ejercicios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "Ejercicio sugerido:\n\n"
        "Ejercicio de Escaneo Corporal y Respiración:\n\n"
        "1. Encuentra un Lugar Tranquilo: Busca un lugar donde puedas sentarte o recostarte sin interrupciones.\n\n"
        "2. Cierra los Ojos: Lleva tu atención hacia adentro.\n\n"
        "3. Respira Profundamente: Inhala por la nariz contando hasta 4, retén, y exhala por la boca contando hasta 6.\n\n"
        "4. Escaneo Corporal: Dirige tu atención desde los pies hasta la cabeza, observando sensaciones."
    )
    partes = texto.split("\n\n")
    for parte in partes:
        if parte.strip():
            await update.message.reply_text(parte.strip())

async def mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        usuario = update.effective_user
        registrar_usuario(usuario)

        if plan_activo(usuario):
            texto_usuario = update.message.text.strip()
            respuesta = await responder_con_chatgpt(texto_usuario)
            await update.message.reply_text(respuesta)
        else:
            interacciones = contar_interaccion(usuario)
            if interacciones <= 5:
                texto_usuario = update.message.text.strip()
                respuesta = await responder_con_chatgpt(texto_usuario)
                await update.message.reply_text(respuesta)
            else:
                await planes(update, context)

    except Exception as e:
        notificar_admin(f"Error en mensaje(): {e}")
        await update.message.reply_text("Ocurrió un error. Intentalo nuevamente más tarde.")

# --- Lanzar bot ---
if __name__ == '__main__':
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("planes", planes))
    application.add_handler(CommandHandler("ejercicios", ejercicios))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensaje))

    logger.info("🤖 Bot iniciado y esperando mensajes...")
    application.run_polling()}
