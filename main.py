import logging
import os
import openai
import asyncio
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# --- CONFIGURACIÓN ---
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = 818432829  # Telegram ID de @Lautaro_Leon
FREE_INTERACTIONS = 5

# --- BASE DE DATOS SIMPLIFICADA ---
usuarios = {}  # user_id: {"inicio": timestamp, "vencimiento": timestamp, "interacciones": int}

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- FUNCIONES AUXILIARES ---
def obtener_nombre(update: Update):
    return update.effective_user.first_name or "Usuario"

def verificar_plan(user_id):
    datos = usuarios.get(user_id)
    if not datos:
        return False
    return time.time() < datos["vencimiento"]

def registrar_usuario(user_id):
    if user_id not in usuarios:
        ahora = time.time()
        usuarios[user_id] = {
            "inicio": ahora,
            "vencimiento": ahora + 30 * 24 * 3600,  # 30 días
            "interacciones": 0
        }

def dividir_mensaje_por_puntos(texto):
    partes = []
    secciones = texto.split('\n\n')
    actual = ""
    for s in secciones:
        s = s.replace("**", "")
        if len(actual + s) + 2 <= 4095:
            actual += s + "\n\n"
        else:
            partes.append(actual.strip())
            actual = s + "\n\n"
    if actual:
        partes.append(actual.strip())
    return partes

async def enviar_mensaje_dividido(context, chat_id, texto):
    partes = dividir_mensaje_por_puntos(texto)
    for p in partes:
        await context.bot.send_message(chat_id=chat_id, text=p)
        await asyncio.sleep(0.5)

async def notificar_admin(context: ContextTypes.DEFAULT_TYPE, error):
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ Error en el bot:\n{error}")

# --- COMANDOS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        nombre = obtener_nombre(update)
        registrar_usuario(update.effective_user.id)
        mensaje = (
            f"👋 Hola, {nombre}! Estoy acá para acompañarte.\n\n"
            "Podés contarme cómo te sentís, qué te preocupa o en qué querés trabajar hoy. No hay respuestas incorrectas.\n\n"
            "💬 Solo escribí lo que quieras compartir. Si estas con tu pareja, pueden hablar juntos también.\n\n"
            "Estoy para escucharte."
        )
        await update.message.reply_text(mensaje)
    except Exception as e:
        logging.error(e)
        await notificar_admin(context, e)

async def ejercicios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        texto = (
            "🏋️ Ejercicio sugerido:\n"
            "Claro, aquí tienes un ejercicio breve y relajante que puede ayudar a alguien que se siente neutral a reconectar con sus emociones y sensaciones físicas:\n\n"
            "Ejercicio de Respiración Consciente y Sensación Corporal\n\n"
            "1. Encuentra un Lugar Tranquilo: Busca un lugar donde puedas sentarte o recostarte cómodamente sin ser interrumpido durante unos minutos.\n\n"
            "2. Cierra los Ojos: Cierra suavemente los ojos y lleva tu atención a tu respiración. No trates de cambiarla, simplemente obsérvala.\n\n"
            "3. Respira Profundamente: Inhala profundamente por la nariz contando hasta cuatro, manten el aire contando hasta cuatro, y luego exhala lentamente por la boca contando hasta seis. Repite esto de cinco a diez veces.\n\n"
            "4. Escaneo Corporal: Comienza a llevar tu atención a diferentes partes de tu cuerpo, empezando por los pies y subiendo lentamente hasta la cabeza. Observa cualquier sensación, tensión o relajación que puedas sentir."
        )
        await enviar_mensaje_dividido(context, update.effective_chat.id, texto)
    except Exception as e:
        logging.error(e)
        await notificar_admin(context, e)

async def planes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = (
        "📆 Planes disponibles:\n\n"
        "💸 Plan Semanal: $3.000\n"
        "💸 Plan Mensual: $10.000\n"
        "💸 Plan Anual: $99.000\n\n"
        "Consultá por promociones especiales o medios de pago!"
    )
    await update.message.reply_text(mensaje)

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Este bot es un acompañante emocional. Usa /start para comenzar, /ejercicios para ejercicios, /planes para ver opciones de suscripción.")

async def mensaje_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        registrar_usuario(user_id)

        if not verificar_plan(user_id):
            usuarios[user_id]["interacciones"] += 1
            if usuarios[user_id]["interacciones"] > FREE_INTERACTIONS:
                await update.message.reply_text("Has alcanzado el límite gratuito. Usá /planes para suscribirte y seguir usando el bot.")
                return

        mensaje_usuario = update.message.text
        nombre = obtener_nombre(update)

        respuesta = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Sos un terapeuta emocional empático y breve."},
                {"role": "user", "content": mensaje_usuario},
            ]
        )
        respuesta_texto = respuesta.choices[0].message.content.strip()
        await update.message.reply_text(f"{respuesta_texto}")
    except Exception as e:
        logging.error(e)
        await notificar_admin(context, e)

# --- APP ---
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("ejercicios", ejercicios))
app.add_handler(CommandHandler("planes", planes))
app.add_handler(CommandHandler("ayuda", ayuda))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensaje_handler))

if __name__ == '__main__':
    print("Bot iniciado...")
    app.run_polling()
