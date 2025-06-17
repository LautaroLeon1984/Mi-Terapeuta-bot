import os
import logging
import openai
import asyncio
import json
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters

# --- Configuración de claves ---
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- Logging ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- Keep Alive con Flask ---
app_web = Flask(__name__)

@app_web.route("/")
def home():
    return "Bot activo", 200

def run():
    app_web.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- Usuarios ---
USUARIOS_FILE = "usuarios_autorizados.json"

def cargar_usuarios():
    if os.path.exists(USUARIOS_FILE):
        with open(USUARIOS_FILE, "r") as f:
            return set(json.load(f))
    return set()

def guardar_usuario(user_id):
    usuarios = cargar_usuarios()
    usuarios.add(user_id)
    with open(USUARIOS_FILE, "w") as f:
        json.dump(list(usuarios))

usuarios_autorizados = cargar_usuarios()
usuarios_temporales = {}
inactividad = {}
tareas_inactividad = {}
emociones_detectadas = {}

# --- Funciones del bot ---
async def mostrar_planes(update, context):
    botones = [
        [InlineKeyboardButton("🗓️ Plan Semanal – $4.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=21746b5ae9c94be08c0b9abcb9484f0b")],
        [InlineKeyboardButton("🗓️ Plan Quincenal – $7.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=32e17d17ce334234ac3d5577bfc3fea0")],
        [InlineKeyboardButton("🗓️ Plan Mensual – $12.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=1a92e8b1e31d44b99188505cf835483d")],
        [InlineKeyboardButton("🗓️ Plan Trimestral – $30.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=9a17a9ac63844309ab87119b56f6f71e")],
        [InlineKeyboardButton("🗓️ Plan Semestral – $55.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=cff15077ebe84fb88ccd0e20afa29437")],
        [InlineKeyboardButton("🗓️ Plan Anual – $99.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=3f7b1e3b69d544f78c7d9862e1391228")],
    ]
    await update.message.reply_text(
        "🚫 Tu acceso gratuito ha finalizado.\nSeleccioná uno de los planes para seguir usando el bot:",
        reply_markup=InlineKeyboardMarkup(botones)
    )

async def ayuda(update, context):
    await update.message.reply_text(
        "🤖 Soy tu terapeuta virtual. Podés escribirme libremente, de forma individual o en pareja.\n\n"
        "📌 Gratis por 5 mensajes. Luego, podés suscribirte desde /planes.\n"
        "📋 En cualquier momento podés pedir un resumen con /resumen.\n"
        "🔐 Todo es confidencial y automático. Estoy para escucharte."
    )

async def planes(update, context):
    await mostrar_planes(update, context)

async def resumen(update, context):
    user_id = update.effective_user.id
    await generar_resumen(user_id, context, update)

async def reset(update, context):
    user_id = update.effective_user.id
    usuarios_temporales[user_id] = []
    await update.message.reply_text("🔁 Historial borrado. Podés comenzar una nueva conversación cuando quieras.")

async def ejercicio(update, context):
    user_id = update.effective_user.id
    emocion = emociones_detectadas.get(user_id, "neutro")
    client = openai.OpenAI()
    try:
        respuesta = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": f"Sos un terapeuta. Sugerí un ejercicio breve, práctico y relajante para una persona que se siente {emocion}."}
            ],
            temperature=0.6,
            max_tokens=200
        )
        ejercicio_texto = respuesta.choices[0].message.content
        await update.message.reply_text(f"🧘‍♀️ Ejercicio sugerido:\n{ejercicio_texto}")
    except Exception as e:
        logging.error(f"Error al generar ejercicio: {e}")
        await update.message.reply_text("⚠️ Ocurrió un error al generar el ejercicio.")

async def activar_acceso(update, context):
    user_id = update.effective_user.id
    guardar_usuario(user_id)
    await update.message.reply_text("✅ Tu acceso fue activado. ¡Gracias por tu suscripción!")

async def generar_resumen(user_id, context, update):
    mensajes = usuarios_temporales.get(user_id, [])
    if not mensajes:
        await update.message.reply_text("No hay suficiente historial para generar un resumen todavía.")
        return
    client = openai.OpenAI()
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Resumí lo conversado en formato simple para que el usuario pueda retomarlo luego."},
                *[{"role": "user", "content": m} for m in mensajes]
            ],
            temperature=0.5,
            max_tokens=300
        )
        resumen = response.choices[0].message.content
        await update.message.reply_text(f"📝 Resumen de la conversación:\n{resumen}\n\nGuardalo para retomarlo la próxima vez.")
        usuarios_temporales[user_id] = []
    except Exception as e:
        logging.error(f"Error al generar resumen: {e}")

async def verificar_inactividad(user_id, context, update):
    await asyncio.sleep(600)
    if inactividad.get(user_id):
        await update.message.reply_text("⏰ ¿Querés seguir conversando o preferís un resumen de lo hablado?")
        await asyncio.sleep(120)
        if inactividad.get(user_id):
            await generar_resumen(user_id, context, update)
        inactividad[user_id] = False
        tareas_inactividad.pop(user_id, None)

async def responder_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    voice = update.message.voice
    if not voice:
        return
    file = await context.bot.get_file(voice.file_id)
    file_path = f"{user_id}_audio.ogg"
    await file.download_to_drive(file_path)
    try:
        with open(file_path, "rb") as audio_file:
            transcript = openai.Audio.transcribe("whisper-1", audio_file)
            texto = transcript["text"]
            if len(texto.strip()) < 5:
                await update.message.reply_text("🔇 No pude entender claramente el audio. ¿Podés repetirlo o escribirlo?")
                return
            await update.message.reply_text(f"✅ Audio recibido. Esto entendí: \"{texto}\"")
            update.message.text = texto
            await responder(update, context)
    except Exception as e:
        logging.error(f"Error al transcribir audio: {e}")
        await update.message.reply_text("⚠️ Ocurrió un error al procesar tu audio.")
    finally:
        os.remove(file_path)

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.lower()

    if user_id not in usuarios_autorizados and user_id not in usuarios_temporales:
        await update.message.reply_text(
            "👋 ¡Hola! Bienvenido/a. Estoy acá para acompañarte.\n\nPodés contarme cómo te sentís, qué te preocupa o en qué querés trabajar hoy. No hay respuestas incorrectas.\n\n💬 Solo escribí lo que quieras compartir. Si sos una pareja, pueden hablar juntos también.\n\nEstoy para escucharte."
        )

    if text == "/reset":
        await reset(update, context)
        return

    if text == "/ejercicio":
        await ejercicio(update, context)
        return

    if text in ["ya pagué", "ya pague", "pagué", "pagado"]:
        await activar_acceso(update, context)
        return

    if text.startswith("📝 resumen de la conversación") or "guardalo para retomarlo" in text:
        usuarios_temporales[user_id] = [text]
        await update.message.reply_text("📌 Resumen recibido. Retomamos la conversación desde ese punto. Contame en qué querés enfocarte hoy.")
        return

    if user_id not in usuarios_autorizados:
        if user_id not in usuarios_temporales:
            usuarios_temporales[user_id] = []
        if len(usuarios_temporales[user_id]) >= 5:
            await mostrar_planes(update, context)
            return

    inactividad[user_id] = True
    if user_id in tareas_inactividad:
        tareas_inactividad[user_id].cancel()
    tarea = context.application.create_task(verificar_inactividad(user_id, context, update))
    tareas_inactividad[user_id] = tarea

    usuarios_temporales.setdefault(user_id, []).append(update.message.text)

    client = openai.OpenAI()
    try:
        emociones = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Clasificá el tono emocional del siguiente mensaje como uno de estos: feliz, triste, ansioso, enojado, neutro."},
                {"role": "user", "content": update.message.text}
            ],
            temperature=0.3,
            max_tokens=10
        )
        tono = emociones.choices[0].message.content.lower()
        emociones_detectadas[user_id] = tono
        logging.info(f"Emoción detectada: {tono}")
    except:
        tono = "neutro"

    try:
        respuesta = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": f"Actuá como un terapeuta empático especializado en personas y parejas. El usuario parece estar {tono}. Respondé con comprensión y sin juzgar."},
                {"role": "user", "content": update.message.text}
            ],
            temperature=0.7,
            max_tokens=500
        )
        reply = respuesta.choices[0].message.content
        await update.message.reply_text(reply)
        inactividad[user_id] = False
    except Exception as e:
        logging.error(f"Error al generar respuesta: {e}")
        await update.message.reply_text("⚠️ Ocurrió un error al procesar tu mensaje.")

# --- Inicio del bot ---
if __name__ == "__main__":
    keep_alive()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("planes", planes))
    app.add_handler(CommandHandler("resumen", resumen))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("ejercicio", ejercicio))
    app.add_handler(MessageHandler(filters.VOICE, responder_audio))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    print("🤖 Bot iniciado y esperando mensajes...")
    app.run_polling()
