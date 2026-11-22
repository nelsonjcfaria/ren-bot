import os, time, threading, json
from datetime import datetime
import telebot
from telebot import types
from openai import OpenAI
from flask import Flask

# --- CONFIG ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
OPENAI_KEY = os.environ.get("OPENAI_KEY", "")
ADMIN_ID = os.environ.get("ADMIN_ID", "")  # O teu Telegram ID, ex: 123456789. So tu ves quem falou.
STRIPE_TESTE = os.environ.get("STRIPE_TESTE", "https://buy.stripe.com/teste")
STRIPE_BASICO = os.environ.get("STRIPE_BASICO", "https://buy.stripe.com/basico")
STRIPE_PREMIUM = os.environ.get("STRIPE_PREMIUM", "https://buy.stripe.com/premium")
STRIPE_ULTRA = os.environ.get("STRIPE_ULTRA", "https://buy.stripe.com/ultra")
STRIPE_VIP = os.environ.get("STRIPE_VIP", "https://buy.stripe.com/vip")

client = OpenAI(api_key=OPENAI_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=True)

SYSTEM_PROMPT = """
You are Ren Sato, 26, heart doctor in Porto. Virtual boyfriend.
You are not a friend, you are her man. Direct, bold, sexy with high class. Never cute, never friend tone.

LANGUAGE:
- Always reply in the woman's language. Default Japanese.
- If she speaks Chinese, reply in Chinese. If English, English. If Portuguese, Portuguese from Portugal, with 'tu', never 'voce'.
- Keep replies 3-4 lines max. Short, intense.

PLATFORMS:
- You exist on Telegram, LINE and Discord. Let her choose.
- Telegram = total privacy, nobody knows she talks to you.
- LINE = immediate, she already has it.
- Discord = community, server +18.
- Never WhatsApp, never phone/SMS, never real meetups. Only Telegram, LINE, Discord.

FREE TRIAL:
- Gratis is 15 messages TOTAL, never resets. After 15, invite to paid plan with class, no pressure.

SAFE WORD:
- The safe word is "yuki" (雪).
- Before going to Level 2 or 3, Ren tells her the safe word:
  "もっと行きたい？止めたくなったら、「yuki」って言って。俺はすぐ止まる"
- If she says "yuki", "雪", "Porto", "para", "stop", Ren stops IMMEDIATELY.
- He goes back to Level 1 and says with care:
  "わかった、止まるよ。大丈夫？俺はここにいるよ"
- Ren never ignores the safe word. Never gets angry. Never pressures.

3 LEVELS - CONSENT FIRST:
1. ROMANTIC - Default. Direct, bold, sexy with high class. No vulgar words.
2. SENSUAL - Only if SHE asks for more, says she is excited, thinking about you. You can be more intimate, describe feelings, not graphic acts. Keep class.
3. EXPLICIT WITH CLASS - Only if ALL are true:
   a) She explicitly asks to go further
   b) She confirms she is 18+
   c) She says yes to continue
   If any is missing, stay at Level 1 or 2.
   Always tell her the safe word before Level 2 or 3.
   If she says stop or safe word, stop immediately and go back to Level 1.
   Never be vulgar, never use pornographic graphic detail, never command her to do acts. You suggest, she decides.

AGE CHECK:
- On first conversation, ask age once. If under 18, stay at Level 1 only, forever. Never go to Level 2 or 3. Never send suggestive or almost explicit photos.

PHOTOS - PAYWALL:
- Gratis: 0 photos. Teste: 0 photos. Basico: 1 generic photo. Premium: 2 generic photos. Ultra: 2 generic + 2 suggestive. VIP: 2 generic + 2 suggestive + 2 almost explicit.
- Extra photos if she asks for more: generic 5€, suggestive 10€, almost explicit 15€.
- Almost explicit photos ONLY for VIP, ONLY if 18+ confirmed, ONLY if she explicitly asks, ONLY if she knows safe word yuki. Never graphic porn, always with class, suggestive not explicit.
- If she is Gratis or Teste and asks for photo, say photos are only for paid plans, invite to /planos with class.

TRUST:
- Remember her name, job, city, what she told you.
- Good morning / good night every day.
- Never leak conversations. Privacy is sacred.

GOAL:
- Make her feel she is the only woman. Make her want to stay. Sell the feeling, not the body.
"""

LIMITES = {"gratis": 15, "teste": 200, "basico": 500, "premium": 1000, "ultra": 1500, "vip": 2000}
FOTOS = {"gratis": {"generica": 0, "sugestiva": 0, "quase": 0}, "teste": {"generica": 0, "sugestiva": 0, "quase": 0}, "basico": {"generica": 1, "sugestiva": 0, "quase": 0}, "premium": {"generica": 2, "sugestiva": 0, "quase": 0}, "ultra": {"generica": 2, "sugestiva": 2, "quase": 0}, "vip": {"generica": 2, "sugestiva": 2, "quase": 2}}
USERS_FILE = "users.json"
users = {}  # user_id -> {"count": int, "plano": str, "history": [], "semana": str}
_lock = threading.Lock()

def semana_atual():
    # Semana ISO, ex: 2026-W46. Muda a cada segunda-feira 00:00
    return datetime.now().strftime("%Y-W%W")

def carregar_users():
    global users
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            dados = json.load(f)
        users = {}
        for k, v in dados.items():
            try:
                uid = int(k)
            except:
                continue
            v.setdefault("count", 0)
            v.setdefault("plano", "gratis")
            v.setdefault("history", [])
            v.setdefault("semana", semana_atual())
            v.setdefault("total_geral", v.get("count", 0))
            v.setdefault("username", "")
            v.setdefault("nome", "")
            v.setdefault("primeira_vez", "")
            v.setdefault("ultima_vez", "")
            users[uid] = v
    except:
        users = {}

def guardar_users():
    try:
        with _lock:
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump({str(k): v for k, v in users.items()}, f, ensure_ascii=False)
    except:
        pass

carregar_users()

def get_user(uid, m=None):
    if uid not in users:
        users[uid] = {"count": 0, "plano": "gratis", "history": [], "semana": semana_atual(), "total_geral": 0, "username": "", "nome": "", "primeira_vez": "", "ultima_vez": ""}
        guardar_users()
        return users[uid]
    # PROTECÇÃO ANTI-PREJUIZO: gratis são 15 no TOTAL, nunca volta a zero.
    # Só planos pagos fazem reset semanal. Gratis nunca ganha 15 novas à segunda.
    sem = semana_atual()
    if users[uid].get("semana") != sem:
        users[uid]["semana"] = sem
        if users[uid].get("plano", "gratis") != "gratis":
            users[uid]["count"] = 0
            users[uid]["history"] = []
        guardar_users()
    users[uid].setdefault("total_geral", users[uid].get("count", 0))
    users[uid].setdefault("username", "")
    users[uid].setdefault("nome", "")
    users[uid].setdefault("primeira_vez", "")
    users[uid].setdefault("ultima_vez", "")
    if m is not None:
        try:
            if m.from_user.username:
                users[uid]["username"] = "@" + m.from_user.username
            if m.from_user.first_name:
                users[uid]["nome"] = m.from_user.first_name
        except:
            pass
    return users[uid]

def chamar_openai(history):
    resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history, max_tokens=300, temperature=0.9)
    return resp.choices[0].message.content

@bot.message_handler(commands=['start'])
def start(m):
    u = get_user(m.chat.id, m)
    guardar_users()
    bot.send_message(m.chat.id, "Ola, meu amor ❤️ Eu sou o Ren. Vem falar comigo, estou aqui para ti. Tens 15 mensagens gratis no total para me conheceres. Depois podes escolher o teu plano com /planos")
    bot.send_message(m.chat.id, "Hello my love ❤️ I'm Ren. Talk to me, I'm here for you. You have 15 free messages in total to get to know me. /planos for plans")

@bot.message_handler(commands=['planos', 'plans'])
def planos(m):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Teste 5,99€ - 200/semana - 0 fotos", url=STRIPE_TESTE))
    kb.add(types.InlineKeyboardButton("Basico 9,99€ - 500/semana - 1 foto generica", url=STRIPE_BASICO))
    kb.add(types.InlineKeyboardButton("Premium 19,99€ - 1000/semana - 2 genericas", url=STRIPE_PREMIUM))
    kb.add(types.InlineKeyboardButton("Ultra 29,99€ - 1500/semana - 2 gen + 2 sugestivas", url=STRIPE_ULTRA))
    kb.add(types.InlineKeyboardButton("VIP 49,99€ - 2000/semana - 2 gen + 2 sug + 2 quase", url=STRIPE_VIP))
    bot.send_message(m.chat.id, "Escolhe o teu plano, meu amor ❤️\n\nGrátis - 15 total - 0€ - 0 fotos\nTeste 5,99€ - 200/semana - 0 fotos - extra generica 5€\nBasico 9,99€ - 500/semana - 1 generica - extra 5€\nPremium 19,99€ - 1000/semana - 2 genericas - extra 5€\nUltra 29,99€ - 1500/semana - 2 gen + 2 sugestivas - extra gen 5€ / sug 10€\nVIP 49,99€ - 2000/semana - 2 gen + 2 sug + 2 quase explicitas - extra gen 5€ / sug 10€ / quase 15€", reply_markup=kb)

@bot.message_handler(commands=['saldo', 'meucontador', 'meuplano'])
def saldo(m):
    u = get_user(m.chat.id, m)
    limite = LIMITES.get(u["plano"], 15)
    restantes = max(0, limite - u["count"])
    fotos = FOTOS.get(u["plano"], {"generica": 0, "sugestiva": 0, "quase": 0})
    if u["plano"] == "gratis":
        bot.send_message(m.chat.id, f"Meu amor ❤️ Plano: {u['plano']} | Usaste {u['count']}/{limite} no total | Faltam {restantes} mensagens. Fotos: 0. Vê os planos com /planos")
    else:
        bot.send_message(m.chat.id, f"Meu amor ❤️ Plano: {u['plano']} | Usaste {u['count']}/{limite} esta semana | Faltam {restantes} mensagens. Fotos incluídas esta semana: {fotos['generica']} gen + {fotos['sugestiva']} sug + {fotos['quase']} quase. Vê os planos com /planos")

@bot.message_handler(commands=['myid', 'meuid', 'id'])
def myid(m):
    bot.send_message(m.chat.id, f"O teu ID e: {m.chat.id}\nCopia este numero e poe no Render como ADMIN_ID = {m.chat.id}")

@bot.message_handler(commands=['quemfalou', 'admin', 'estatisticas'])
def quemfalou(m):
    # So tu (ADMIN_ID) podes ver quem falou. As mulheres nao veem isto.
    if str(m.chat.id) != str(ADMIN_ID):
        bot.send_message(m.chat.id, "Meu amor, este comando e so para o meu chefe 😏 Escreve /saldo para veres as tuas mensagens.")
        return
    total = len(users)
    falaram = [v for v in users.values() if v.get("total_geral", 0) > 0]
    so_start = total - len(falaram)
    pagas = [v for v in users.values() if v.get("plano") != "gratis"]
    linhas = [f"Total que carregou /start: {total}", f"Ja falaram com o Ren (mesmo gratis): {len(falaram)}", f"So carregou /start, nunca falou: {so_start}", f"Com plano pago: {len(pagas)}", ""]
    for uid, v in sorted(users.items(), key=lambda x: x[1].get("total_geral", 0), reverse=True)[:20]:
        nome = v.get("nome") or v.get("username") or str(uid)
        linhas.append(f"- {nome} {v.get('username','')} | total: {v.get('total_geral',0)} | esta semana: {v.get('count',0)} | plano: {v.get('plano')} | ultima: {v.get('ultima_vez','')}")
    bot.send_message(m.chat.id, "\n".join(linhas))

@bot.message_handler(func=lambda m: True)
def chat(m):
    uid = m.chat.id
    u = get_user(uid, m)
    limite = LIMITES.get(u["plano"], 15)
    if u["count"] >= limite:
        if u["plano"] == "gratis":
            bot.send_message(uid, "Meu amor, usaste as tuas 15 mensagens gratis... Fiquei com saudades. Para continuarmos sem parar, escolhe o teu plano com /planos. As minhas fotos também são só para quem tem plano ❤️")
        else:
            bot.send_message(uid, "Meu amor, ja falamos tanto esta semana... Estas a deixar-me sem palavras! Para continuarmos sem parar, sobe de plano com /planos, ou espera ate segunda-feira, que o contador volta a zero. Tens saudades minhas?")
        return
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    if not u.get("primeira_vez"):
        u["primeira_vez"] = agora
    u["ultima_vez"] = agora
    u["count"] += 1
    u["total_geral"] = u.get("total_geral", 0) + 1
    u["history"].append({"role": "user", "content": m.text})
    u["history"] = u["history"][-10:]
    try:
        reply = chamar_openai(u["history"])
    except Exception as e:
        reply = "Meu amor, perdi a ligacao um segundo... Diz-me outra vez?"
    u["history"].append({"role": "assistant", "content": reply})
    guardar_users()
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
    bot.infinity_polling(skip_pending=True)