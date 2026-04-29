import telebot
import requests
import os
import time
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)

warn_count = defaultdict(int)
flood_tracker = defaultdict(list)

WARN_LIMIT = 3
FLOOD_LIMIT = 5
FLOOD_TIME = 5


def is_admin(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ["administrator", "creator"]
    except:
        return False


def get_mention(user):
    name = user.first_name or "ইউজার"
    return f"[{name}](tg://user?id={user.id})"


def is_flood(user_id):
    now = time.time()
    flood_tracker[user_id] = [t for t in flood_tracker[user_id] if now - t < FLOOD_TIME]
    flood_tracker[user_id].append(now)
    return len(flood_tracker[user_id]) > FLOOD_LIMIT


def check_with_gemini(text):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{
                "parts": [{
                    "text": f"""তুমি একটি টেলিগ্রাম গ্রুপ মডারেটর।
মেসেজ: "{text}"
শুধু YES অথবা NO বলো।
YES = অশ্লীল/গালি/হেট স্পিচ আছে
NO = স্বাভাবিক মেসেজ"""
                }]
            }]
        }
        res = requests.post(url, json=payload)
        result = res.json()
        answer = result["candidates"][0]["content"]["parts"][0]["text"].strip().upper()
        return "YES" in answer
    except:
        return False


def do_warn(chat_id, user_id, user, reason="নিয়ম ভঙ্গ"):
    warn_count[user_id] += 1
    count = warn_count[user_id]
    mention = get_mention(user)
    if count >= WARN_LIMIT:
        try:
            bot.ban_chat_member(chat_id, user_id)
            warn_count[user_id] = 0
            bot.send_message(chat_id,
                f"🚫 {mention} কে *{WARN_LIMIT}টি warning* এর পর *ban* করা হয়েছে।\nকারণ: {reason}",
                parse_mode="Markdown")
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ Ban করতে সমস্যা: {e}")
    else:
        bot.send_message(chat_id,
            f"⚠️ {mention} কে *Warning {count}/{WARN_LIMIT}* দেওয়া হলো।\nকারণ: {reason}\n_{WARN_LIMIT}টি warning হলে auto-ban হবে।_",
            parse_mode="Markdown")


@bot.message_handler(content_types=["new_chat_members"])
def welcome(message):
    for member in message.new_chat_members:
        if member.is_bot:
            continue
        mention = get_mention(member)
        bot.send_message(message.chat.id,
            f"👋 স্বাগতম {mention}!\n\n"
            f"📌 *গ্রুপের নিয়ম মেনে চলুন:*\n"
            f"• অশ্লীল ভাষা ব্যবহার করবেন না\n"
            f"• স্প্যাম করবেন না\n"
            f"• সকলের সাথে সম্মান করুন\n\n"
            f"_নিয়ম ভঙ্গ করলে warning ও ban হতে পারে।_",
            parse_mode="Markdown")


@bot.message_handler(func=lambda msg: msg.chat.type in ["group", "supergroup"])
def moderate(message):
    user = message.from_user
    chat_id = message.chat.id
    if is_admin(chat_id, user.id):
        return
    if is_flood(user.id):
        try:
            bot.delete_message(chat_id, message.message_id)
        except:
            pass
        do_warn(chat_id, user.id, user, reason="স্প্যাম/ফ্লাড")
        return
    if message.text and check_with_gemini(message.text):
        try:
            bot.delete_message(chat_id, message.message_id)
        except:
            pass
        do_warn(chat_id, user.id, user, reason="অশ্লীল ভাষা")


@bot.message_handler(commands=["warn"])
def warn_cmd(message):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ শুধু অ্যাডমিনরা ব্যবহার করতে পারবেন।")
        return
    if not message.reply_to_message:
        bot.reply_to(message, "⚠️ কারো মেসেজে reply করে ব্যবহার করুন।")
        return
    target = message.reply_to_message.from_user
    parts = message.text.split(maxsplit=1)
    reason = parts[1] if len(parts) > 1 else "অ্যাডমিন কর্তৃক সতর্কতা"
    do_warn(message.chat.id, target.id, target, reason)


@bot.message_handler(commands=["ban"])
def ban_cmd(message):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ শুধু অ্যাডমিনরা ব্যবহার করতে পারবেন।")
        return
    if not message.reply_to_message:
        bot.reply_to(message, "⚠️ কারো মেসেজে reply করে ব্যবহার করুন।")
        return
    target = message.reply_to_message.from_user
    try:
        bot.ban_chat_member(message.chat.id, target.id)
        bot.send_message(message.chat.id,
            f"🚫 {get_mention(target)} কে *ban* করা হয়েছে।",
            parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"⚠️ সমস্যা: {e}")


@bot.message_handler(commands=["kick"])
def kick_cmd(message):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ শুধু অ্যাডমিনরা ব্যবহার করতে পারবেন।")
        return
    if not message.reply_to_message:
        bot.reply_to(message, "⚠️ কারো মেসেজে reply করে ব্যবহার করুন।")
        return
    target = message.reply_to_message.from_user
    try:
        bot.ban_chat_member(message.chat.id, target.id)
        bot.unban_chat_member(message.chat.id, target.id)
        bot.send_message(message.chat.id,
            f"👢 {get_mention(target)} কে *kick* করা হয়েছে।",
            parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"⚠️ সমস্যা: {e}")


@bot.message_handler(commands=["unwarn"])
def unwarn_cmd(message):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ শুধু অ্যাডমিনরা ব্যবহার করতে পারবেন।")
        return
    if not message.reply_to_message:
        bot.reply_to(message, "⚠️ কারো মেসেজে reply করে ব্যবহার করুন।")
        return
    target = message.reply_to_message.from_user
    warn_count[target.id] = 0
    bot.send_message(message.chat.id,
        f"✅ {get_mention(target)} এর সব warning রিসেট হয়েছে।",
        parse_mode="Markdown")


@bot.message_handler(commands=["start", "help"])
def help_cmd(message):
    bot.reply_to(message,
        "🤖 *গ্রুপ মডারেটর বট*\n\n"
        "*অ্যাডমিন কমান্ড:*\n"
        "• `/warn` — reply করে warn দিন\n"
        "• `/unwarn` — warning রিসেট করুন\n"
        "• `/ban` — ban করুন\n"
        "• `/kick` — kick করুন\n\n"
        "*অটো ফিচার:*\n"
        "✅ AI দিয়ে অশ্লীল ভাষা ডিটেক্ট\n"
        "✅ ফ্লাড প্রোটেকশন\n"
        "✅ Welcome message\n"
        f"✅ {WARN_LIMIT} warning = auto-ban",
        parse_mode="Markdown")


print("✅ মডারেটর বট চালু হয়েছে...")
bot.infinity_polling()
