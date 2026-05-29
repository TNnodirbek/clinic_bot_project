import os
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")


def send_telegram_message(chat_id, text):
    if not BOT_TOKEN:
        return {
            "ok": False,
            "description": "BOT_TOKEN topilmadi. .env faylni tekshiring."
        }

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        response = requests.post(
            url,
            data={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
            },
            timeout=20
        )
        return response.json()

    except requests.exceptions.Timeout:
        return {
            "ok": False,
            "description": "Telegram API ga ulanish vaqti tugadi."
        }

    except requests.exceptions.RequestException as error:
        return {
            "ok": False,
            "description": str(error)
        }


def send_telegram_document(chat_id, file_path, caption=""):
    if not BOT_TOKEN:
        return {
            "ok": False,
            "description": "BOT_TOKEN topilmadi. .env faylni tekshiring."
        }

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"

    try:
        with open(file_path, "rb") as file:
            response = requests.post(
                url,
                data={
                    "chat_id": chat_id,
                    "caption": caption,
                },
                files={
                    "document": file,
                },
                timeout=30
            )

        return response.json()

    except requests.exceptions.Timeout:
        return {
            "ok": False,
            "description": "PDF yuborishda Telegram API ga ulanish vaqti tugadi."
        }

    except requests.exceptions.RequestException as error:
        return {
            "ok": False,
            "description": str(error)
        }

    except FileNotFoundError:
        return {
            "ok": False,
            "description": "PDF fayl topilmadi."
        }