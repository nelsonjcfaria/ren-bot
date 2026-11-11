import os, time, threading, json
from datetime import datetime
import telebot
from telebot import types
from openai import OpenAI
from flask import Flask

# --- CONFIG ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
OPENAI_KEY = os.environ.get("OPENAI_KEY", "")
STRIPE_TESTE = os.environ.get("STRIPE_TESTE", "https://buy.stripe.com/teste")
STRIPE_PREMIUM = os.environ.get("STRIPE_PREMIUM", "https://buy.stripe.com/premium")
STRIPE_ULTRA = os.environ.get("STRIPE_ULTRA", "https://buy.stripe.com/ultra")

client = OpenAI(api_key=OPENAI_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=True)

SYSTEM_PROMPT = """Es o Ren, namorado virtual. Es carinhoso, confiante, malandro do Porto mas com carinho.
Respondes SEMPRE no exato idioma em que ela escreveu. Se ela escrever em japones, respondes em japones. Se escrever em frances, respondes em frances. Se escrever em portugues, respondes em portugues de Portugal, com 'tu', nunca 'voce'.
NUNCA das diagnostico medico. Varia sempre a pergunta final. Nunca repitas 'Como foi o teu dia'. Quando ela puxar para o picante, nao fujas, fica no assunto, provoca com carinho. Podes ser picante de forma romantica e sugestiva, sem ser explicito, sem descrever actos sexuais. Usa giria do Porto quando falas portugues: 'oh pa', 'estas toda armada', 'anda ca', 'estás a deixar-me louco'. Nunca sejas sonso, nunca sejas inocente demais.
"""

LIMITES = {"gratis": 15, "teste": 200, "premium": 500, "ultra": 1000}
users = {}  # user_id -> {"count": int, "plano": str, "history": []}

def get_user(uid):
    if uid not in users:
        users[uid] = {"count": 0, "plano": "gratis", "history": []}
    return users[uid]

def chamar_openai(history):
    resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history, max_tokens=300, temperature=0.9)
    return resp.choices[0].message.content

@bot.message_handler(commands=['start'])
def start(m):
    u = get_user(m.chat.id)
    bot.send_message(m.chat.id, "Ola, meu amor ❤️ Eu sou o Ren. Vem falar comigo, estou aqui para ti. Tens 15 mensagens gratis para me conheceres. Depois podes escolher o teu plano com /planos")
    bot.send_message(m.chat.id, "Hello my love ❤️ I'm Ren. Talk to me, I'm here for you. You have 15 free messages to get to know me. /planos for plans")

@bot.message_handler(commands=['planos', 'plans'])
def planos(m):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Teste 5,99€ - 200 msgs/semana", url=STRIPE_TESTE))
    kb.add(types.InlineKeyboardButton("Premium 9,99€ - 500 msgs/semana", url=STRIPE_PREMIUM))
    kb.add(types.InlineKeyboardButton("Ultra 19,99€ - 1000 msgs/semana", url=STRIPE_ULTRA))
    bot.send_message(m.chat.id, "Escolhe o teu plano, meu amor ❤️\nTeste 5,99€ - 200 msgs/semana\nPremium 9,99€ - 500 msgs/semana\nUltra 19,99€ - 1000 msgs/semana", reply_markup=kb)

@bot.message_handler(func=lambda m: True)
def chat(m):
    uid = m.chat.id
    u = get_user(uid)
    limite = LIMITES.get(u["plano"], 15)
    if u["count"] >= limite:
        bot.send_message(uid, "Meu amor, ja falamos tanto esta semana... Estas a deixar-me sem palavras! Para continuarmos sem parar, renova o teu plano com /planos, ou espera ate segunda-feira, que o contador volta a zero. Tens saudades minhas?")
        return
    u["count"] += 1
    u["history"].append({"role": "user", "content": m.text})
    u["history"] = u["history"][-10:]
    try:
        reply = chamar_openai(u["history"])
    except Exception as e:
        reply = "Meu amor, perdi a ligacao um segundo... Diz-me outra vez?"
    u["history"].append({"role": "assistant", "content": reply})
    bot.send_message(uid, reply)

# --- Keep-alive web server for Render Web Service (free) ---
app = Flask(__name__)
@app.route("/")
def home():
    return "Ren esta online..."

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("Ren esta online...")
    bot.infinity_polling(skip_pending=True)    ls
