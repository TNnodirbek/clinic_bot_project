import os
from pathlib import Path
from decimal import Decimal

from dotenv import load_dotenv

from asgiref.sync import sync_to_async
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, models

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from patients.models import NewPatient, Owner, Pet


BASE_DIR = Path(__file__).resolve().parents[4]
load_dotenv(BASE_DIR / ".env")


# =========================
# STATES
# =========================

(
    LANGUAGE,
    MAIN_MENU,

    FULL_NAME,

    PHONE_CHOICE,
    PHONE_TEXT,

    PET_CHOICE,
    ANIMAL_TYPE,
    ANIMAL_NAME,

    LOCATION_CHOICE,
    ADDRESS_TEXT,

    DANGER_TYPE,
) = range(11)


# =========================
# CONSTANTS
# =========================

LANG_UZ = "uz"
LANG_RU = "ru"
LANG_EN = "en"

SERVICE_CLINIC = "clinic"
SERVICE_VET_CALL = "vet_call"
SERVICE_DANGER = "danger"

CLINIC_PHONE = "+998 (70) 123-45-67"


# =========================
# TEXTS
# =========================

TEXT = {
    "choose_language": {
        "uz": "Tilni tanlang:\nВыберите язык:\nChoose language:",
        "ru": "Tilni tanlang:\nВыберите язык:\nChoose language:",
        "en": "Tilni tanlang:\nВыберите язык:\nChoose language:",
    },
    "welcome": {
        "uz": "Salom, {name}!\nVetClinic elektron ariza botiga xush kelibsiz.\nMa’lumotlaringiz faqat veterinariya xizmati uchun ishlatiladi.\n\nXizmat turini tanlang:",
        "ru": "Здравствуйте, {name}!\nДобро пожаловать в электронный бот заявок VetClinic.\nВаши данные используются только для ветеринарных услуг.\n\nВыберите тип услуги:",
        "en": "Hello, {name}!\nWelcome to the VetClinic electronic request bot.\nYour data is used only for veterinary services.\n\nChoose a service:",
    },
    "menu": {
        "uz": "Xizmat turini tanlang:",
        "ru": "Выберите тип услуги:",
        "en": "Choose a service:",
    },
    "language_changed": {
        "uz": "✅ Til o‘zgartirildi.\n\nXizmat turini tanlang:",
        "ru": "✅ Язык изменён.\n\nВыберите тип услуги:",
        "en": "✅ Language changed.\n\nChoose a service:",
    },
    "ask_full_name": {
        "uz": "Ism-familiyangizni yozing:",
        "ru": "Напишите ваше имя и фамилию:",
        "en": "Enter your full name:",
    },
    "phone_choice": {
        "uz": "Telefon raqamingizni yuboring yoki qo‘lda yozing:",
        "ru": "Отправьте номер телефона или напишите вручную:",
        "en": "Send your phone number or enter it manually:",
    },
    "send_contact_message": {
        "uz": "Pastdagi tugma orqali telefon raqamingizni yuboring:",
        "ru": "Отправьте номер телефона с помощью кнопки ниже:",
        "en": "Send your phone number using the button below:",
    },
    "phone_text": {
        "uz": "Telefon raqamingizni yozing:\nMasalan: +998901234567",
        "ru": "Напишите номер телефона:\nНапример: +998901234567",
        "en": "Enter your phone number:\nExample: +998901234567",
    },
    "pet_choice": {
        "uz": "Avvalgi hayvoningizni tanlang yoki yangi hayvon qo‘shing:",
        "ru": "Выберите существующее животное или добавьте новое:",
        "en": "Choose an existing animal or add a new one:",
    },
    "animal_type": {
        "uz": "Hayvon turini tanlang:",
        "ru": "Выберите тип животного:",
        "en": "Choose animal type:",
    },
    "animal_name": {
        "uz": "Hayvon nomini yozing.\nAgar nomi bo‘lmasa, “O‘tkazib yuborish” tugmasini bosing:",
        "ru": "Напишите имя животного.\nЕсли имени нет, нажмите «Пропустить»:",
        "en": "Enter the animal name.\nIf there is no name, press “Skip”:",
    },
    "location_with_old": {
        "uz": "Oldingi manzil topildi:\n{address}\n\nManzilni tanlang:",
        "ru": "Найден предыдущий адрес:\n{address}\n\nВыберите адрес:",
        "en": "Previous address found:\n{address}\n\nChoose address:",
    },
    "location_without_old": {
        "uz": "Manzilni kiriting:",
        "ru": "Укажите адрес:",
        "en": "Enter address:",
    },
    "send_location_message": {
        "uz": "Pastdagi tugma orqali joylashuvingizni yuboring:",
        "ru": "Отправьте геолокацию с помощью кнопки ниже:",
        "en": "Send your location using the button below:",
    },
    "address_text": {
        "uz": "Manzilni yozib yuboring:",
        "ru": "Напишите адрес:",
        "en": "Write the address:",
    },
    "danger_type": {
        "uz": "Xavfli holat turini tanlang:",
        "ru": "Выберите тип опасного случая:",
        "en": "Choose dangerous case type:",
    },
    "cancelled": {
        "uz": "❌ Amal bekor qilindi.",
        "ru": "❌ Действие отменено.",
        "en": "❌ Action cancelled.",
    },
    "success_clinic": {
        "uz": "✅ Klinikada davolash arizangiz qabul qilindi.\n\nAriza raqami: {code}\nHayvon ID: {pet_code}\n\nKlinika administratori arizangizni ko‘rib chiqadi.",
        "ru": "✅ Заявка на лечение в клинике принята.\n\nНомер заявки: {code}\nID животного: {pet_code}\n\nАдминистратор клиники рассмотрит вашу заявку.",
        "en": "✅ Clinic treatment request accepted.\n\nRequest code: {code}\nAnimal ID: {pet_code}\n\nThe clinic administrator will review your request.",
    },
    "success_vet": {
        "uz": "✅ Veterinar chaqirish arizangiz qabul qilindi.\n\nAriza raqami: {code}\nHayvon ID: {pet_code}\n\nKlinika administratori siz bilan bog‘lanadi.\n☎️ {phone}",
        "ru": "✅ Заявка на вызов ветеринара принята.\n\nНомер заявки: {code}\nID животного: {pet_code}\n\nАдминистратор клиники свяжется с вами.\n☎️ {phone}",
        "en": "✅ Vet call request accepted.\n\nRequest code: {code}\nAnimal ID: {pet_code}\n\nThe clinic administrator will contact you.\n☎️ {phone}",
    },
    "success_danger": {
        "uz": "✅ Xavfli holat bo‘yicha xabar qabul qilindi.\n\nAriza raqami: {code}\n\nAdministrator xabarni ko‘rib chiqadi.",
        "ru": "✅ Сообщение об опасном случае принято.\n\nНомер заявки: {code}\n\nАдминистратор рассмотрит сообщение.",
        "en": "✅ Dangerous case report accepted.\n\nRequest code: {code}\n\nThe administrator will review it.",
    },
    "wrong": {
        "uz": "Iltimos, tugmalardan birini tanlang.",
        "ru": "Пожалуйста, выберите одну из кнопок.",
        "en": "Please choose one of the buttons.",
    },
}


def tr(lang, key, **kwargs):
    text = TEXT.get(key, {}).get(lang) or TEXT.get(key, {}).get(LANG_UZ) or key

    if not text or not str(text).strip():
        text = key

    return text.format(**kwargs) if kwargs else text


def get_lang(context):
    return context.user_data.get("lang", LANG_UZ)


# =========================
# MODEL HELPERS
# =========================

def model_has_field(model_class, field_name):
    return any(field.name == field_name for field in model_class._meta.fields)


def model_choice_keys(model_class, field_name):
    for field in model_class._meta.fields:
        if field.name == field_name and field.choices:
            return [choice[0] for choice in field.choices]
    return []


def valid_animal_type(code):
    choices = set(model_choice_keys(NewPatient, "animal_type") + model_choice_keys(Pet, "animal_type"))

    if not choices:
        return code

    if code in choices:
        return code

    if "other" in choices:
        return "other"

    return list(choices)[0]


def normalize_phone(phone):
    phone = (phone or "").strip().replace(" ", "").replace("-", "")

    if phone.startswith("+"):
        return phone

    if phone.startswith("998"):
        return f"+{phone}"

    return phone


def pet_code(pet):
    if not pet:
        return "-"

    return getattr(pet, "pet_code", None) or f"HAY-{pet.id:05d}"


def pet_name(pet):
    if not pet:
        return "-"

    if getattr(pet, "name", None):
        return pet.name

    if hasattr(pet, "get_animal_type_display"):
        return pet.get_animal_type_display()

    return pet.animal_type or "-"


def address_from_note(note):
    for line in (note or "").splitlines():
        if line.strip().startswith("Manzil:"):
            value = line.split(":", 1)[1].strip()
            if value and value != "Klinika ichida":
                return value
    return ""


def format_location_note(address="", latitude=None, longitude=None):
    parts = []

    if address:
        parts.append(f"Manzil: {address}")

    if latitude is not None and longitude is not None:
        parts.append(f"Latitude: {latitude}")
        parts.append(f"Longitude: {longitude}")
        parts.append(f"Xarita: https://www.google.com/maps?q={latitude},{longitude}")

    return "\n".join(parts)


# =========================
# INLINE KEYBOARDS
# =========================

def language_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇺🇿 O‘zbek", callback_data="lang:uz"),
            InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru"),
            InlineKeyboardButton("🇬🇧 English", callback_data="lang:en"),
        ]
    ])


def main_keyboard(lang):
    if lang == LANG_RU:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🏥 Лечение", callback_data="service:clinic"),
                InlineKeyboardButton("🚑 Вызов", callback_data="service:vet_call"),
                InlineKeyboardButton("⚠️ Опасно", callback_data="service:danger"),
            ],
            [InlineKeyboardButton("🌐 Изменить язык", callback_data="change_language")],
        ])

    if lang == LANG_EN:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🏥 Clinic", callback_data="service:clinic"),
                InlineKeyboardButton("🚑 Vet call", callback_data="service:vet_call"),
                InlineKeyboardButton("⚠️ Danger", callback_data="service:danger"),
            ],
            [InlineKeyboardButton("🌐 Change language", callback_data="change_language")],
        ])

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏥 Klinikada davolash", callback_data="service:clinic"),
            InlineKeyboardButton("🚑 Veterinar chaqirish", callback_data="service:vet_call"),
            InlineKeyboardButton("⚠️ Xavfli holatlar", callback_data="service:danger"),
        ],
        [InlineKeyboardButton("🌐 Tilni o‘zgartirish", callback_data="change_language")],
    ])

def back_cancel_keyboard(lang, back_to):
    if lang == LANG_RU:
        back = "⬅️ Назад"
        cancel = "❌ Отмена"
    elif lang == LANG_EN:
        back = "⬅️ Back"
        cancel = "❌ Cancel"
    else:
        back = "⬅️ Orqaga"
        cancel = "❌ Bekor qilish"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(back, callback_data=f"back:{back_to}"),
            InlineKeyboardButton(cancel, callback_data="cancel"),
        ]
    ])


def phone_choice_keyboard(lang):
    if lang == LANG_RU:
        auto = "📞 Автоматически отправить"
        manual = "✍️ Написать вручную"
        back = "⬅️ Назад"
        cancel = "❌ Отмена"
    elif lang == LANG_EN:
        auto = "📞 Send automatically"
        manual = "✍️ Type manually"
        back = "⬅️ Back"
        cancel = "❌ Cancel"
    else:
        auto = "📞 Avtomatik yuborish"
        manual = "✍️ Qo‘lda yozish"
        back = "⬅️ Orqaga"
        cancel = "❌ Bekor qilish"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(auto, callback_data="phone:auto")],
        [InlineKeyboardButton(manual, callback_data="phone:manual")],
        [
            InlineKeyboardButton(back, callback_data="back:menu"),
            InlineKeyboardButton(cancel, callback_data="cancel"),
        ],
    ])


def phone_request_keyboard(lang):
    if lang == LANG_RU:
        text = "📞 Отправить номер телефона"
    elif lang == LANG_EN:
        text = "📞 Send phone number"
    else:
        text = "📞 Telefon raqamni yuborish"

    return ReplyKeyboardMarkup(
        [[KeyboardButton(text, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def pets_keyboard(lang, pets):
    rows = []

    for pet in pets:
        rows.append([
            InlineKeyboardButton(
                f"🐾 {pet_name(pet)} | {pet_code(pet)}",
                callback_data=f"pet:{pet.id}",
            )
        ])

    if lang == LANG_RU:
        other = "➕ Другое животное"
        back = "⬅️ Назад"
        cancel = "❌ Отмена"
    elif lang == LANG_EN:
        other = "➕ Other animal"
        back = "⬅️ Back"
        cancel = "❌ Cancel"
    else:
        other = "➕ Boshqa hayvon"
        back = "⬅️ Orqaga"
        cancel = "❌ Bekor qilish"

    rows.append([InlineKeyboardButton(other, callback_data="pet:new")])
    rows.append([
        InlineKeyboardButton(back, callback_data="back:menu"),
        InlineKeyboardButton(cancel, callback_data="cancel"),
    ])

    return InlineKeyboardMarkup(rows)


def animal_keyboard(lang, clinic=False):
    if lang == LANG_RU:
        dog, cat = "🐶 Собака", "🐱 Кошка"
        cow, horse = "🐄 Корова", "🐴 Лошадь"
        sheep, goat = "🐑 Овца", "🐐 Коза"
        bird, other = "🐦 Птица", "➕ Другое"
        back, cancel = "⬅️ Назад", "❌ Отмена"
    elif lang == LANG_EN:
        dog, cat = "🐶 Dog", "🐱 Cat"
        cow, horse = "🐄 Cow", "🐴 Horse"
        sheep, goat = "🐑 Sheep", "🐐 Goat"
        bird, other = "🐦 Bird", "➕ Other"
        back, cancel = "⬅️ Back", "❌ Cancel"
    else:
        dog, cat = "🐶 It", "🐱 Mushuk"
        cow, horse = "🐄 Sigir", "🐴 Ot"
        sheep, goat = "🐑 Qo‘y", "🐐 Echki"
        bird, other = "🐦 Qush", "➕ Boshqa"
        back, cancel = "⬅️ Orqaga", "❌ Bekor qilish"

    if clinic:
        rows = [
            [
                InlineKeyboardButton(dog, callback_data="animal:dog"),
                InlineKeyboardButton(cat, callback_data="animal:cat"),
            ],
            [InlineKeyboardButton(other, callback_data="animal:other")],
            [
                InlineKeyboardButton(back, callback_data="back:pets"),
                InlineKeyboardButton(cancel, callback_data="cancel"),
            ],
        ]
    else:
        rows = [
            [
                InlineKeyboardButton(dog, callback_data="animal:dog"),
                InlineKeyboardButton(cat, callback_data="animal:cat"),
            ],
            [
                InlineKeyboardButton(cow, callback_data="animal:cow"),
                InlineKeyboardButton(horse, callback_data="animal:horse"),
            ],
            [
                InlineKeyboardButton(sheep, callback_data="animal:sheep"),
                InlineKeyboardButton(goat, callback_data="animal:goat"),
            ],
            [
                InlineKeyboardButton(bird, callback_data="animal:bird"),
                InlineKeyboardButton(other, callback_data="animal:other"),
            ],
            [
                InlineKeyboardButton(back, callback_data="back:pets"),
                InlineKeyboardButton(cancel, callback_data="cancel"),
            ],
        ]

    return InlineKeyboardMarkup(rows)


def skip_keyboard(lang):
    if lang == LANG_RU:
        skip = "⏭ Пропустить"
        back = "⬅️ Назад"
        cancel = "❌ Отмена"
    elif lang == LANG_EN:
        skip = "⏭ Skip"
        back = "⬅️ Back"
        cancel = "❌ Cancel"
    else:
        skip = "⏭ O‘tkazib yuborish"
        back = "⬅️ Orqaga"
        cancel = "❌ Bekor qilish"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(skip, callback_data="name:skip")],
        [
            InlineKeyboardButton(back, callback_data="back:animal_type"),
            InlineKeyboardButton(cancel, callback_data="cancel"),
        ],
    ])


def location_choice_keyboard(lang, has_old_address):
    if lang == LANG_RU:
        old = "📌 Предыдущий адрес"
        auto = "📍 Отправить геолокацию"
        manual = "✍️ Написать адрес"
        back = "⬅️ Назад"
        cancel = "❌ Отмена"
    elif lang == LANG_EN:
        old = "📌 Previous address"
        auto = "📍 Send location"
        manual = "✍️ Write address"
        back = "⬅️ Back"
        cancel = "❌ Cancel"
    else:
        old = "📌 Oldingi manzil"
        auto = "📍 Joylashuv yuborish"
        manual = "✍️ Manzil yozish"
        back = "⬅️ Orqaga"
        cancel = "❌ Bekor qilish"

    rows = []

    if has_old_address:
        rows.append([InlineKeyboardButton(old, callback_data="location:old")])

    rows.append([InlineKeyboardButton(auto, callback_data="location:auto")])
    rows.append([InlineKeyboardButton(manual, callback_data="location:manual")])
    rows.append([
        InlineKeyboardButton(back, callback_data="back:after_animal"),
        InlineKeyboardButton(cancel, callback_data="cancel"),
    ])

    return InlineKeyboardMarkup(rows)


def location_request_keyboard(lang):
    if lang == LANG_RU:
        text = "📍 Отправить геолокацию"
    elif lang == LANG_EN:
        text = "📍 Send location"
    else:
        text = "📍 Joylashuvni yuborish"

    return ReplyKeyboardMarkup(
        [[KeyboardButton(text, request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def danger_keyboard(lang):
    if lang == LANG_RU:
        rows = [
            [InlineKeyboardButton("☠️ Мёртвое животное", callback_data="danger:dead")],
            [InlineKeyboardButton("🐕 Агрессивное животное", callback_data="danger:aggressive")],
            [InlineKeyboardButton("🦠 Подозрение на инфекцию", callback_data="danger:infection")],
            [InlineKeyboardButton("⚠️ Другое", callback_data="danger:other")],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="back:menu"),
                InlineKeyboardButton("❌ Отмена", callback_data="cancel"),
            ],
        ]
    elif lang == LANG_EN:
        rows = [
            [InlineKeyboardButton("☠️ Dead animal", callback_data="danger:dead")],
            [InlineKeyboardButton("🐕 Aggressive animal", callback_data="danger:aggressive")],
            [InlineKeyboardButton("🦠 Suspected infection", callback_data="danger:infection")],
            [InlineKeyboardButton("⚠️ Other", callback_data="danger:other")],
            [
                InlineKeyboardButton("⬅️ Back", callback_data="back:menu"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
            ],
        ]
    else:
        rows = [
            [InlineKeyboardButton("☠️ O‘lik hayvon", callback_data="danger:dead")],
            [InlineKeyboardButton("🐕 Tajovuzkor hayvon", callback_data="danger:aggressive")],
            [InlineKeyboardButton("🦠 Yuqumli kasallik gumoni", callback_data="danger:infection")],
            [InlineKeyboardButton("⚠️ Boshqa xavfli holat", callback_data="danger:other")],
            [
                InlineKeyboardButton("⬅️ Orqaga", callback_data="back:menu"),
                InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel"),
            ],
        ]

    return InlineKeyboardMarkup(rows)


# =========================
# DATABASE FUNCTIONS
# =========================

@sync_to_async
def get_or_create_owner(user, lang):
    owner = Owner.objects.filter(telegram_id=user.id).first()

    if owner:
        changed = False

        if model_has_field(Owner, "telegram_username") and user.username:
            owner.telegram_username = user.username
            changed = True

        if model_has_field(Owner, "language"):
            owner.language = lang
            changed = True

        if changed:
            owner.save()

        return owner

    data = {"telegram_id": user.id}

    if model_has_field(Owner, "telegram_username"):
        data["telegram_username"] = user.username

    if model_has_field(Owner, "full_name"):
        data["full_name"] = ""

    if model_has_field(Owner, "phone"):
        data["phone"] = ""

    if model_has_field(Owner, "language"):
        data["language"] = lang

    return Owner.objects.create(**data)


@sync_to_async
def update_owner_name(owner_id, full_name):
    owner = Owner.objects.get(id=owner_id)
    owner.full_name = full_name.strip()
    owner.save()
    return owner


@sync_to_async
def update_owner_phone(owner_id, phone):
    owner = Owner.objects.get(id=owner_id)
    owner.phone = normalize_phone(phone)
    owner.save()
    return owner


@sync_to_async
def get_owner_pets(owner_id, clinic=False):
    qs = Pet.objects.filter(owner_id=owner_id).order_by("-created_at")

    if clinic:
        qs = qs.filter(animal_type__in=["dog", "cat", "other"])

    return list(qs)


@sync_to_async
def get_pet(owner_id, pet_id):
    return Pet.objects.filter(id=pet_id, owner_id=owner_id).first()


@sync_to_async
def create_pet(owner_id, animal_type, name):
    data = {
        "owner_id": owner_id,
        "animal_type": valid_animal_type(animal_type),
    }

    if model_has_field(Pet, "name"):
        data["name"] = name or ""

    return Pet.objects.create(**data)


@sync_to_async
def get_last_address_for_owner(owner_id):
    owner = Owner.objects.filter(id=owner_id).first()

    if not owner:
        return ""

    if model_has_field(Owner, "address"):
        owner_address = getattr(owner, "address", "") or ""
        if owner_address.strip():
            return owner_address.strip()

    last_patient = (
        NewPatient.objects
        .filter(
            telegram_id=owner.telegram_id,
            note__icontains="Manzil:",
        )
        .exclude(note__icontains="Manzil: Klinika ichida")
        .order_by("-created_at")
        .first()
    )

    if not last_patient:
        return ""

    return address_from_note(last_patient.note)


@sync_to_async
def create_application(owner_id, pet_id=None, service_type=SERVICE_CLINIC, address="", latitude=None, longitude=None, danger_type=""):
    """
    Telegram botdan ariza yaratadi.

    Muhim: eski bazada NewPatient.telegram_id unique bo‘lsa, bir foydalanuvchi
    ikkinchi marta ariza yuborganda IntegrityError chiqadi. Shuning uchun bu
    funksiya avval yangi ariza yaratishga urinadi. Agar telegram_id unique xatosi
    chiqsa, bot yiqilmasligi uchun shu foydalanuvchining mavjud NewPatient
    yozuvini yangi ariza ma’lumotlari bilan yangilaydi.

    Eng to‘g‘ri yechim: models.py da NewPatient.telegram_id dan unique=True ni
    olib tashlash va migration qilish. Lekin bu fallback hozirgi bazada ham botni
    ishlatib turadi.
    """
    owner = Owner.objects.get(id=owner_id)
    pet = Pet.objects.filter(id=pet_id).first() if pet_id else None

    if service_type == SERVICE_CLINIC:
        service_label = "Klinikada davolash"
        problem = "Klinikada davolash uchun Telegram bot orqali ariza yuborildi."
        address_text = "Klinika ichida"
    elif service_type == SERVICE_VET_CALL:
        service_label = "Veterinar chaqirish"
        problem = "Veterinar chaqirish uchun Telegram bot orqali ariza yuborildi."
        address_text = address or "Manzil kiritilmagan"
    else:
        service_label = "Xavfli holat"
        problem = "Xavfli holat bo‘yicha Telegram bot orqali xabar yuborildi."
        address_text = address or "Manzil kiritilmagan"

    note_parts = [
        "Telegram bot orqali yuborilgan ariza",
        f"Xizmat turi: {service_label}",
        f"Muammo tavsifi / izoh: {problem}",
        format_location_note(address_text, latitude, longitude),
    ]

    if danger_type:
        note_parts.append(f"Xavf turi: {danger_type}")

    animal_name = pet_name(pet) if pet else ""
    animal_type = valid_animal_type(pet.animal_type if pet else "other")

    data = {
        "full_name": owner.full_name or "Telegram foydalanuvchi",
        "phone": owner.phone or "",
        "telegram_id": owner.telegram_id,
        "animal_name": animal_name,
        "animal_type": animal_type,
        "selected_doctor": None,
        "status": "new",
        "note": "\n".join(str(item) for item in note_parts if item),
    }

    if model_has_field(NewPatient, "telegram_username"):
        data["telegram_username"] = getattr(owner, "telegram_username", None)

    created_new = True

    try:
        patient = NewPatient.objects.create(**data)
    except IntegrityError as exc:
        # patients_newpatient.telegram_id UNIQUE bo‘lib qolgan eski bazalar uchun.
        if "telegram_id" not in str(exc):
            raise

        patient = (
            NewPatient.objects
            .filter(telegram_id=owner.telegram_id)
            .order_by("-id")
            .first()
        )

        if not patient:
            raise

        for field_name, value in data.items():
            if model_has_field(NewPatient, field_name):
                setattr(patient, field_name, value)

        patient.save()
        created_new = False

    if service_type in [SERVICE_VET_CALL, SERVICE_DANGER] and address:
        if model_has_field(Owner, "address"):
            owner.address = address
            owner.save()

    return {
        "code": getattr(patient, "patient_code", None) or f"BEM-{patient.id:06d}",
        "pet_code": pet_code(pet),
        "created_new": created_new,
    }


# =========================
# NAVIGATION HELPERS
# =========================

async def safe_edit(query, text, keyboard=None):
    await query.answer()
    await query.edit_message_text(text=text, reply_markup=keyboard)


async def show_main_menu_from_query(query, context):
    lang = get_lang(context)
    await safe_edit(query, tr(lang, "menu"), main_keyboard(lang))
    return MAIN_MENU


async def show_after_user_data_from_query(query, context, owner):
    lang = get_lang(context)
    service = context.user_data.get("service")

    if service == SERVICE_DANGER:
        await safe_edit(query, tr(lang, "danger_type"), danger_keyboard(lang))
        return DANGER_TYPE

    clinic = service == SERVICE_CLINIC
    pets = await get_owner_pets(owner.id, clinic=clinic)

    if pets:
        await safe_edit(query, tr(lang, "pet_choice"), pets_keyboard(lang, pets))
        return PET_CHOICE

    await safe_edit(query, tr(lang, "animal_type"), animal_keyboard(lang, clinic=clinic))
    return ANIMAL_TYPE


async def show_after_user_data_from_message(message, context, owner):
    lang = get_lang(context)
    service = context.user_data.get("service")

    if service == SERVICE_DANGER:
        await message.reply_text(
            tr(lang, "danger_type"),
            reply_markup=danger_keyboard(lang),
        )
        return DANGER_TYPE

    clinic = service == SERVICE_CLINIC
    pets = await get_owner_pets(owner.id, clinic=clinic)

    if pets:
        await message.reply_text(
            tr(lang, "pet_choice"),
            reply_markup=pets_keyboard(lang, pets),
        )
        return PET_CHOICE

    await message.reply_text(
        tr(lang, "animal_type"),
        reply_markup=animal_keyboard(lang, clinic=clinic),
    )
    return ANIMAL_TYPE


async def show_location_choice(query_or_message, context):
    lang = get_lang(context)
    old_address = await get_last_address_for_owner(context.user_data["owner_id"])
    context.user_data["old_address"] = old_address

    if old_address:
        text = tr(lang, "location_with_old", address=old_address)
    else:
        text = tr(lang, "location_without_old")

    keyboard = location_choice_keyboard(lang, bool(old_address))

    if hasattr(query_or_message, "edit_message_text"):
        await query_or_message.edit_message_text(text=text, reply_markup=keyboard)
    else:
        await query_or_message.reply_text(text, reply_markup=keyboard)

    return LOCATION_CHOICE


# =========================
# FLOW
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "🔄 Bot ishga tushdi.",
        reply_markup=ReplyKeyboardRemove(),
    )

    await update.message.reply_text(
        tr(LANG_UZ, "choose_language"),
        reply_markup=language_keyboard(),
    )

    return LANGUAGE


async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "lang:uz":
        lang = LANG_UZ
    elif query.data == "lang:ru":
        lang = LANG_RU
    elif query.data == "lang:en":
        lang = LANG_EN
    else:
        lang = LANG_UZ

    is_change_language = bool(context.user_data.get("change_language_mode"))
    context.user_data["lang"] = lang
    context.user_data.pop("change_language_mode", None)

    owner = await get_or_create_owner(query.from_user, lang)
    context.user_data["owner_id"] = owner.id

    name = getattr(owner, "full_name", "") or query.from_user.first_name or ""

    if is_change_language:
        text = tr(lang, "language_changed")
    else:
        text = tr(lang, "welcome", name=name)

    await query.edit_message_text(
        text=text,
        reply_markup=main_keyboard(lang),
    )

    return MAIN_MENU


async def change_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["change_language_mode"] = True

    await query.edit_message_text(
        text=tr(get_lang(context), "choose_language"),
        reply_markup=language_keyboard(),
    )

    return LANGUAGE


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = get_lang(context)
    owner = await get_or_create_owner(query.from_user, lang)
    context.user_data["owner_id"] = owner.id

    if query.data == "service:clinic":
        context.user_data["service"] = SERVICE_CLINIC
    elif query.data == "service:vet_call":
        context.user_data["service"] = SERVICE_VET_CALL
    elif query.data == "service:danger":
        context.user_data["service"] = SERVICE_DANGER
    else:
        await query.edit_message_text(tr(lang, "menu"), reply_markup=main_keyboard(lang))
        return MAIN_MENU

    if not getattr(owner, "full_name", ""):
        await query.edit_message_text(
            text=tr(lang, "ask_full_name"),
            reply_markup=back_cancel_keyboard(lang, "menu"),
        )
        return FULL_NAME

    if not getattr(owner, "phone", ""):
        await query.edit_message_text(
            text=tr(lang, "phone_choice"),
            reply_markup=phone_choice_keyboard(lang),
        )
        return PHONE_CHOICE

    return await show_after_user_data_from_query(query, context, owner)


async def full_name_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    owner = await update_owner_name(context.user_data["owner_id"], update.message.text)

    if not getattr(owner, "phone", ""):
        await update.message.reply_text(
            tr(lang, "phone_choice"),
            reply_markup=phone_choice_keyboard(lang),
        )
        return PHONE_CHOICE

    return await show_after_user_data_from_message(update.message, context, owner)


async def full_name_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query.data == "cancel":
        return await cancel_flow(update, context)

    if query.data == "back:menu":
        return await show_main_menu_from_query(query, context)

    return FULL_NAME


async def phone_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = get_lang(context)

    if query.data == "cancel":
        return await cancel_flow(update, context)

    if query.data == "back:menu":
        return await show_main_menu_from_query(query, context)

    if query.data == "phone:manual":
        await query.edit_message_text(
            text=tr(lang, "phone_text"),
            reply_markup=back_cancel_keyboard(lang, "phone_choice"),
        )
        await query.message.reply_text(
            "⌨️",
            reply_markup=ReplyKeyboardRemove(),
        )
        return PHONE_TEXT

    if query.data == "phone:auto":
        await query.message.reply_text(
            tr(lang, "send_contact_message"),
            reply_markup=phone_request_keyboard(lang),
        )
        return PHONE_CHOICE

    return PHONE_CHOICE


async def phone_contact_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)

    if update.message.contact:
        phone_value = update.message.contact.phone_number
    else:
        phone_value = update.message.text or ""

    owner = await update_owner_phone(context.user_data["owner_id"], phone_value)

    await update.message.reply_text(
        "✅",
        reply_markup=ReplyKeyboardRemove(),
    )

    return await show_after_user_data_from_message(update.message, context, owner)


async def phone_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    owner = await update_owner_phone(context.user_data["owner_id"], update.message.text)
    await update.message.reply_text("✅", reply_markup=ReplyKeyboardRemove())
    return await show_after_user_data_from_message(update.message, context, owner)


async def phone_text_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query.data == "cancel":
        return await cancel_flow(update, context)

    if query.data == "back:phone_choice":
        lang = get_lang(context)
        await safe_edit(query, tr(lang, "phone_choice"), phone_choice_keyboard(lang))
        return PHONE_CHOICE

    return PHONE_TEXT


async def pet_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = get_lang(context)

    if query.data == "cancel":
        return await cancel_flow(update, context)

    if query.data == "back:menu":
        return await show_main_menu_from_query(query, context)

    if query.data == "pet:new":
        clinic = context.user_data.get("service") == SERVICE_CLINIC
        await query.edit_message_text(
            text=tr(lang, "animal_type"),
            reply_markup=animal_keyboard(lang, clinic=clinic),
        )
        return ANIMAL_TYPE

    if query.data.startswith("pet:"):
        pet_id = int(query.data.split(":")[1])
        pet = await get_pet(context.user_data["owner_id"], pet_id)

        if not pet:
            await query.edit_message_text(
                text=tr(lang, "pet_choice"),
                reply_markup=main_keyboard(lang),
            )
            return MAIN_MENU

        context.user_data["pet_id"] = pet.id

        if context.user_data.get("service") == SERVICE_CLINIC:
            return await finish_application_from_query(query, context)

        return await show_location_choice(query, context)

    return PET_CHOICE


async def animal_type_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = get_lang(context)

    if query.data == "cancel":
        return await cancel_flow(update, context)

    if query.data == "back:pets":
        owner = await get_or_create_owner(query.from_user, lang)
        return await show_after_user_data_from_query(query, context, owner)

    if query.data.startswith("animal:"):
        context.user_data["animal_type"] = query.data.split(":")[1]

        await query.edit_message_text(
            text=tr(lang, "animal_name"),
            reply_markup=skip_keyboard(lang),
        )
        return ANIMAL_NAME

    return ANIMAL_TYPE


async def animal_name_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()

    pet = await create_pet(
        owner_id=context.user_data["owner_id"],
        animal_type=context.user_data.get("animal_type", "other"),
        name=name,
    )

    context.user_data["pet_id"] = pet.id

    if context.user_data.get("service") == SERVICE_CLINIC:
        return await finish_application_from_message(update.message, context)

    return await show_location_choice(update.message, context)


async def animal_name_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = get_lang(context)

    if query.data == "cancel":
        return await cancel_flow(update, context)

    if query.data == "back:animal_type":
        clinic = context.user_data.get("service") == SERVICE_CLINIC
        await query.edit_message_text(
            text=tr(lang, "animal_type"),
            reply_markup=animal_keyboard(lang, clinic=clinic),
        )
        return ANIMAL_TYPE

    if query.data == "name:skip":
        pet = await create_pet(
            owner_id=context.user_data["owner_id"],
            animal_type=context.user_data.get("animal_type", "other"),
            name="",
        )

        context.user_data["pet_id"] = pet.id

        if context.user_data.get("service") == SERVICE_CLINIC:
            return await finish_application_from_query(query, context)

        return await show_location_choice(query, context)

    return ANIMAL_NAME


async def danger_type_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = get_lang(context)

    if query.data == "cancel":
        return await cancel_flow(update, context)

    if query.data == "back:menu":
        return await show_main_menu_from_query(query, context)

    danger_map = {
        "danger:dead": "O‘lik hayvon",
        "danger:aggressive": "Tajovuzkor hayvon",
        "danger:infection": "Yuqumli kasallik gumoni",
        "danger:other": "Boshqa xavfli holat",
    }

    context.user_data["danger_type"] = danger_map.get(query.data, "Boshqa xavfli holat")

    return await show_location_choice(query, context)


async def location_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = get_lang(context)

    if query.data == "cancel":
        return await cancel_flow(update, context)

    if query.data == "back:after_animal":
        owner = await get_or_create_owner(query.from_user, lang)
        return await show_after_user_data_from_query(query, context, owner)

    if query.data == "location:old":
        old_address = context.user_data.get("old_address", "")
        context.user_data["address"] = old_address
        context.user_data["latitude"] = None
        context.user_data["longitude"] = None
        return await finish_application_from_query(query, context)

    if query.data == "location:manual":
        await query.edit_message_text(
            text=tr(lang, "address_text"),
            reply_markup=back_cancel_keyboard(lang, "location_choice"),
        )
        await query.message.reply_text("⌨️", reply_markup=ReplyKeyboardRemove())
        return ADDRESS_TEXT

    if query.data == "location:auto":
        await query.message.reply_text(
            tr(lang, "send_location_message"),
            reply_markup=location_request_keyboard(lang),
        )
        return LOCATION_CHOICE

    return LOCATION_CHOICE


async def location_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.location:
        context.user_data["address"] = "Telegram orqali joylashuv yuborildi"
        context.user_data["latitude"] = Decimal(str(update.message.location.latitude))
        context.user_data["longitude"] = Decimal(str(update.message.location.longitude))

        return await finish_application_from_message(update.message, context)

    return LOCATION_CHOICE


async def address_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["address"] = update.message.text.strip()
    context.user_data["latitude"] = None
    context.user_data["longitude"] = None

    return await finish_application_from_message(update.message, context)


async def address_text_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query.data == "cancel":
        return await cancel_flow(update, context)

    if query.data == "back:location_choice":
        return await show_location_choice(query, context)

    return ADDRESS_TEXT


def success_text(lang, service, result):
    if service == SERVICE_CLINIC:
        return tr(lang, "success_clinic", code=result["code"], pet_code=result["pet_code"])

    if service == SERVICE_VET_CALL:
        return tr(lang, "success_vet", code=result["code"], pet_code=result["pet_code"], phone=CLINIC_PHONE)

    return tr(lang, "success_danger", code=result["code"])


def error_text(lang):
    if lang == LANG_RU:
        return "❌ Заявка не была сохранена. Попробуйте ещё раз или нажмите /start."
    if lang == LANG_EN:
        return "❌ The request was not saved. Try again or press /start."
    return "❌ Ariza saqlanmadi. Qayta urinib ko‘ring yoki /start bosing."


async def finish_application_from_query(query, context):
    lang = get_lang(context)

    try:
        result = await create_application(
            owner_id=context.user_data["owner_id"],
            pet_id=context.user_data.get("pet_id"),
            service_type=context.user_data.get("service"),
            address=context.user_data.get("address", ""),
            latitude=context.user_data.get("latitude"),
            longitude=context.user_data.get("longitude"),
            danger_type=context.user_data.get("danger_type", ""),
        )
    except Exception:
        await query.message.reply_text(
            error_text(lang),
            reply_markup=main_keyboard(lang),
        )
        return MAIN_MENU

    text = success_text(lang, context.user_data.get("service"), result)

    await query.message.reply_text(
        text,
        reply_markup=main_keyboard(lang),
    )

    return MAIN_MENU


async def finish_application_from_message(message, context):
    lang = get_lang(context)

    try:
        result = await create_application(
            owner_id=context.user_data["owner_id"],
            pet_id=context.user_data.get("pet_id"),
            service_type=context.user_data.get("service"),
            address=context.user_data.get("address", ""),
            latitude=context.user_data.get("latitude"),
            longitude=context.user_data.get("longitude"),
            danger_type=context.user_data.get("danger_type", ""),
        )
    except Exception:
        await message.reply_text(
            error_text(lang),
            reply_markup=main_keyboard(lang),
        )
        return MAIN_MENU

    text = success_text(lang, context.user_data.get("service"), result)

    await message.reply_text(
        text,
        reply_markup=ReplyKeyboardRemove(),
    )

    await message.reply_text(
        tr(lang, "menu"),
        reply_markup=main_keyboard(lang),
    )

    return MAIN_MENU


async def cancel_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data.clear()
    context.user_data["lang"] = lang

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text=tr(lang, "cancelled"),
            reply_markup=main_keyboard(lang),
        )
    else:
        await update.message.reply_text(
            tr(lang, "cancelled"),
            reply_markup=main_keyboard(lang),
        )

    return MAIN_MENU


# =========================
# COMMAND
# =========================

class Command(BaseCommand):
    help = "Telegram botni ishga tushirish"

    def handle(self, *args, **options):
        token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")

        if not token:
            raise CommandError("TELEGRAM_BOT_TOKEN yoki BOT_TOKEN .env faylda topilmadi.")

        app = ApplicationBuilder().token(token).build()

        conversation = ConversationHandler(
            entry_points=[
                CommandHandler("start", start),
            ],
            states={
                LANGUAGE: [
                    CallbackQueryHandler(choose_language, pattern="^lang:"),
                ],
                MAIN_MENU: [
                    CallbackQueryHandler(change_language_callback, pattern="^change_language$"),
                    CallbackQueryHandler(main_menu, pattern="^service:"),
                    CallbackQueryHandler(cancel_flow, pattern="^cancel$"),
                ],
                FULL_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, full_name_message),
                    CallbackQueryHandler(full_name_callback, pattern="^(back:menu|cancel)$"),
                ],
                PHONE_CHOICE: [
                    CallbackQueryHandler(phone_choice_callback, pattern="^(phone:|back:menu|cancel)"),
                    MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), phone_contact_message),
                ],
                PHONE_TEXT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, phone_text_message),
                    CallbackQueryHandler(phone_text_callback, pattern="^(back:phone_choice|cancel)$"),
                ],
                PET_CHOICE: [
                    CallbackQueryHandler(pet_choice, pattern="^(pet:|back:menu|cancel)"),
                ],
                ANIMAL_TYPE: [
                    CallbackQueryHandler(animal_type_choice, pattern="^(animal:|back:pets|cancel)"),
                ],
                ANIMAL_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, animal_name_message),
                    CallbackQueryHandler(animal_name_callback, pattern="^(name:skip|back:animal_type|cancel)$"),
                ],
                DANGER_TYPE: [
                    CallbackQueryHandler(danger_type_choice, pattern="^(danger:|back:menu|cancel)"),
                ],
                LOCATION_CHOICE: [
                    CallbackQueryHandler(location_choice_callback, pattern="^(location:|back:after_animal|cancel)"),
                    MessageHandler(filters.LOCATION, location_message),
                ],
                ADDRESS_TEXT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, address_text_message),
                    CallbackQueryHandler(address_text_callback, pattern="^(back:location_choice|cancel)$"),
                ],
            },
            fallbacks=[
                CommandHandler("start", start),
                CallbackQueryHandler(cancel_flow, pattern="^cancel$"),
            ],
            allow_reentry=True,
        )

        app.add_handler(conversation)

        self.stdout.write(
            self.style.SUCCESS("Telegram bot ishga tushdi. CTRL+C bilan to‘xtating.")
        )

        app.run_polling()