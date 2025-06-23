import os
import logging
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    filters, CallbackContext
)
from openai import OpenAI

# Configuraciones iniciales
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", 818432829))
openai = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO)

# Inicializar base de datos
conn = sqlite3.connect("bot_usuarios.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS usuarios (
        user_id INTEGER PRIMARY KEY,
        nombre TEXT,
        fecha_inicio TEXT,
        fecha_vencimiento TEXT
    )
''')
conn.commit()

# Verificar si el usuario tiene acceso activo
def tiene_acceso(user_id: int) -> bool:
    cursor.execute("SELECT fecha_vencimiento FROM usuarios WHERE user_id = ?", (user_id,))
    fila = cursor.fetchone()
    if not fila:
        return True  # Permitimos hasta 5 mensajes antes del registro
    try:
        vencimiento = datetime.strptime(fila[0], "%Y-%m-%d")
        return vencimiento >= datetime.now()
    except:
        return False

# Dividir texto inteligentemente
def dividir_mensaje(texto: str, limite=4095):
    partes = []
    while len(texto) > limite:
        corte = texto.rfind("\n", 0, limite)
        if corte == -1:
            corte = limite
        partes.append(texto[:corte].strip())
        texto = texto[corte:].strip()
    partes.append(texto)
    return partes

# Registro o actualización
def registrar_usuario(user_id: int, nombre: str):
    hoy = datetime.now()
    vencimiento = hoy + timedelta(days=7)
    cursor.execute("REPLACE INTO usuarios (user_id, nombre, fecha_inicio, fecha_vencimiento) VALUES (?, ?, ?, ?)",
                   (user_id, nombre, hoy.strftime("%Y-%m-%d"), vencimiento.strftime("%Y-%m-%d")))
    conn.commit()

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    registrar_usuario(user.id, user.first_name)
    mensaje = f"Hola {user.first_name}! 👋\nSoy tu terapeuta IA. Podés escribirme cuando quieras.\nUsá /ayuda para ver opciones disponibles."
    await update.message.reply_text(mensaje)

# Comando /ayuda
async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Comandos disponibles:\n/start – Iniciar\n/planes – Ver planes\n/ejercicios – Ver ejercicios\n/resumen – Solicitar resumen")

# Comando /planes
async def mostrar_planes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    botones = [
        [InlineKeyboardButton("🗓️ Plan Semanal – $4.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=21746b5ae9c94be08c0b9abcb9484f0b")],
        [InlineKeyboardButton("📆 Plan Quincenal – $7.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=32e17d17ce334234ac3d5577bfc3fea0")],
        [InlineKeyboardButton("🗓️ Plan Mensual – $12.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=1a92e8b1e31d44b99188505cf835483d")],
        [InlineKeyboardButton("📅 Plan Trimestral – $30.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=9a17a9ac63844309ab87119b56f6f71e")],
        [InlineKeyboardButton("📅 Plan Semestral – $55.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=cff15077ebe84fb88ccd0e20afa29437")],
        [InlineKeyboardButton("📅 Plan Anual – $99.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=3f7b1e3b69d544f78c7d9862e1391228")],
    ]
    await update.message.reply_text("Seleccioná un plan para continuar:", reply_markup=InlineKeyboardMarkup(botones))

# Comando /ejercicios
async def ejercicios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "🧘‍♀️ Ejercicio sugerido:\n"
        "Claro, aquí tienes un ejercicio breve y relajante que puedes intentar si te sientes en un estado neutral:\n\n"
        "Ejercicio de Respiración Consciente y Sensación Corporal\n\n"
        "1. Encuentra un Lugar Tranquilo: Busca un lugar donde puedas sentarte o recostarte cómodamente sin interrupciones.\n\n"
        "2. Cierra los Ojos: Cierra suavemente los ojos y enfoca tu atención en la respiración.\n\n"
        "3. Respira Profundamente: Inhala por la nariz contando hasta cuatro, sostén el aire, exhala por la boca contando hasta seis.\n\n"
        "4. Escaneo Corporal: Lleva tu atención de los pies a la cabeza, observando cada parte del cuerpo sin juzgar."
    )
    partes = dividir_mensaje(texto)
    for parte in partes:
        await update.message.reply_text(parte)

# Comando /resumen
async def resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"{update.effective_user.first_name}, aún no hay resumen disponible en esta versión. ¡Pronto estará habilitado!")

# Middleware de control de acceso y errores
async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if not tiene_acceso(user_id):
            await mostrar_planes(update, context)
            return
        pregunta = update.message.text
        respuesta = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "Brindá respuestas empáticas, claras y concisas."},
                      {"role": "user", "content": pregunta}]
        )
        texto = respuesta.choices[0].message.content
        partes = dividir_mensaje(texto)
        for parte in partes:
            await update.message.reply_text(parte)
    except Exception as e:
        logging.error(f"Error grave: {e}")
        if ADMIN_CHAT_ID:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"🚨 Error grave en el bot: {e}")

# Configuración del bot
if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("planes", mostrar_planes))
    app.add_handler(CommandHandler("ejercicios", ejercicios))
    app.add_handler(CommandHandler("resumen", resumen))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_mensaje))

    print("🤖 Bot iniciado y esperando mensajes...")
    app.run_polling()
