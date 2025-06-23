import os
import logging
import datetime
import traceback
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, CallbackContext
)
from openai import OpenAI

# Configuraciones iniciales
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", 818432829))

# Inicializar cliente OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# Estructura de almacenamiento en memoria (puede ser reemplazada por base de datos real)
user_data = {}

# Setup logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Función para enviar mensajes divididos inteligentemente
def split_message(message, limit=4095):
    parts = []
    while len(message) > limit:
        split_index = message.rfind("\n", 0, limit)
        if split_index == -1:
            split_index = limit
        parts.append(message[:split_index])
        message = message[split_index:].lstrip()
    parts.append(message)
    return parts

# Saludo inicial
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    user_name = user.first_name or "amig@"

    # Registro
    if user_id not in user_data:
        user_data[user_id] = {
            "start": datetime.datetime.now(),
            "plan": None,
            "messages": 0
        }

    saludo = f"\U0001F44B Hola {user_name}! Estoy acá para acompañarte.\n\n" \
             "Podés contarme cómo te sentís, qué te preocupa o en qué querés trabajar hoy.\n" \
             "No hay respuestas incorrectas.\n\n" \
             "... Solo escribí lo que quieras compartir. Si estas con tu pareja, pueden hablar juntos también.\n\n" \
             "Estoy para escucharte."
    await context.bot.send_message(chat_id=user_id, text=saludo)

# Comando /planes
async def planes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = (
        "📦 Planes disponibles:\n\n"
        "🔹 *Plan Semanal* - $3.000\n"
        "🔹 *Plan Mensual* - $9.500\n"
        "🔹 *Plan Anual* - $85.000\n\n"
        "Podés contratar un plan para continuar después de usar tus 5 interacciones gratuitas."
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=mensaje, parse_mode='Markdown')

# Comando /ejercicios
async def ejercicios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    texto = (
        "🧘‍♀️ Ejercicio sugerido:\n"
        "Claro, aquí tienes un ejercicio breve y relajante que puede ayudar a reconectar con tus emociones y sensaciones físicas:\n\n"
        "Ejercicio de Respiración Consciente y Escaneo Corporal\n\n"
        "1. Encuentra un Lugar Tranquilo: Busca un lugar donde puedas sentarte o recostarte cómodamente sin interrupciones.\n\n"
        "2. Cierra los Ojos: Cierra suavemente los ojos y lleva tu atención a tu respiración.\n\n"
        "3. Respira Profundamente: Inhala profundo por la nariz contando hasta cuatro, mantené el aire, y exhala por la boca contando hasta seis. Repetí esto tres veces.\n\n"
        "4. Escaneo Corporal: Comenzá por los pies y subí lentamente la atención por cada parte de tu cuerpo. Observá cualquier sensación, sin juzgar.\n\n"
        "5. Final: Abrí lentamente los ojos y notá cómo te sentís ahora."
    )

    for parte in split_message(texto):
        await context.bot.send_message(chat_id=user_id, text=parte)

# Verificación de plan y generación de respuesta
async def handle_message(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    mensaje = update.message.text

    # Registro de usuario si aún no existe
    if user_id not in user_data:
        user_data[user_id] = {"start": datetime.datetime.now(), "plan": None, "messages": 0}

    # Verificar vencimiento
    plan_info = user_data[user_id].get("plan")
    if plan_info and plan_info < datetime.datetime.now():
        user_data[user_id]["plan"] = None

    # Verificar límite gratuito
    if not user_data[user_id]["plan"] and user_data[user_id]["messages"] >= 5:
        await context.bot.send_message(chat_id=user_id, text="🚫 Has alcanzado el límite gratuito. Usá /planes para continuar.")
        return

    # Aumentar contador
    user_data[user_id]["messages"] += 1

    # Llamada a OpenAI
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": mensaje}],
            max_tokens=400
        )
        respuesta = response.choices[0].message.content
        partes = split_message(respuesta)
        for parte in partes:
            await context.bot.send_message(chat_id=user_id, text=parte)

    except Exception as e:
        logger.error("Error al procesar mensaje:", exc_info=e)
        await context.bot.send_message(chat_id=user_id, text="❌ Ocurrió un error procesando tu mensaje.")
        # Notificar al admin
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ Error para el usuario {user_name} ({user_id}):\n{traceback.format_exc()}")

# Función principal
if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("planes", planes))
    app.add_handler(CommandHandler("ejercicios", ejercicios))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot iniciado.")
    app.run_polling()
