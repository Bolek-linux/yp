import tls_client
from datetime import datetime
import threading
from flask import Flask
import os
import telebot

# ================= KONFIGURACJA =================
API_ID = os.getenv("API_ID")        # nieużywane tutaj, ale możesz zostawić
API_HASH = os.getenv("API_HASH")    # nieużywane
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN)

# ================= SESJA =================
session = tls_client.Session(
    client_identifier="okhttp4_android_13",
    random_tls_extension_order=True
)

url = "https://ant.ritm.media/api/shub/public/v1/streams?page_size=30&top_size=20"


def get_streams_messages():
    aktualny_czas_iso = datetime.now().astimezone().isoformat()

    headers = {
        "current_server_time": aktualny_czas_iso,
        "current_server_firewall": "QRATOR",
        "user-agent": "client: YAPPY_MOBILE version: 1.131.0(1054) device: Android WayDroid x86_64 Device OS: 13",
        "x-client-id": "94eda458-7080-37a0-95b4-7e919255e4fa",
        "accept": "application/json",
        "accept-language": "en-US"
    }

    try:
        response = session.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            streams = data.get("streams", [])

            if not streams:
                return ["[-] Brak aktywnych streamów."]

            blocks = [f"📡 Znaleziono {len(streams)} streamów:\n\n"]

            for i, stream in enumerate(streams, 1):
                title = stream.get("title", "Brak tytułu")
                stream_url = stream.get("stream_url", "Brak linku")

                streamers = stream.get("streamers", [])
                nickname = streamers[0].get("nickname", "Nieznany") if streamers else "Nieznany"

                block = (
                    f"🎬 STREAM #{i}\n"
                    f"👤 Użytkownik: `{nickname}`\n"
                    f"📝 Tytuł: {title}\n"
                    f"🔗 Link: `{stream_url}`\n\n"
                )
                blocks.append(block)

            MAX_LENGTH = 4096
            messages = []
            current = ""

            for block in blocks:
                if len(current) + len(block) > MAX_LENGTH:
                    messages.append(current.strip())
                    current = block
                else:
                    current += block

            if current:
                messages.append(current.strip())

            return messages

        else:
            return [f"❌ Błąd API: {response.status_code}"]

    except Exception as e:
        return [f"❌ Exception: {e}"]


# ================= KOMENDA =================
@bot.message_handler(commands=['show'])
def show_command(message):
    wait_msg = bot.reply_to(message, "⏳ Pobieranie streamów...")

    messages = get_streams_messages()

    for i, text in enumerate(messages):
        if i == 0:
            bot.edit_message_text(
                text,
                chat_id=wait_msg.chat.id,
                message_id=wait_msg.message_id,
                disable_web_page_preview=True
            )
        else:
            bot.send_message(
                message.chat.id,
                text,
                disable_web_page_preview=True
            )


# ================= WEB (RENDER KEEP ALIVE) =================
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot działa!"

def run_web():
    port = int(os.environ.get("PORT", 5000))
    app_web.run(host="0.0.0.0", port=port)


# ================= START =================
if __name__ == "__main__":
    print("[*] Start web...")
    threading.Thread(target=run_web).start()

    print("[*] Start bot...")
    bot.infinity_polling()