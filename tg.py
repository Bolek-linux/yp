import tls_client
from datetime import datetime
import threading
from flask import Flask
import os
import telebot
import re

# ================= KONFIGURACJA =================
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN)

# ================= SESJA =================
session = tls_client.Session(
    client_identifier="okhttp4_android_13",
    random_tls_extension_order=True
)

url_top = "https://ant.ritm.media/api/shub/public/v1/streams?page_size=30&top_size=20"


# Wspólne nagłówki dla wszystkich zapytań do API
def get_headers():
    aktualny_czas_iso = datetime.now().astimezone().isoformat()
    return {
        "current_server_time": aktualny_czas_iso,
        "current_server_firewall": "QRATOR",
        "user-agent": "client: YAPPY_MOBILE version: 1.131.0(1054) device: Android WayDroid x86_64 Device OS: 13",
        "x-client-id": "94eda458-7080-37a0-95b4-7e919255e4fa",
        "accept": "application/json",
        "accept-language": "en-US"
    }


# ================= LOGIKA: LISTA STREAMÓW =================
def get_streams_messages():
    try:
        response = session.get(url_top, headers=get_headers())

        if response.status_code == 200:
            data = response.json()
            streams = data.get("streams", [])

            if not streams:
                return ["[-] Brak aktywnych streamów."]

            blocks = [f"🟢 Znaleziono {len(streams)} streamów:\n\n"]

            for i, stream in enumerate(streams, 1):
                title = stream.get("title", "Brak tytułu")
                stream_url = stream.get("stream_url", "Brak linku")

                streamers = stream.get("streamers", [])
                nickname = streamers[0].get("nickname", "Nieznany") if streamers else "Nieznany"

                block = (
                    f"🎬 STREAM #{i}\n"
                    f"👤 Użytkownik: `{nickname}`\n"
                    f"📝 Tytuł: {title}\n"
                    f"🔗 Link: {stream_url}\n\n"
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


# ================= LOGIKA: POJEDYNCZY LINK =================
def resolve_yappy_stream(short_url):
    try:
        # 1. Wysyłamy zapytanie do krótkiego linku. tls_client automatycznie idzie za przekierowaniem 301
        res = session.get(short_url, allow_redirects=True)
        final_url = res.url  # Wyciągamy ostateczny długi adres url

        # 2. Wyciągamy UUID z długiego linku za pomocą wyrażenia regularnego
        uuid_match = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", final_url)
        if not uuid_match:
            return "❌ Nie udało się odnaleźć ID streamu w przekierowanym linku."

        # Usuwamy myślniki, żeby uzyskać czysty ciąg do API
        stream_id = uuid_match.group(1).replace("-", "")

        # 3. Odpytujemy ukryte API Yappy za pomocą zebranych wcześniej informacji
        api_url = f"https://ant.ritm.media/api/shub/public/v1/streams/cursor/{stream_id}"
        api_res = session.get(api_url, headers=get_headers())

        if api_res.status_code != 200:
            return f"❌ Błąd API przy pobieraniu streama: {api_res.status_code}"

        data = api_res.json()
        streams = data.get("streams", [])

        if not streams:
            return "❌ Ten stream już nie istnieje, zakończył się lub jest niedostępny."

        # 4. Wyciągamy dane ze struktury JSON (zgodnie z naszym zrzutem ekranu)
        stream_info = streams[0]
        stream_url = stream_info.get("stream_url", "Brak linku m3u8")
        count_viewers = stream_info.get("count_viewers", 0)
        title = stream_info.get("title", "Brak tytułu")

        streamers = stream_info.get("streamers", [])
        nickname = streamers[0].get("nickname", "Nieznany") if streamers else "Nieznany"

        # Formatuje i zwraca wynik
        msg = (
            f"✅ **Znaleziono transmisję!**\n\n"
            f"👤 **Streamer:** `{nickname}`\n"
            f"📝 **Tytuł:** {title}\n"
            f"👁 **Widzów:** {count_viewers}\n\n"
            f"🔗 **Bezpośredni link do odtwarzacza (m3u8):**\n{stream_url}"
        )
        return msg

    except Exception as e:
        return f"❌ Wystąpił błąd podczas dekodowania: {str(e)}"


# ================= KOMENDY BOTA =================

# 1. Obsługa starej komendy /show
@bot.message_handler(commands=['show'])
def show_command(message):
    wait_msg = bot.reply_to(message, "⏳ Pobieranie listy streamów...")

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


# 2. NOWY HANDLER: Obsługa wrzucanych krótkich linków Yappy
@bot.message_handler(func=lambda message: "yappy.media/s/" in message.text)
def handle_yappy_link(message):
    # Wyciągamy sam link na wypadek, gdyby użytkownik wpisał też jakiś inny tekst
    match = re.search(r"(https://yappy\.media/s/[A-Za-z0-9_]+)", message.text)
    if not match:
        return

    short_url = match.group(1)
    wait_msg = bot.reply_to(message, "🕵️‍♂️ Rozkodowywanie linku i pobieranie wideo...")

    # Wykonujemy dekodowanie
    result_text = resolve_yappy_stream(short_url)

    # Wysyłamy wynik z parsowaniem Markdown, żeby link i nazwa ładnie się kopiowały
    bot.edit_message_text(
        result_text,
        chat_id=wait_msg.chat.id,
        message_id=wait_msg.message_id,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )


# ================= WEB (RENDER KEEP ALIVE) =================
app_web = Flask(__name__)


@app_web.route('/')
def home():
    return "Bot działa i nasłuchuje linków Yappy!"


def run_web():
    port = int(os.environ.get("PORT", 5000))
    app_web.run(host="0.0.0.0", port=port)


# ================= START =================
if __name__ == "__main__":
    print("[*] Start serwera web...")
    threading.Thread(target=run_web).start()

    print("[*] Start bota na Telegramie...")
    bot.infinity_polling()