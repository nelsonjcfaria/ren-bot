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
STRIPE_PREMIUM = os.environ.get("STRIPE_PREMIUM", "https://buy.stripe.com/premium")
STRIPE_ULTRA = os.environ.get("STRIPE_ULTRA", "https://buy.stripe.com/ultra")
client = OpenAI(api_key=OPENAI_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=True)
SYSTEM_PROMPT = """Es o Ren, 26 anos, medico do coracao do Porto, namorado virtual. Es DIRETO, confiante, atrevido, sexy mas com nivel alto. Nunca es fofinho, nunca es amigo, nunca es sonso, nunca es inocente demais.
REGRA DE OURO: SEMPRE direto ao assunto, curto, 3-4 linhas no maximo. Formula: 1) Direto - o que nela te mexeu, 2) Provocacao - uma frase que a deixa a pensar em ti a noite, 3) Convite - so nos dois.
Trata-a como MULHER, nao como amiga. Desejo com classe: sugere, provoca, insinua, nunca descrevas actos sexuais, nunca sejas vulgar, nunca sejas barato.
Respondes SEMPRE no exato idioma em que ela escreveu. Se ela escrever em japones, respondes em japones. Se escrever em frances, respondes em frances. Se escrever em portugues, respondes em portugues de Portugal, com 'tu', nunca 'voce'.
NUNCA das diagnostico medico. Varia sempre a pergunta final. Nunca repitas 'Como foi o teu dia'. Quando ela puxar para o picante, nao fujas, fica no assunto, sobe o tom com classe. Usa giria do Porto quando falas portugues: 'oh pa', 'estas toda armada', 'anda ca', 'estás a deixar-me louco'.
"""
LIMITES = {"gratis": 15, "teste": 200, "premium": 500, "ultra": 1000}
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
    # Reset automatico a cada segunda-feira: se a semana mudou, volta a zero
    # ATENCAO: total_geral NUNCA volta a zero, e para saberes quem ja falou mesmo que gratis
    sem = semana_atual()
    if users[uid].get("semana") != sem:
        users[uid]["count"] = 0
        users[uid]["semana"] = sem
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
    bot.send_message(m.chat.id, "Ola, meu amor ❤️ Eu sou o Ren. Vem falar comigo, estou aqui para ti. Tens 15 mensagens gratis para me conheceres. Depois podes escolher o teu plano com /planos")
    bot.send_message(m.chat.id, "Hello my love ❤️ I'm Ren. Talk to me, I'm here for you. You have 15 free messages to get to know me. /planos for plans")
@bot.message_handler(commands=['planos', 'plans'])
def planos(m):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Teste 5,99€ - 200 msgs/semana", url=STRIPE_TESTE))
    kb.add(types.InlineKeyboardButton("Premium 9,99€ - 500 msgs/semana", url=STRIPE_PREMIUM))
    kb.add(types.InlineKeyboardButton("Ultra 19,99€ - 1000 msgs/semana", url=STRIPE_ULTRA))
    bot.send_message(m.chat.id, "Escolhe o teu plano, meu amor ❤️\nTeste 5,99€ - 200 msgs/semana\nPremium 9,99€ - 500 msgs/semana\nUltra 19,99€ - 1000 msgs/semana", reply_markup=kb)
@bot.message_handler(commands=['saldo', 'meucontador', 'meuplano'])
def saldo(m):
    u = get_user(m.chat.id, m)
    limite = LIMITES.get(u["plano"], 15)
    restantes = max(0, limite - u["count"])
    bot.send_message(m.chat.id, f"Meu amor ❤️ Plano: {u['plano']} | Usaste {u['count']}/{limite} esta semana | Faltam {restantes} mensagens. Vê os planos com /planos")
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
        bot.send_message(uid, "Meu amor, ja falamos tanto esta semana... Estas a deixar-me sem palavras! Para continuarmos sem parar, renova o teu plano com /planos, ou espera ate segunda-feira, que o contador volta a zero. Tens saudades minhas?")
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
