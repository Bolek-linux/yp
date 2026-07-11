import os
import re
import json
import base64
import hashlib
import threading
import urllib.parse
from collections import OrderedDict
from datetime import datetime

import tls_client
import telebot
from flask import Flask

# ================= KONFIGURACJA BOTA =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# ================= SŁOWNIK PAŃSTW (Dla Fusi) =================
COUNTRY_MAP = {
    # Europa
    "AL": "Albania", "AD": "Andora", "AT": "Austria", "BE": "Belgia", "BY": "Białoruś",
    "BA": "Bośnia i Hercegowina", "BG": "Bułgaria", "HR": "Chorwacja", "ME": "Czarnogóra",
    "CZ": "Czechy", "DK": "Dania", "EE": "Estonia", "FI": "Finlandia", "FR": "Francja",
    "GR": "Grecja", "ES": "Hiszpania", "NL": "Holandia", "IE": "Irlandia", "IS": "Islandia",
    "LI": "Liechtenstein", "LT": "Litwa", "LU": "Luksemburg", "LV": "Łotwa", "MK": "Macedonia Północna",
    "MT": "Malta", "MD": "Mołdawia", "MC": "Monako", "DE": "Niemcy", "NO": "Norwegia",
    "PL": "Polska", "PT": "Portugalia", "RU": "Rosja", "RO": "Rumunia", "SM": "San Marino",
    "RS": "Serbia", "SK": "Słowacja", "SI": "Słowenia", "CH": "Szwajcaria", "SE": "Szwecja",
    "UA": "Ukraina", "VA": "Watykan", "GB": "Wielka Brytania", "IT": "Włochy", "CY": "Cypr",

    # Reszta świata (wybrane)
    "AF": "Afganistan", "SA": "Arabia Saudyjska", "CN": "Chiny", "PH": "Filipiny",
    "IN": "Indie", "ID": "Indonezja", "JP": "Japonia", "KR": "Korea Południowa",
    "MY": "Malezja", "SG": "Singapur", "TW": "Tajwan", "TH": "Tajlandia",
    "VN": "Wietnam", "US": "Stany Zjednoczone", "CA": "Kanada", "BR": "Brazylia",
    "AR": "Argentyna", "MX": "Meksyk", "EG": "Egipt", "ZA": "RPA", "AU": "Australia"
}

# ================= SESJA GLOBALNA (Dla Yappy) =================
session = tls_client.Session(
    client_identifier="okhttp4_android_13",
    random_tls_extension_order=True
)

url_top = "https://ant.ritm.media/api/shub/public/v1/streams?page_size=30&top_size=20"


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


# ================= LOGIKA 1: YAPPY =================
def get_streams_messages():
    try:
        response = session.get(url_top, headers=get_headers())

        if response.status_code == 200:
            data = response.json()
            streams = data.get("streams", [])

            if not streams:
                return ["[-] Brak aktywnych streamów (Yappy)."]

            blocks = [f"🟢 Znaleziono {len(streams)} streamów (Yappy):\n\n"]

            for i, stream in enumerate(streams, 1):
                title = stream.get("title", "Brak tytułu")
                stream_url = stream.get("stream_url", "Brak linku")

                streamers = stream.get("streamers", [])
                nickname = streamers[0].get("nickname", "Nieznany") if streamers else "Nieznany"

                block = (
                    f"🎬 STREAM #{i}\n"
                    f"👤 Użytkownik: {nickname}\n"
                    f"📝 Tytuł: {title}\n"
                    f"🔗 Link: {stream_url}\n\n"
                )
                blocks.append(block)

            MAX_LENGTH = 4000
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
            return [f"❌ Błąd API Yappy: {response.status_code}"]

    except Exception as e:
        return [f"❌ Exception Yappy: {e}"]


def resolve_yappy_stream(short_url):
    try:
        res = session.get(short_url, allow_redirects=True)
        final_url = res.url

        uuid_match = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", final_url)
        if not uuid_match:
            return "❌ Nie udało się odnaleźć ID streamu w przekierowanym linku."

        stream_id = uuid_match.group(1).replace("-", "")
        api_url = f"https://ant.ritm.media/api/shub/public/v1/streams/cursor/{stream_id}"
        api_res = session.get(api_url, headers=get_headers())

        if api_res.status_code != 200:
            return f"❌ Błąd API przy pobieraniu streama: {api_res.status_code}"

        data = api_res.json()
        streams = data.get("streams", [])

        if not streams:
            return "❌ Ten stream już nie istnieje, zakończył się lub jest niedostępny."

        stream_info = streams[0]
        stream_url = stream_info.get("stream_url", "Brak linku m3u8")
        count_viewers = stream_info.get("count_viewers", 0)
        title = stream_info.get("title", "Brak tytułu")

        streamers = stream_info.get("streamers", [])
        nickname = streamers[0].get("nickname", "Nieznany") if streamers else "Nieznany"

        msg = (
            f"✅ **Znaleziono transmisję!**\n\n"
            f"👤 **Streamer:** `{nickname}`\n"
            f"📝 **Tytuł:** {title}\n"
            f"👁 **Widzów:** {count_viewers}\n\n"
            f"🔗 **Bezpośredni link do odtwarzacza (m3u8):**\n{stream_url}"
        )
        return msg

    except Exception as e:
        return f"❌ Wystąpił błąd podczas dekodowania Yappy: {str(e)}"


# ================= LOGIKA 2: FUSI =================
class FusiCrypto:
    def __init__(self):
        row0 = [chr(i) for i in range(97, 110)]
        row1 = ['0', '9', '_', '-', '1', '8', '6', '3', '4', '2', '7', '5', '#']
        row2 = [chr(i) for i in range(65, 78)]
        row3 = [chr(i) for i in range(110, 123)]
        row4 = [chr(i) for i in range(78, 91)]

        interleaved = []
        for col in range(13):
            for row in range(5):
                interleaved.append([row0, row1, row2, row3, row4][row][col])

        full_string = "".join(interleaved)
        self.custom_table = full_string.replace('l', '')
        self.std_table = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

        self.decode_map = str.maketrans(self.custom_table, self.std_table)
        self.encode_map = str.maketrans(self.std_table, self.custom_table)

    def decrypt_response(self, encrypted_str):
        if not encrypted_str: return ""
        if encrypted_str.startswith('"') and encrypted_str.endswith('"'):
            encrypted_str = encrypted_str[1:-1]
        temp_str = encrypted_str.replace('l', '=')
        try:
            std_b64_str = temp_str.translate(self.decode_map)
            decoded_bytes = base64.b64decode(std_b64_str)
            return decoded_bytes.decode('utf-8')
        except Exception as e:
            return f"Error: {e}"

    def _encrypt(self, plain_str):
        std_b64 = base64.b64encode(plain_str.encode('utf-8')).decode('utf-8')
        custom_b64 = std_b64.translate(self.encode_map)
        return custom_b64.replace('=', 'l')

    def generate_cert(self, cid, driver_id, app_version):
        raw_str = f"{cid}{driver_id}android{app_version}"
        md5_hash = hashlib.md5(raw_str.encode('utf-8')).hexdigest()
        return self._encrypt(md5_hash)


def build_fusi_request_body(user_conf, device_conf, crypto):
    params = OrderedDict()
    params["pkg"] = "android.footseen"
    params["appname"] = "meet.live.chat.among.friends.fs.lite"
    params["cid"] = device_conf['cid']
    params["net"] = "wifi"
    params["advertisingId"] = device_conf['advertisingId']
    params["model"] = device_conf['model']
    params["device"] = device_conf['model']
    params["brand"] = device_conf['brand']
    params["bootloader"] = "uboot"
    params["manufactruer"] = device_conf['manufacturer']
    params["prchannel"] = ""
    params["os"] = "android"
    params["driverid"] = device_conf['driverid']
    params["appversion"] = device_conf['appversion']

    cert_val = crypto.generate_cert(device_conf['cid'], device_conf['driverid'], device_conf['appversion'])
    params["cert"] = cert_val

    params["localecode"] = device_conf['localecode']
    params["lang"] = "1"
    params["larea"] = "1"

    if user_conf.get('uid') and user_conf.get('token'):
        params["uid"] = user_conf['uid']
        params["token"] = user_conf['token']

    params["type"] = "0"
    params["page"] = "1"
    params["pageSize"] = "20"

    return params


def get_fusi_messages():
    crypto = FusiCrypto()

    user_conf = {
        "uid": "9218785",
        "token": "b751e39eb039409bb1eb68935e20d638"
    }
    device_conf = {
        "cid": "ftsgp_fuss_lite",
        "appversion": "7745",
        "localecode": "pl-PL",
        "advertisingId": "00000000-0000-0000-0000-000000000000",
        "manufacturer": "samsung",
        "brand": "samsung",
        "model": "SM-N975F",
        "driverid": "3c9577b3ccdc3b3cb5328eb764c3f7fb2"
    }

    payload = build_fusi_request_body(user_conf, device_conf, crypto)

    fusi_session = tls_client.Session(
        client_identifier="okhttp4_android_7",
        random_tls_extension_order=True
    )

    url = "https://zhibo.yabolive.net/home/footSeen/queryLiveRoomList"

    headers = {
        "Accept-Encoding": "gzip",
        "Connection": "Keep-Alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "okhttp/3.11.0"
    }

    try:
        response = fusi_session.post(url, headers=headers, data=payload)
        encrypted_body = response.text

        if not encrypted_body:
            return ["❌ Pusta odpowiedź serwera Fusi."]

        decrypted_json = crypto.decrypt_response(encrypted_body)

        try:
            parsed = json.loads(decrypted_json)
            rooms = parsed.get("rooms", [])

            if not rooms:
                return ["Nie znaleziono żadnych pokoi na liście Fusi."]

            blocks = ["🟣 Znalezione pokoje (Fusi):\n\n"]
            display_index = 1

            for room in rooms:
                stream_link = room.get("publishUrl", "Brak linku")

                # Odfiltrowanie domen
                if "pull.zl.ox199.com" in stream_link:
                    continue

                raw_name = room.get("nickname", "Brak nazwy")
                raw_title = room.get("introduce", "Brak tytułu")
                raw_addr = room.get("addr", "")
                country_code = room.get("country", "")

                encryption = room.get("encryption", 0)
                toll_price = room.get("tollPrice", 0)
                room_type = room.get("roomType", 0)

                if encryption > 0 or toll_price > 0 or room_type != 0:
                    status = "🔒 Prywatny / Płatny"
                    details = []
                    if encryption > 0: details.append("Wymaga hasła")
                    if toll_price > 0: details.append(f"Płatny ({toll_price} monet)")
                    if room_type != 0: details.append(f"Typ: {room_type}")
                    status += f" [{', '.join(details)}]"
                else:
                    status = "🌍 Publiczny"

                streamer_name = urllib.parse.unquote(raw_name)
                stream_title = urllib.parse.unquote(raw_title)
                decoded_addr = urllib.parse.unquote(raw_addr)

                full_country = COUNTRY_MAP.get(country_code, country_code)

                if decoded_addr and full_country:
                    location = f"{decoded_addr} ({full_country})"
                elif decoded_addr:
                    location = decoded_addr
                elif full_country:
                    location = full_country
                else:
                    location = "Nieznana"

                # Blok tekstu dla jednego pokoju
                block = (
                    f"[{display_index}] Streamer: {streamer_name}\n"
                    f"    Typ:   {status}\n"
                    f"    Kraj:  {location}\n"
                    f"    Tytuł: {stream_title}\n"
                    f"    Link:  {stream_link}\n"
                    f"〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️\n"
                )
                blocks.append(block)
                display_index += 1

            # Dzielenie wiadomości, żeby nie przekroczyły limitu Telegrama (4096 znaków)
            MAX_LENGTH = 4000
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

        except json.JSONDecodeError:
            return ["❌ Nie udało się sparsować JSON z serwera Fusi."]

    except Exception as e:
        return [f"❌ Wystąpił błąd krytyczny podczas łączenia z Fusi: {e}"]


# ================= KOMENDY BOTA =================

# 1. Nowa komenda: /show_yappy
@bot.message_handler(commands=['show_yappy'])
def show_yappy_command(message):
    wait_msg = bot.reply_to(message, "⏳ Pobieranie listy streamów Yappy...")
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


# 2. Nowa komenda: /show_fusi
@bot.message_handler(commands=['show_fusi'])
def show_fusi_command(message):
    wait_msg = bot.reply_to(message, "⏳ Pobieranie listy pokoi Fusi, to może chwilę zająć...")
    messages = get_fusi_messages()

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


# 3. Obsługa wrzucanych krótkich linków Yappy
@bot.message_handler(func=lambda message: "yappy.media/s/" in message.text)
def handle_yappy_link(message):
    match = re.search(r"(https://yappy\.media/s/[A-Za-z0-9_]+)", message.text)
    if not match:
        return

    short_url = match.group(1)
    wait_msg = bot.reply_to(message, "🕵️‍♂️ Rozkodowywanie linku i pobieranie wideo (Yappy)...")

    result_text = resolve_yappy_stream(short_url)

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
    return "Bot działa i obsługuje Yappy oraz Fusi!"


def run_web():
    port = int(os.environ.get("PORT", 5000))
    app_web.run(host="0.0.0.0", port=port)


# ================= START =================
if __name__ == "__main__":
    print("[*] Start serwera web...")
    threading.Thread(target=run_web).start()

    print("[*] Start bota na Telegramie...")
    bot.infinity_polling()