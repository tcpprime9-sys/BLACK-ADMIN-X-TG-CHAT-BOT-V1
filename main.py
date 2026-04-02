# main.py
import os
import requests
import datetime
import sqlite3
from zipfile import ZipFile
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# ===================== CONFIG =====================
BOT_TOKEN = "8761903557:AAG6wXAr2nnyoRGvuqiuk07z2odT9wMZc5w"
OWNER_ID = 7090770573
GEMINI_API_KEY = "AIzaSyDVvQsyfZbhLAHAUculChgwLLg5AXPPrqI"
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ===================== DATABASE =====================
conn = sqlite3.connect("users.db")
c = conn.cursor()

# Users table
c.execute("""CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            role TEXT,
            expiry TEXT
            )""")

# Virtual partners table
c.execute("""CREATE TABLE IF NOT EXISTS partners(
            user_id INTEGER PRIMARY KEY,
            partner_name TEXT,
            partner_type TEXT
            )""")

conn.commit()

# ===================== UTILITIES =====================
def add_pro_user(user_id: int, days: int):
    expiry_date = datetime.datetime.now() + datetime.timedelta(days=days)
    c.execute("INSERT OR REPLACE INTO users(user_id, role, expiry) VALUES (?, ?, ?)",
              (user_id, "pro", expiry_date.isoformat()))
    conn.commit()

def remove_pro_user(user_id: int):
    c.execute("INSERT OR REPLACE INTO users(user_id, role, expiry) VALUES (?, ?, ?)",
              (user_id, "free", None))
    conn.commit()

def get_user_role(user_id: int):
    c.execute("SELECT role, expiry FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if row:
        role, expiry = row
        if role == "pro" and expiry:
            if datetime.datetime.fromisoformat(expiry) < datetime.datetime.now():
                remove_pro_user(user_id)
                return "free"
        return role
    else:
        c.execute("INSERT INTO users(user_id, role, expiry) VALUES (?, ?, ?)", (user_id, "free", None))
        conn.commit()
        return "free"

def get_all_users():
    c.execute("SELECT * FROM users")
    return c.fetchall()

# ===================== GEMINI AI =====================
def get_gemini_response(prompt):
    ai_prompt = f"""
You are an expert programming assistant called BLACK ADMIN X AI. 
Analyze the content and provide:

1. Explanation of what the code/file does
2. Highlights of key functions/sections
3. Suggestions for improvement if applicable
4. Short summary

Content: {prompt}
"""
    url = "https://api.generativeai.googleapis.com/v1beta2/models/text-bison-001:generate"
    headers = {
        "Authorization": f"Bearer {GEMINI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {"prompt": {"text": ai_prompt}, "temperature":0.7, "candidateCount":1}
    try:
        response = requests.post(url, headers=headers, json=data).json()
        return response['candidates'][0]['content']['text']
    except:
        return "❌ Error getting response from Gemini."

# ===================== BOT COMMANDS =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Hello {update.effective_user.first_name}! 🤖\nI am BLACK ADMIN bot.")

# ===== Admin Commands =====
async def addpro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Only owner can use this command.")
        return
    try:
        user_id = int(context.args[0])
        days = int(context.args[1])
        add_pro_user(user_id, days)
        await update.message.reply_text(f"✅ User {user_id} is now PRO for {days} days.")
    except:
        await update.message.reply_text("Usage: /addpro user_id days")

async def removepro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Only owner can use this command.")
        return
    try:
        user_id = int(context.args[0])
        remove_pro_user(user_id)
        await update.message.reply_text(f"✅ User {user_id} is now FREE.")
    except:
        await update.message.reply_text("Usage: /removepro user_id")

async def userlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Only owner can use this command.")
        return
    users = get_all_users()
    msg = "📝 Users:\n"
    for u in users:
        msg += f"{u[0]} - {u[1]} - {u[2]}\n"
    await update.message.reply_text(msg)

# ===== Owner-only HTML fetch =====
async def fetch_html(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Only owner can use this command!")
        return
    if not context.args:
        await update.message.reply_text("Usage: /html <website_url>")
        return
    url = context.args[0]
    try:
        response = requests.get(url)
        response.raise_for_status()
        html_content = response.text
        html_path = os.path.join(DOWNLOAD_FOLDER, "black.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        await update.message.reply_document(open(html_path, "rb"))
        await update.message.reply_text("✅ HTML saved as black.html")
    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching website: {str(e)}")

# ===== File Handler =====
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    role = get_user_role(user_id)
    file = update.message.document
    file_path = os.path.join(DOWNLOAD_FOLDER, file.file_name)
    await file.get_file().download_to_drive(file_path)
    if file.file_name.endswith(".zip"):
        try:
            with ZipFile(file_path, "r") as zip_ref:
                zip_ref.extractall(DOWNLOAD_FOLDER)
            await update.message.reply_text("✅ Zip extracted successfully.")
        except:
            await update.message.reply_text("❌ Cannot extract zip.")
        return
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read(3000)
        ai_response = get_gemini_response(content)
        await update.message.reply_text(f"📄 Preview + AI Explanation:\n{ai_response}")
    except:
        await update.message.reply_text("❌ Cannot read this file type.")

# ===== GitHub Repo Viewer =====
def get_repo_files(repo_url):
    parts = repo_url.replace("https://github.com/", "").split("/")
    if len(parts) < 2:
        return []
    owner, repo = parts[0], parts[1]
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/"
    res = requests.get(api_url).json()
    files = [f["name"] for f in res if "name" in f]
    return files

async def github_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /github <repo_url>")
        return
    url = context.args[0]
    files = get_repo_files(url)
    if files:
        msg = "📁 Repo files:\n" + "\n".join(files)
        await update.message.reply_text(msg)
        first_file_url = url.replace("https://github.com/", "https://raw.githubusercontent.com/") + f"/main/{files[0]}"
        try:
            content = requests.get(first_file_url).text[:3000]
            ai_resp = get_gemini_response(content)
            await update.message.reply_text(f"🤖 AI Explanation (first file {files[0]}):\n{ai_resp}")
        except:
            pass
    else:
        await update.message.reply_text("❌ Cannot fetch repo files.")

# ===== Virtual GF/BF Commands =====
async def add_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ শুধুমাত্র অ্যাডমিনই এটি ব্যবহার করতে পারবে।")
        return
    try:
        partner_type = context.args[0].lower()  # 'gf' বা 'bf'
        partner_name = context.args[1]
        if partner_type not in ["gf", "bf"]:
            raise ValueError()
        c.execute("INSERT OR REPLACE INTO partners(user_id, partner_name, partner_type) VALUES (?, ?, ?)",
                  (OWNER_ID, partner_name, partner_type))
        conn.commit()
        await update.message.reply_text(f"✅ {partner_type.upper()} '{partner_name}' তৈরি হয়েছে!")
    except:
        await update.message.reply_text("ব্যবহার: /addgf <name> বা /addbf <name>")

async def remove_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ শুধুমাত্র অ্যাডমিনই এটি ব্যবহার করতে পারবে।")
        return
    c.execute("DELETE FROM partners WHERE user_id=?", (OWNER_ID,))
    conn.commit()
    await update.message.reply_text("✅ ভার্চুয়াল পার্টনার মুছে ফেলা হয়েছে।")

# ===== AI + Virtual Partner Handler =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    # Virtual partner check
    c.execute("SELECT partner_name, partner_type FROM partners WHERE user_id=?", (OWNER_ID,))
    partner = c.fetchone()
    
    if partner:
        partner_name, partner_type = partner
        response = f"💌 {partner_name} ({partner_type} মোড) বলছে: "
        response += get_gemini_response(text)
        await update.message.reply_text(response)
        return

    # Identity checks
    if "bot ta ke banaise" in text.lower():
        await update.message.reply_text("BLACK ADMIN")
        return
    elif "tumi ke" in text.lower():
        await update.message.reply_text("BLACK ADMIN X AI")
        return

    # Default AI
    ai_response = get_gemini_response(text)
    await update.message.reply_text(ai_response)

# ===================== BOT SETUP =====================
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("addpro", addpro))
app.add_handler(CommandHandler("removepro", removepro))
app.add_handler(CommandHandler("userlist", userlist))
app.add_handler(CommandHandler("html", fetch_html))
app.add_handler(CommandHandler("github", github_view))
app.add_handler(CommandHandler("addgf", add_partner))
app.add_handler(CommandHandler("addbf", add_partner))
app.add_handler(CommandHandler("removepartner", remove_partner))
app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("Bot is running...")
app.run_polling()
