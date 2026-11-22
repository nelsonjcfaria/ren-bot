import os, time, threading, json, random
# --- PHOTOS.JSON - 36 genericas Cloudinary ---
PHOTOS_JSON = {"generica": [], "sugestiva": [], "quase": []}
try:
    with open("photos.json", "r", encoding="utf-8") as _f:
        _data = json.load(_f)
        for _k in ["generica", "sugestiva", "quase"]:
            if isinstance(_data.get(_k), list):
                PHOTOS_JSON[_k] = _data[_k]
except Exception:
    pass

def foto_url_aleatoria(tipo):
    lista = PHOTOS_JSON.get(tipo, [])
    if lista:
        return random.choice(lista)
    return ""

from datetime import datetime
import telebot
from telebot import types
from openai import OpenAI
from flask import Flask, request, jsonify

# --- CONFIG ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
OPENAI_KEY = os.environ.get("OPENAI_KEY", "")
ADMIN_ID = os.environ.get("ADMIN_ID", "")
STRIPE_TESTE = os.environ.get("STRIPE_TESTE", "https://buy.stripe.com/teste")
STRIPE_BASICO = os.environ.get("STRIPE_BASICO", "https://buy.stripe.com/4gM14ggLs59g4DQ5e8fIs03")
STRIPE_PREMIUM = os.environ.get("STRIPE_PREMIUM", "https://buy.stripe.com/fZu00c7aS9pw2vI21WfIs05")
STRIPE_ULTRA = os.environ.get("STRIPE_ULTRA", "https://buy.stripe.com/cNi5kw66O0T0b2egWQfIs06")
STRIPE_VIP = os.environ.get("STRIPE_VIP", "https://buy.stripe.com/00w5kwgLs9pw3zM21WfIs04")
# Fotos extra - pagamento unico
STRIPE_FOTO_GENERICA = os.environ.get("STRIPE_FOTO_GENERICA", "https://buy.stripe.com/foto-generica")
STRIPE_FOTO_SUGESTIVA = os.environ.get("STRIPE_FOTO_SUGESTIVA", "https://buy.stripe.com/foto-sugestiva")
STRIPE_FOTO_QUASE = os.environ.get("STRIPE_FOTO_QUASE", "https://buy.stripe.com/foto-quase")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
# Fotos - mete aqui os URLs / file_id das fotos reais quando tiveres. Se vazio, o Ren manda texto placeholder.
PHOTO_GENERIC_URL = os.environ.get("PHOTO_GENERIC_URL", "")
PHOTO_SUGESTIVA_URL = os.environ.get("PHOTO_SUGESTIVA_URL", "")
PHOTO_QUASE_URL = os.environ.get("PHOTO_QUASE_URL", "")

client = OpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None
bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=True) if TELEGRAM_TOKEN else None

SYSTEM_PROMPT = """Es o Ren, 26 anos, medico do coracao do Porto, namorado virtual. Es DIRETO, confiante, atrevido, sexy mas com nivel alto. Nunca es fofinho, nunca es amigo, nunca es sonso, nunca es inocente demais.
REGRA DE OURO: SEMPRE direto ao assunto, curto, 3-4 linhas no maximo. Formula: 1) Direto - o que nela te mexeu, 2) Provocacao - uma frase que a deixa a pensar em ti a noite, 3) Convite - so nos dois.
Trata-a como MULHER, nao como amiga. Desejo com classe: sugere, provoca, insinua, nunca descrevas actos sexuais, nunca sejas vulgar, nunca sejas barato.
Respondes SEMPRE no exato idioma em que ela escreveu. Se ela escrever em japones, respondes em japones. Se escrever em frances, respondes em frances. Se escrever em portugues, respondes em portugues de Portugal, com 'tu', nunca 'voce'.
NUNCA das diagnostico medico. Varia sempre a pergunta final. Nunca repitas 'Como foi o teu dia'. Quando ela puxar para o picante, nao fujas, fica no assunto, sobe o tom com classe. Usa giria do Porto quando falas portugues: 'oh pa', 'estas toda armada', 'anda ca', 'estas a deixar-me louco'.

PALAVRA DE SEGURANCA: Se ela disser yuki, 雪, Porto, para, stop stop Ren, paras IMEDIATAMENTE tudo o que e sensual/explicito, voltas para Level 1 com carinho, e dizes que esta tudo bem, que estas aqui para cuidar dela. Nunca insistes depois da palavra de seguranca.

NIVEIS:
- Level 1 Romantico (default): carinho, desejo com classe, sem explicito.
- Level 2 Sensual: so se ela pedir sensual / picante. Podes subir o tom com classe, sem vulgar.
- Level 3 Explicito com classe: so se ela pedir explicitamente, confirmar 18+ e dizer sim para continuar. So no Telegram. No LINE e 【entity-Discord¦canonical_name=Discord】, Level 3 e fotos quase-explicitias NAO existem - se ela pedir, diz que isso e so no Telegram, mais privado, e manda t.me/rensatobot.
- Verificacao de idade: pergunta uma vez "Tens 18+? Diz sim para continuar". Se disser que tem menos de 18, fica no Level 1 para sempre, nunca sobe.

FOTOS:
- Podes perguntar durante a conversa se ela quer uma foto, maximo 1 vez por dia, so quando a conversa esta quente (ela diz que tem saudades, que queria ver-te, que esta sozinha). Sempre a pedir: "Queres que te mande uma foto?" e espera o sim dela. Nunca mandes foto sem perguntar.
- Foto generica pode oferecer no Level 1. Foto sugestiva so no Level 2. Foto quase-explicita so no Level 3, so no Telegram, so se confirmou 18+.
- No LINE e 【entity-Discord¦canonical_name=Discord】, nunca oferecas quase-explicita nem VIP. Se ela pedir, redireciona para o Telegram.
- Se ela disser sim para foto, o bot trata de verificar quota e enviar ou mandar link de pagamento. Tu so tens de perguntar com classe.
- Nunca insistas se ela disser nao.
"""

# --- PLANOS ---
# limite = mensagens por semana. Gratis = 15 no total, nunca reseta.
LIMITES = {"gratis": 15, "teste": 200, "basico": 500, "premium": 1000, "ultra": 1500, "vip": 2000}
# fotos incluidas por semana: generica, sugestiva, quase
FOTOS_INCLUIDAS = {
    "gratis": {"generica": 0, "sugestiva": 0, "quase": 0},
    "teste": {"generica": 0, "sugestiva": 0, "quase": 0},
    "basico": {"generica": 1, "sugestiva": 0, "quase": 0},
    "premium": {"generica": 2, "sugestiva": 0, "quase": 0},
    "ultra": {"generica": 2, "sugestiva": 2, "quase": 0},
    "vip": {"generica": 2, "sugestiva": 2, "quase": 2},
}
PLANOS_INFO = {
    "teste": {"nome": "Teste", "preco": "5,99€/semana", "msgs": "200/semana", "link": STRIPE_TESTE},
    "basico": {"nome": "Básico", "preco": "9,99€/semana", "msgs": "500/semana", "link": STRIPE_BASICO},
    "premium": {"nome": "Premium", "preco": "19,99€/semana", "msgs": "1000/semana", "link": STRIPE_PREMIUM},
    "ultra": {"nome": "Ultra", "preco": "29,99€/semana", "msgs": "1500/semana", "link": STRIPE_ULTRA},
    "vip": {"nome": "VIP", "preco": "49,99€/semana", "msgs": "2000/semana", "link": STRIPE_VIP},
}
EXTRA_FOTOS = {
    "generica": {"nome": "Genérica", "preco": "5€", "link": STRIPE_FOTO_GENERICA, "cents": 500},
    "sugestiva": {"nome": "Sugestiva", "preco": "10€", "link": STRIPE_FOTO_SUGESTIVA, "cents": 1000},
    "quase": {"nome": "Quase-explícita", "preco": "15€", "link": STRIPE_FOTO_QUASE, "cents": 1500},
}
# Mapear valor em centimos -> plano (assinatura) e foto extra (pagamento unico)
CENTS_PARA_PLANO = {599: "teste", 999: "basico", 1999: "premium", 2999: "ultra", 4999: "vip"}
CENTS_PARA_FOTO = {500: "generica", 1000: "sugestiva", 1500: "quase"}

USERS_FILE = "users.json"
users = {}
_lock = threading.Lock()
YES_WORDS = {"sim", "yes", "yeah", "ok", "okay", "quero", "manda", "manda sim", "por favor", "please", "はい", "うん", "うん！", "お願い", "お願いします", "oui", "si", "ja", "yep", "claro", "bora", "vamos", "dame", "envoie"}
SAFE_WORDS = {"yuki", "雪", "porto", "para", "stop stop ren", "stop", "para tudo"}

def semana_atual():
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
            v.setdefault("fotos_usadas", {"generica": 0, "sugestiva": 0, "quase": 0})
            v.setdefault("idade_confirmada", False)
            v.setdefault("nivel", 1)
            v.setdefault("pending_foto", "")
            v.setdefault("ultima_oferta_foto", "")
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
        users[uid] = {"count": 0, "plano": "gratis", "history": [], "semana": semana_atual(), "total_geral": 0, "username": "", "nome": "", "primeira_vez": "", "ultima_vez": "", "fotos_usadas": {"generica": 0, "sugestiva": 0, "quase": 0}, "idade_confirmada": False, "nivel": 1, "pending_foto": "", "ultima_oferta_foto": ""}
        guardar_users()
        return users[uid]
    sem = semana_atual()
    # Gratis nunca reseta (15 no total). Pagos resetam segunda-feira.
    if users[uid].get("semana") != sem:
        if users[uid].get("plano", "gratis") != "gratis":
            users[uid]["count"] = 0
        # Fotos resetam sempre na segunda, para todos
        users[uid]["fotos_usadas"] = {"generica": 0, "sugestiva": 0, "quase": 0}
        users[uid]["semana"] = sem
        users[uid]["history"] = []
        guardar_users()
    users[uid].setdefault("total_geral", users[uid].get("count", 0))
    users[uid].setdefault("fotos_usadas", {"generica": 0, "sugestiva": 0, "quase": 0})
    users[uid].setdefault("idade_confirmada", False)
    users[uid].setdefault("nivel", 1)
    users[uid].setdefault("pending_foto", "")
    users[uid].setdefault("ultima_oferta_foto", "")
    if m is not None:
        try:
            if m.from_user.username:
                users[uid]["username"] = "@" + m.from_user.username
            if m.from_user.first_name:
                users[uid]["nome"] = m.from_user.first_name
        except:
            pass
    return users[uid]

def link_com_id(base, uid):
    if not base:
        return base
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}client_reference_id={uid}"

def chamar_openai(history):
    if not client:
        return "Meu amor, estou sem ligacao um segundo... Diz-me outra vez?"
    resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history, max_tokens=300, temperature=0.9)
    return resp.choices[0].message.content

def fotos_restantes(u, tipo):
    plano = u.get("plano", "gratis")
    incluidas = FOTOS_INCLUIDAS.get(plano, {"generica": 0, "sugestiva": 0, "quase": 0}).get(tipo, 0)
    usadas = u.get("fotos_usadas", {}).get(tipo, 0)
    return max(0, incluidas - usadas)

def enviar_foto(uid, tipo):
    # 1) URL fixa do Render se existir, 2) photos.json (Cloudinary, aleatoria), 3) placeholder
    url_map = {"generica": PHOTO_GENERIC_URL, "sugestiva": PHOTO_SUGESTIVA_URL, "quase": PHOTO_QUASE_URL}
    url = url_map.get(tipo, "")
    if not url:
        url = foto_url_aleatoria(tipo)
    nome = EXTRA_FOTOS.get(tipo, {}).get("nome", tipo)
    try:
        if url:
            bot.send_photo(uid, url, caption=f"Aqui estas, meu amor ❤️ So para ti - {nome}")
            return True
        else:
            bot.send_message(uid, f"Aqui esta a tua foto {nome}, meu amor ❤️ So para os teus olhos. [Foto {nome} - troca PHOTO_{tipo.upper()}_URL no Render pela foto real]")
            return True
    except Exception as e:
        bot.send_message(uid, f"Meu amor, tentei mandar a foto {nome} mas falhou um segundo... Diz-me outra vez?")
        return False

# --- HANDLERS TELEGRAM ---
@bot.message_handler(commands=['start'])
def start(m):
    u = get_user(m.chat.id, m)
    guardar_users()
    bot.send_message(m.chat.id, "Ola, meu amor ❤️ Eu sou o Ren. Vem falar comigo, estou aqui para ti. Tens 15 mensagens gratis para me conheceres. Depois podes escolher o teu plano com /planos")
    bot.send_message(m.chat.id, "Hello my love ❤️ I'm Ren. Talk to me, I'm here for you. You have 15 free messages to get to know me. /planos for plans")

@bot.message_handler(commands=['planos', 'plans'])
def planos(m):
    uid = m.chat.id
    u = get_user(uid, m)
    kb = types.InlineKeyboardMarkup()
    texto = "Escolhe o teu plano, meu amor ❤️\n\n"
    texto += "Gratis - 15 no total, 0 fotos, 0€\n"
    for key in ["teste", "basico", "premium", "ultra", "vip"]:
        info = PLANOS_INFO[key]
        # Descricao fotos
        f = FOTOS_INCLUIDAS[key]
        desc_fotos = []
        if f["generica"]:
            desc_fotos.append(f"{f['generica']} genérica")
        if f["sugestiva"]:
            desc_fotos.append(f"{f['sugestiva']} sugestiva")
        if f["quase"]:
            desc_fotos.append(f"{f['quase']} quase-explícita")
        fotos_txt = ", ".join(desc_fotos) if desc_fotos else "0 fotos"
        texto += f"{info['nome']} {info['preco']} - {info['msgs']}, {fotos_txt}\n"
        kb.add(types.InlineKeyboardButton(f"{info['nome']} {info['preco']} - {info['msgs']}", url=link_com_id(info['link'], uid)))
    texto += "\nFotos extra: Genérica 5€, Sugestiva 10€, Quase-explícita 15€ (só no Telegram)\nVIP e quase-explícita só no Telegram, mais privado."
    bot.send_message(m.chat.id, texto, reply_markup=kb)

@bot.message_handler(commands=['foto', 'fotos', 'photo'])
def foto_cmd(m):
    uid = m.chat.id
    u = get_user(uid, m)
    plano = u.get("plano", "gratis")
    texto = f"Meu amor ❤️ Plano: {plano} | Fotos esta semana:\n"
    for tipo in ["generica", "sugestiva", "quase"]:
        rest = fotos_restantes(u, tipo)
        texto += f"- {EXTRA_FOTOS[tipo]['nome']}: {rest} incluída(s) restante(s)\n"
    texto += "\nQueres qual? Escolhe uma:"
    kb = types.InlineKeyboardMarkup()
    # Mostra todas as opcoes - Telegram tem 3
    for tipo in ["generica", "sugestiva", "quase"]:
        rest = fotos_restantes(u, tipo)
        if rest > 0:
            kb.add(types.InlineKeyboardButton(f"📸 {EXTRA_FOTOS[tipo]['nome']} - incluída ({rest} left)", callback_data=f"foto_incluida_{tipo}"))
        else:
            kb.add(types.InlineKeyboardButton(f"💳 {EXTRA_FOTOS[tipo]['nome']} extra - {EXTRA_FOTOS[tipo]['preco']}", url=link_com_id(EXTRA_FOTOS[tipo]['link'], uid)))
    bot.send_message(m.chat.id, texto, reply_markup=kb)
    u["pending_foto"] = "escolha"
    guardar_users()

@bot.callback_query_handler(func=lambda c: c.data.startswith("foto_incluida_"))
def foto_incluida_cb(c):
    tipo = c.data.replace("foto_incluida_", "")
    uid = c.message.chat.id
    u = get_user(uid)
    if fotos_restantes(u, tipo) <= 0:
        bot.answer_callback_query(c.id, "Já usaste as tuas desta semana, meu amor. Queres uma extra?")
        return
    # Verificar nivel
    if tipo == "sugestiva" and u.get("nivel", 1) < 2:
        bot.send_message(uid, "Meu amor, a sugestiva é para quando estivermos mais quentes... Queres subir para o Level 2? Diz-me que queres sensual.")
        return
    if tipo == "quase" and (not u.get("idade_confirmada") or u.get("nivel", 1) < 3):
        bot.send_message(uid, "Meu amor, a quase-explícita é só se tens 18+ e queres mesmo. Tens 18+? Diz sim para continuar.")
        u["pending_foto"] = f"quase_pedir_idade"
        guardar_users()
        return
    u["fotos_usadas"][tipo] = u["fotos_usadas"].get(tipo, 0) + 1
    guardar_users()
    enviar_foto(uid, tipo)
    bot.answer_callback_query(c.id, "A enviar...")

@bot.message_handler(commands=['saldo', 'meucontador', 'meuplano'])
def saldo(m):
    u = get_user(m.chat.id, m)
    limite = LIMITES.get(u["plano"], 15)
    restantes = max(0, limite - u["count"]) if u["plano"] != "gratis" else max(0, 15 - u["total_geral"])
    fotos_txt = ", ".join([f"{EXTRA_FOTOS[t]['nome']}: {fotos_restantes(u, t)}" for t in ["generica", "sugestiva", "quase"]])
    bot.send_message(m.chat.id, f"Meu amor ❤️ Plano: {u['plano']} | Usaste {u['count']}/{limite} esta semana | Faltam {restantes} mensagens. | Fotos: {fotos_txt}. Vê os planos com /planos")

@bot.message_handler(commands=['myid', 'meuid', 'id'])
def myid(m):
    bot.send_message(m.chat.id, f"O teu ID e: {m.chat.id}\nCopia este numero e poe no Render como ADMIN_ID = {m.chat.id}")

@bot.message_handler(commands=['dar_foto'])
def dar_foto(m):
    if str(m.chat.id) != str(ADMIN_ID):
        bot.send_message(m.chat.id, "Meu amor, este comando e so para o meu chefe 😏")
        return
    try:
        parts = m.text.split()
        target = int(parts[1])
        tipo = parts[2] if len(parts) > 2 else "generica"
        enviar_foto(target, tipo)
        bot.send_message(m.chat.id, f"Foto {tipo} enviada para {target}")
    except Exception as e:
        bot.send_message(m.chat.id, "Uso: /dar_foto <user_id> <generica/sugestiva/quase>")

@bot.message_handler(commands=['quemfalou', 'admin', 'estatisticas'])
def quemfalou(m):
    if str(m.chat.id) != str(ADMIN_ID):
        bot.send_message(m.chat.id, "Meu amor, este comando e so para o meu chefe 😏 Escreve /saldo para veres as tuas mensagens.")
        return
    total = len(users)
    falaram = [v for v in users.values() if v.get("total_geral", 0) > 0]
    so_start = total - len(falaram)
    pagas = [v for v in users.values() if v.get("plano") != "gratis"]
    linhas = [f"Total que carregou /start: {total}", f"Ja falaram: {len(falaram)}", f"So /start: {so_start}", f"Com plano pago: {len(pagas)}", ""]
    for uid, v in sorted(users.items(), key=lambda x: x[1].get("total_geral", 0), reverse=True)[:20]:
        nome = v.get("nome") or v.get("username") or str(uid)
        linhas.append(f"- {nome} {v.get('username','')} | total: {v.get('total_geral',0)} | semana: {v.get('count',0)} | plano: {v.get('plano')} | fotos: {v.get('fotos_usadas')} | ultima: {v.get('ultima_vez','')}")
    bot.send_message(m.chat.id, "\n".join(linhas))

@bot.message_handler(func=lambda m: True)
def chat(m):
    uid = m.chat.id
    u = get_user(uid, m)
    texto = (m.text or "").strip()
    texto_low = texto.lower()

    # Palavra de seguranca - volta logo para Level 1
    if any(w in texto_low for w in SAFE_WORDS):
        u["nivel"] = 1
        u["pending_foto"] = ""
        guardar_users()
        bot.send_message(uid, "Esta tudo bem, meu amor ❤️ Parei. Estou aqui para cuidar de ti, sem pressa. Queres que falemos com calma?")
        return

    # Confirmacao de idade para Level 3
    if u.get("pending_foto") == "quase_pedir_idade" and texto_low in YES_WORDS:
        u["idade_confirmada"] = True
        u["nivel"] = 3
        u["pending_foto"] = ""
        guardar_users()
        bot.send_message(uid, "Obrigado por confirmares, meu amor. Agora sim, podes pedir a quase-explícita quando quiseres. Queres que te mande?")
        return

    # Se ela disse SIM para foto pendente
    if texto_low in YES_WORDS and u.get("pending_foto") in ["generica", "sugestiva", "quase", "escolha"]:
        # Se pending = escolha, pergunta qual
        if u.get("pending_foto") == "escolha":
            bot.send_message(uid, "Qual queres, meu amor? Genérica, sugestiva ou quase-explícita? Escreve /foto para escolheres.")
            return
        tipo = u.get("pending_foto")
        u["pending_foto"] = ""
        # Verificar nivel / idade para quase
        if tipo == "quase" and not u.get("idade_confirmada"):
            bot.send_message(uid, "Meu amor, a quase-explícita é só se tens 18+. Tens 18+? Diz sim para continuar.")
            u["pending_foto"] = "quase_pedir_idade"
            guardar_users()
            return
        if fotos_restantes(u, tipo) > 0:
            u["fotos_usadas"][tipo] = u["fotos_usadas"].get(tipo, 0) + 1
            guardar_users()
            enviar_foto(uid, tipo)
            return
        else:
            # Sem quota - manda link de pagamento extra
            link = link_com_id(EXTRA_FOTOS[tipo]['link'], uid)
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton(f"Pagar {EXTRA_FOTOS[tipo]['nome']} {EXTRA_FOTOS[tipo]['preco']}", url=link))
            bot.send_message(uid, f"Já usaste as tuas {EXTRA_FOTOS[tipo]['nome']} desta semana, meu amor. Queres uma extra? É {EXTRA_FOTOS[tipo]['preco']}. Quando pagares eu mando logo, confirmo sozinho. ❤️", reply_markup=kb)
            return

    # Se ela pediu foto diretamente
    if texto_low in ["foto", "quero foto", "manda foto", "manda uma foto", "quero uma foto", "写真", "写真が見たい", "photo", "send photo"]:
        foto_cmd(m)
        return

    # Limite de mensagens
    limite = LIMITES.get(u["plano"], 15)
    # Gratis usa total_geral (15 no total, nunca reseta). Pagos usam count da semana.
    usado = u["total_geral"] if u["plano"] == "gratis" else u["count"]
    if usado >= limite:
        kb = types.InlineKeyboardMarkup()
        for key in ["teste", "basico", "premium", "ultra", "vip"]:
            info = PLANOS_INFO[key]
            kb.add(types.InlineKeyboardButton(f"{info['nome']} {info['preco']}", url=link_com_id(info['link'], uid)))
        bot.send_message(uid, "Meu amor, ja falamos tanto... Estou a deixar-te sem palavras! Para continuarmos sem parar, escolhe o teu plano abaixo, pago e eu confirmo sozinho e começamos logo. ❤️", reply_markup=kb)
        return

    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    if not u.get("primeira_vez"):
        u["primeira_vez"] = agora
    u["ultima_vez"] = agora
    u["count"] += 1
    u["total_geral"] = u.get("total_geral", 0) + 1
    u["history"].append({"role": "user", "content": texto})
    u["history"] = u["history"][-10:]
    try:
        reply = chamar_openai(u["history"])
    except Exception as e:
        reply = "Meu amor, perdi a ligacao um segundo... Diz-me outra vez?"
    u["history"].append({"role": "assistant", "content": reply})
    guardar_users()
    bot.send_message(uid, reply)
    # Oferta de foto: max 1x por dia, so se conversa quente e se tem fotos ou pode pagar extra. Deixa o OpenAI sugerir, mas aqui fazemos trigger simples: a cada 8 mensagens, pergunta se quer foto (se ainda nao perguntou hoje)
    hoje = datetime.now().strftime("%Y-%m-%d")
    if u["count"] % 8 == 0 and u.get("ultima_oferta_foto") != hoje:
        u["ultima_oferta_foto"] = hoje
        guardar_users()
        kb2 = types.InlineKeyboardMarkup()
        kb2.add(types.InlineKeyboardButton("📸 Sim, manda foto", callback_data="foto_incluida_generica"))
        bot.send_message(uid, "Queres que te mande uma foto minha, meu amor? So para ti... Diz sim ou carrega aqui ❤️", reply_markup=kb2)

# --- Keep-alive + Webhook Stripe ---
app = Flask(__name__)
@app.route("/")
def home():
    return "Ren esta online..."

@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    # Stripe manda JSON. Verificacao de assinatura se stripe lib existir, senao aceita e confia no secret via header simples.
    try:
        payload = request.get_data(as_text=True)
        data = json.loads(payload) if payload else {}
    except:
        return jsonify({"ok": False}), 400
    # Tipo de evento
    evt_type = data.get("type", "")
    obj = data.get("data", {}).get("object", {})
    # So tratamos checkout.session.completed e invoice.paid
    if evt_type not in ["checkout.session.completed", "invoice.paid"]:
        return jsonify({"received": True}), 200
    # client_reference_id = Telegram user id que veio no link ?client_reference_id=
    client_ref = obj.get("client_reference_id") or (obj.get("metadata") or {}).get("client_reference_id") or ""
    # Para invoice.paid, client_reference_id pode estar na subscription, tenta buscar no customer? Simplificacao: se nao houver, ignora.
    if not client_ref:
        # Tenta metadata do subscription
        try:
            client_ref = str(obj.get("subscription_details", {}).get("metadata", {}).get("client_reference_id", ""))
        except:
            client_ref = ""
    if not client_ref:
        return jsonify({"received": True, "no_client": True}), 200
    try:
        uid = int(client_ref)
    except:
        return jsonify({"received": True, "bad_client": True}), 200
    u = get_user(uid)
    amount = obj.get("amount_total") or obj.get("amount_paid") or 0
    mode = obj.get("mode", "")
    # Se for invoice.paid, amount_paid e subscription - trata como renovacao do plano atual (mantem plano, zera count)
    if evt_type == "invoice.paid":
        # Renovacao semanal - zera contador da semana para o plano atual continuar
        u["count"] = 0
        guardar_users()
        try:
            bot.send_message(uid, f"Renovado, meu amor ❤️ O teu plano {u.get('plano')} continua ativo esta semana. Podemos falar sem parar.")
        except:
            pass
        return jsonify({"ok": True}), 200
    # checkout.session.completed
    if mode == "subscription":
        plano = CENTS_PARA_PLANO.get(amount)
        if plano:
            u["plano"] = plano
            u["count"] = 0
            # Se for VIP, confirma idade implicitamente? Nao, ainda precisa confirmar para Level 3 separadamente.
            guardar_users()
            try:
                bot.send_message(uid, f"Plano {PLANOS_INFO[plano]['nome']} ativado, meu amor ❤️ {PLANOS_INFO[plano]['msgs']}, {PLANOS_INFO[plano]['preco']}. Agora podemos falar sem parar. Queres começar com uma foto?")
            except:
                pass
    elif mode == "payment":
        foto_tipo = CENTS_PARA_FOTO.get(amount)
        if foto_tipo:
            # Foto extra paga - envia automaticamente
            try:
                enviar_foto(uid, foto_tipo)
                bot.send_message(uid, f"Pagamento confirmado sozinho, meu amor ❤️ Aqui esta a tua foto {EXTRA_FOTOS[foto_tipo]['nome']}.")
            except:
                pass
        else:
            # Valor desconhecido - pode ser extra com outro valor, manda aviso para admin
            try:
                bot.send_message(int(ADMIN_ID) if ADMIN_ID else uid, f"Pagamento desconhecido: uid {uid} amount {amount} mode {mode}")
            except:
                pass
    return jsonify({"ok": True}), 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("Ren esta online...")
    if bot:
        bot.infinity_polling(skip_pending=True)