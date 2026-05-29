import os
import django
from dotenv import load_dotenv
from asgiref.sync import sync_to_async

from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# =========================
# DJANGO SETTINGS
# =========================

load_dotenv()

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from patients.models import NewPatient


BOT_TOKEN = os.getenv("BOT_TOKEN")


# =========================
# STATES
# =========================

LANGUAGE, CONTACT, FULL_NAME, ANIMAL_NAME, ANIMAL_TYPE = range(5)


# =========================
# DATABASE HELPERS
# =========================

@sync_to_async
def save_new_patient(
    telegram_id,
    telegram_username,
    full_name,
    phone,
    animal_name,
    animal_type,
):
    """
    Telegram botdan kelgan arizani NewPatient modeliga saqlaydi.
    Bot endi doktor tanlamaydi.
    Bemor administrator dashboarddagi 'Yangi arizalar' bo‘limiga tushadi.
    """
    return NewPatient.objects.update_or_create(
        telegram_id=telegram_id,
        defaults={
            "full_name": full_name,
            "phone": phone,
            "telegram_username": telegram_username,
            "animal_name": animal_name,
            "animal_type": animal_type,
            "selected_doctor": None,
            "status": "new",
            "note": "Telegram bot orqali yuborilgan ariza",
        }
    )


# =========================
# TEXTS
# =========================

TEXTS = {
    "uz": {
        "choose_lang": "Tilni tanlang:",
        "send_contact": "Telefon raqamingizni yuboring:",
        "contact_button": "📞 Telefon raqamni yuborish",
        "ask_full_name": "Ism va familiyangizni kiriting:",
        "ask_animal_name": "Hayvoningiz nomini yozing:",
        "ask_animal_type": "Hayvon turini tanlang:",
        "saved": (
            "✅ Arizangiz qabul qilindi.\n\n"
            "Klinika administratori arizangizni ko‘rib chiqadi va sizni veterinarga yo‘naltiradi."
        ),
        "cancelled": "❌ Jarayon bekor qilindi. Qayta boshlash uchun /start bosing.",
        "back": "⬅️ Orqaga",
        "cancel": "❌ Bekor qilish",
        "wrong_contact": "Iltimos, telefon raqamingizni maxsus tugma orqali yuboring.",
        "type_again": "Iltimos, matn kiriting.",
    },
    "ru": {
        "choose_lang": "Выберите язык:",
        "send_contact": "Отправьте свой номер телефона:",
        "contact_button": "📞 Отправить номер телефона",
        "ask_full_name": "Введите имя и фамилию:",
        "ask_animal_name": "Введите имя животного:",
        "ask_animal_type": "Выберите вид животного:",
        "saved": (
            "✅ Ваша заявка принята.\n\n"
            "Администратор клиники рассмотрит заявку и направит вас к ветеринару."
        ),
        "cancelled": "❌ Процесс отменён. Чтобы начать заново, нажмите /start.",
        "back": "⬅️ Назад",
        "cancel": "❌ Отмена",
        "wrong_contact": "Пожалуйста, отправьте номер телефона через специальную кнопку.",
        "type_again": "Пожалуйста, введите текст.",
    },
    "en": {
        "choose_lang": "Choose language:",
        "send_contact": "Please send your phone number:",
        "contact_button": "📞 Send phone number",
        "ask_full_name": "Enter your full name:",
        "ask_animal_name": "Enter your animal's name:",
        "ask_animal_type": "Choose animal type:",
        "saved": (
            "✅ Your request has been accepted.\n\n"
            "The clinic administrator will review your request and assign you to a veterinarian."
        ),
        "cancelled": "❌ Process cancelled. Press /start to begin again.",
        "back": "⬅️ Back",
        "cancel": "❌ Cancel",
        "wrong_contact": "Please send your phone number using the special button.",
        "type_again": "Please enter text.",
    },
}


ANIMALS = {
    "uz": [
        ("dog", "🐶 It"),
        ("cat", "🐱 Mushuk"),
        ("cow", "🐄 Sigir"),
        ("horse", "🐴 Ot"),
        ("sheep", "🐑 Qo‘y"),
        ("goat", "🐐 Echki"),
        ("bird", "🐦 Qush"),
        ("other", "➕ Boshqa"),
    ],
    "ru": [
        ("dog", "🐶 Собака"),
        ("cat", "🐱 Кошка"),
        ("cow", "🐄 Корова"),
        ("horse", "🐴 Лошадь"),
        ("sheep", "🐑 Овца"),
        ("goat", "🐐 Коза"),
        ("bird", "🐦 Птица"),
        ("other", "➕ Другое"),
    ],
    "en": [
        ("dog", "🐶 Dog"),
        ("cat", "🐱 Cat"),
        ("cow", "🐄 Cow"),
        ("horse", "🐴 Horse"),
        ("sheep", "🐑 Sheep"),
        ("goat", "🐐 Goat"),
        ("bird", "🐦 Bird"),
        ("other", "➕ Other"),
    ],
}


# =========================
# HELPERS
# =========================

def get_lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.user_data.get("lang", "uz")


def t(context: ContextTypes.DEFAULT_TYPE, key: str) -> str:
    lang = get_lang(context)
    return TEXTS[lang][key]


def is_cancel(text: str | None) -> bool:
    return text in [
        "❌ Bekor qilish",
        "❌ Отмена",
        "❌ Cancel",
    ]


def is_back(text: str | None) -> bool:
    return text in [
        "⬅️ Orqaga",
        "⬅️ Назад",
        "⬅️ Back",
    ]


def language_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🇺🇿 O‘zbek", callback_data="lang_uz"),
                InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
                InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
            ]
        ]
    )


def contact_keyboard(context: ContextTypes.DEFAULT_TYPE):
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(t(context, "contact_button"), request_contact=True)],
            [t(context, "back"), t(context, "cancel")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def simple_keyboard(context: ContextTypes.DEFAULT_TYPE):
    return ReplyKeyboardMarkup(
        [
            [t(context, "back"), t(context, "cancel")],
        ],
        resize_keyboard=True,
    )


def animal_keyboard(context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)

    buttons = []
    row = []

    for code, name in ANIMALS[lang]:
        row.append(InlineKeyboardButton(name, callback_data=f"animal_{code}"))

        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    buttons.append(
        [
            InlineKeyboardButton(t(context, "back"), callback_data="back_animal"),
            InlineKeyboardButton(t(context, "cancel"), callback_data="cancel"),
        ]
    )

    return InlineKeyboardMarkup(buttons)


# =========================
# HANDLERS
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "Tilni tanlang / Выберите язык / Choose language:",
        reply_markup=language_keyboard(),
    )

    return LANGUAGE


async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = query.data.replace("lang_", "")
    context.user_data["lang"] = lang

    await query.message.reply_text(
        TEXTS[lang]["send_contact"],
        reply_markup=contact_keyboard(context),
    )

    return CONTACT


async def get_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if is_cancel(text):
        return await cancel(update, context)

    if is_back(text):
        await update.message.reply_text(
            "Tilni tanlang / Выберите язык / Choose language:",
            reply_markup=language_keyboard(),
        )
        return LANGUAGE

    if not update.message.contact:
        await update.message.reply_text(
            t(context, "wrong_contact"),
            reply_markup=contact_keyboard(context),
        )
        return CONTACT

    contact = update.message.contact
    context.user_data["phone"] = contact.phone_number

    await update.message.reply_text(
        t(context, "ask_full_name"),
        reply_markup=simple_keyboard(context),
    )

    return FULL_NAME


async def get_full_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if is_cancel(text):
        return await cancel(update, context)

    if is_back(text):
        await update.message.reply_text(
            t(context, "send_contact"),
            reply_markup=contact_keyboard(context),
        )
        return CONTACT

    if not text or not text.strip():
        await update.message.reply_text(
            t(context, "type_again"),
            reply_markup=simple_keyboard(context),
        )
        return FULL_NAME

    context.user_data["full_name"] = text.strip()

    await update.message.reply_text(
        t(context, "ask_animal_name"),
        reply_markup=simple_keyboard(context),
    )

    return ANIMAL_NAME


async def get_animal_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if is_cancel(text):
        return await cancel(update, context)

    if is_back(text):
        await update.message.reply_text(
            t(context, "ask_full_name"),
            reply_markup=simple_keyboard(context),
        )
        return FULL_NAME

    if not text or not text.strip():
        await update.message.reply_text(
            t(context, "type_again"),
            reply_markup=simple_keyboard(context),
        )
        return ANIMAL_NAME

    context.user_data["animal_name"] = text.strip()

    await update.message.reply_text(
        t(context, "ask_animal_type"),
        reply_markup=ReplyKeyboardRemove(),
    )

    await update.message.reply_text(
        t(context, "ask_animal_type"),
        reply_markup=animal_keyboard(context),
    )

    return ANIMAL_TYPE


async def choose_animal_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        await query.message.reply_text(
            t(context, "cancelled"),
            reply_markup=ReplyKeyboardRemove(),
        )
        context.user_data.clear()
        return ConversationHandler.END

    if query.data == "back_animal":
        await query.message.reply_text(
            t(context, "ask_animal_name"),
            reply_markup=simple_keyboard(context),
        )
        return ANIMAL_NAME

    animal_type = query.data.replace("animal_", "")
    context.user_data["animal_type"] = animal_type

    user = query.from_user

    telegram_id = user.id
    telegram_username = user.username

    phone = context.user_data.get("phone")
    full_name = context.user_data.get("full_name")
    animal_name = context.user_data.get("animal_name")

    await save_new_patient(
        telegram_id=telegram_id,
        telegram_username=telegram_username,
        full_name=full_name,
        phone=phone,
        animal_name=animal_name,
        animal_type=animal_type,
    )

    await query.message.reply_text(
        t(context, "saved"),
        reply_markup=ReplyKeyboardRemove(),
    )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        t(context, "cancelled"),
        reply_markup=ReplyKeyboardRemove(),
    )

    context.user_data.clear()
    return ConversationHandler.END


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"Bot xatosi: {context.error}")


# =========================
# MAIN
# =========================

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN .env faylida topilmadi.")


    app = (
    ApplicationBuilder()
    .token(BOT_TOKEN)
    .connect_timeout(30)
    .read_timeout(30)
    .write_timeout(30)
    .pool_timeout(30)
    .build()
    )

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
        ],
        states={
            LANGUAGE: [
                CallbackQueryHandler(choose_language, pattern="^lang_"),
            ],
            CONTACT: [
                MessageHandler(filters.CONTACT | filters.TEXT, get_contact),
            ],
            FULL_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_full_name),
            ],
            ANIMAL_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_animal_name),
            ],
            ANIMAL_TYPE: [
                CallbackQueryHandler(
                    choose_animal_type,
                    pattern="^(animal_|back_animal|cancel)"
                ),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, cancel),
        ],
    )

    app.add_handler(conv_handler)
    app.add_error_handler(error_handler)

    print("Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()