import tls_client
from datetime import datetime
from pyrogram import Client, filters
import threading
from flask import Flask
import os

# ================= KONFIGURACJA BOTA =================
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Inicjalizacja bota
app = Client("yappy_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ================= LOGIKA POBIERANIA =================
session = tls_client.Session(
    client_identifier="okhttp4_android_13",
    random_tls_extension_order=True
)

url = "https://ant.ritm.media/api/shub/public/v1/streams?page_size=15&top_size=20"


def get_streams_messages() -> list:
    """
    Pobiera streamy i zwraca LISTĘ wiadomości tekstowych,
    odpowiednio podzielonych, aby nie przekroczyć limitu Telegrama.
    """
    aktualny_czas_iso = datetime.now().astimezone().isoformat()

    headers = {
        "current_server_time": aktualny_czas_iso,
        "current_server_firewall": "QRATOR",
        "user-agent": "client: YAPPY_MOBILE version: 1.131.0(1054) device: Android WayDroid x86_64 Device OS: 13 deviceID: 94eda458-7080-37a0-95b4-7e919255e4fa Network: UNDEFINED capacity: high",
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
                return ["[-] Brak aktywnych streamów (lista jest pusta)."]

            # Najpierw tworzymy "klocki" (osobne bloki tekstu dla każdego streama)
            blocks = [f"✅ **Znaleziono {len(streams)} streamów:**\n\n"]

            for index, stream in enumerate(streams, start=1):
                title = stream.get("title", "Brak tytułu")
                stream_url = stream.get("stream_url", "Brak linku")

                streamers_list = stream.get("streamers", [])
                if streamers_list and len(streamers_list) > 0:
                    nickname = streamers_list[0].get("nickname", "Nieznany")
                else:
                    nickname = "Nieznany"

                # Generujemy pojedynczy, kompletny blok dla streama
                block = (
                    f"🔹 **STREAM #{index}**\n"
                    f"👤 Użytkownik: `{nickname}`\n"
                    f"📝 Tytuł: {title}\n"
                    f"🔗 Link: `{stream_url}`\n\n"
                )
                blocks.append(block)

            # Teraz pakujemy klocki do wiadomości dbając o limit znaków
            MAX_LENGTH = 4096
            messages = []
            current_message = ""

            for block in blocks:
                # Jeśli dodanie klocka przekroczy limit, zapisujemy starą wiadomość
                # i zaczynamy nową od tego konkretnego klocka.
                if len(current_message) + len(block) > MAX_LENGTH:
                    messages.append(current_message.strip())  # .strip() usuwa puste linie na końcu
                    current_message = block
                else:
                    current_message += block

            # Dodajemy to, co zostało w ostatniej, niedokończonej wiadomości
            if current_message:
                messages.append(current_message.strip())

            return messages  # Zwracamy listę gotowych tekstów

        else:
            return [f"❌ Błąd serwera. Kod statusu: `{response.status_code}`"]

    except Exception as e:
        return [f"⚠️ Wystąpił błąd skryptu: `{e}`"]


# ================= OBSŁUGA KOMEND =================

@app.on_message(filters.command("show"))
async def show_command(client, message):
    # Wysyłamy wiadomość oczekiwania
    wait_msg = await message.reply_text("⏳ Pobieranie aktualnej listy streamów...")

    # Otrzymujemy gotową, poporcjowaną LISTĘ wiadomości do wysłania
    messages_to_send = get_streams_messages()

    # Wysyłamy paczki jedna po drugiej
    for i, msg_text in enumerate(messages_to_send):
        if i == 0:
            # Pierwszą paczkę wstawiamy w miejsce napisu "Pobieranie..." (żeby nie śmiecić na czacie)
            await wait_msg.edit_text(msg_text, disable_web_page_preview=True)
        else:
            # Każdą kolejną paczkę (jeśli była ich więcej niż 1) bot wysyła jako nową wiadomość
            await message.reply_text(msg_text, disable_web_page_preview=True)


# ================= SERWER WEBOWY (DLA RENDER.COM) =================
app_web = Flask(__name__)


@app_web.route('/')
def keep_alive():
    return "Bot działa i ma się dobrze!"


def run_web():
    # Render używa zmiennej środowiskowej PORT, domyślnie 5000 dla lokalnego testowania
    port = int(os.environ.get("PORT", 5000))
    app_web.run(host="0.0.0.0", port=port)


# ================= GŁÓWNY START APLIKACJI =================
if __name__ == "__main__":
    # Uruchamiamy serwer webowy w osobnym wątku (żeby nie zablokował bota)
    print("[*] Uruchamianie serwera webowego (podtrzymującego życie)...")
    t = threading.Thread(target=run_web)
    t.start()

    # Uruchamiamy bota
    print("[*] Uruchamianie bota na Telegramie...")
    app.run()