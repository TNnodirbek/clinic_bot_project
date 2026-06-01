import os
from pathlib import Path

from dotenv import load_dotenv
from telegram import Bot

from django.conf import settings

from patients.utils.pdf import generate_visit_pdf


load_dotenv(Path(settings.BASE_DIR) / ".env")


def get_visit_patient(visit):
    return (
        getattr(visit, "patient", None)
        or getattr(visit, "new_patient", None)
        or getattr(visit, "application", None)
        or getattr(visit, "newpatient", None)
    )


def safe_get(obj, field_name, default=None):
    if not obj:
        return default
    return getattr(obj, field_name, default)


async def send_visit_pdf_to_telegram(visit):
    """
    Visit yakunlangandan keyin PDF yaratadi va Telegramga yuboradi.
    Bu funksiya ariza yuborilgan zahoti chaqirilmaydi.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")

    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN yoki BOT_TOKEN .env faylda topilmadi.")

    patient = get_visit_patient(visit)

    telegram_id = (
        safe_get(patient, "telegram_id")
        or safe_get(getattr(patient, "owner", None), "telegram_id")
        or safe_get(getattr(visit, "owner", None), "telegram_id")
    )

    if not telegram_id:
        raise RuntimeError("Telegram ID topilmadi. PDF yuborilmadi.")

    pdf_path = generate_visit_pdf(visit)

    bot = Bot(token=token)

    caption = (
        "✅ Ko‘rik yakunlandi.\n\n"
        "Quyida hayvoningiz bo‘yicha yakuniy tibbiy karta PDF shaklida yuborildi.\n\n"
        f"📄 Hujjat: {Path(pdf_path).name}"
    )

    with open(pdf_path, "rb") as pdf_file:
        await bot.send_document(
            chat_id=int(telegram_id),
            document=pdf_file,
            filename=Path(pdf_path).name,
            caption=caption,
        )

    return pdf_path