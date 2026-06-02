import json
import math
import os
import tempfile
import textwrap

import asyncio

from datetime import timedelta
from decimal import Decimal, InvalidOperation
from html import escape
from urllib.parse import quote_plus

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.translation import gettext as _

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from patients.models import (
    NewPatient,
    DoctorProfile,
    LabResult,
    DiagnosticResult,
    Owner,
    Pet,
    Visit,
)
from patients.telegram import send_telegram_document
from patients.utils.pdf import generate_visit_pdf
from patients.utils.telegram_pdf import send_visit_pdf_to_telegram as send_visit_pdf_document_async

# =========================
# UMUMIY YORDAMCHI FUNKSIYALAR
# =========================

def user_in_group(user, group_name):
    return user.groups.filter(name=group_name).exists()


def custom_logout(request):
    logout(request)
    return redirect("login")


def normalize_service_type(service_type):
    if service_type == "call":
        return "vet_call"

    if service_type in ["clinic", "vet_call", "danger"]:
        return service_type

    return "clinic"


ADMIN_SERVICE_LABELS = {
    "clinic": _("Klinikada davolash"),
    "vet_call": _("Veterinar chaqirish"),
    "danger": _("Xavfli holatlar"),
}

SERVICE_LABELS = ADMIN_SERVICE_LABELS

LOCATION_ACTIVE_MINUTES = 3
LOCATION_STALE_MINUTES = 15
CLINIC_LATITUDE = float(os.getenv("CLINIC_LATITUDE", "41.5500"))
CLINIC_LONGITUDE = float(os.getenv("CLINIC_LONGITUDE", "60.6333"))
CLINIC_RADIUS_METERS = 120
CUSTOMER_NEAR_RADIUS_METERS = 300
ARRIVAL_RADIUS_METERS = 100

IN_PROGRESS_MARKER = "[VET_STATUS:in_progress]"
ACCEPTED_MARKER = "[VET_STATUS:accepted]"
ON_WAY_MARKER = "[VET_STATUS:on_way]"
ARRIVED_MARKER = "[VET_STATUS:arrived]"
VET_STAGE_MARKERS = [
    IN_PROGRESS_MARKER,
    ACCEPTED_MARKER,
    ON_WAY_MARKER,
    ARRIVED_MARKER,
]

VET_STAGE_CONFIG = {
    "accepted": {
        "marker": ACCEPTED_MARKER,
        "label": _("Qabul qildi"),
        "status": "accepted",
        "message": _("Ariza qabul qilindi."),
    },
    "in_progress": {
        "marker": IN_PROGRESS_MARKER,
        "label": _("Jarayonga oldi"),
        "status": "accepted",
        "message": _("Ariza jarayonga olindi."),
    },
    "on_way": {
        "marker": ON_WAY_MARKER,
        "label": _("Yo‘lga chiqdi"),
        "status": "en_route",
        "message": _("Yo‘lga chiqish belgilandi."),
    },
    "arrived": {
        "marker": ARRIVED_MARKER,
        "label": _("Yetib bordi"),
        "status": "arrived",
        "message": _("Yetib borish belgilandi."),
    },
}
PDF_CAPTIONS = {
    "uz": {
        "title": "Yakuniy ko‘rik PDF xulosasi",
        "code": "Ko‘rik kodi",
    },
    "ru": {
        "title": "Итоговое PDF заключение осмотра",
        "code": "Код осмотра",
    },
    "en": {
        "title": "Final checkup PDF report",
        "code": "Visit code",
    },
}

def get_note_value(note, label):
    prefix = f"{label}:"

    for line in (note or "").splitlines():
        if line.strip().startswith(prefix):
            return line.split(":", 1)[1].strip()

    return ""


def get_application_note_value(note, label):
    return get_note_value(note, label)


def get_patient_service_type(patient):
    note = patient.note or ""

    if getattr(patient, "service_type", "") in ["vet_call", "danger"]:
        return patient.service_type

    if "Xavfli holat" in note:
        return "danger"

    if "Veterinar chaqirish" in note:
        return "vet_call"

    return getattr(patient, "service_type", "") or "clinic"


def get_application_service_type(patient):
    return get_patient_service_type(patient)


def build_map_url(address_text):
    if not address_text:
        return ""

    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(address_text)}"


def build_coordinate_map_url(latitude, longitude):
    if latitude is None or longitude is None:
        return ""

    return f"https://www.google.com/maps?q={latitude},{longitude}"


def build_coordinate_embed_url(latitude, longitude):
    if latitude is None or longitude is None:
        return ""

    return f"https://www.google.com/maps?q={latitude},{longitude}&output=embed"


def build_directions_url(origin_latitude, origin_longitude, destination_latitude, destination_longitude):
    if None in [origin_latitude, origin_longitude, destination_latitude, destination_longitude]:
        return ""

    return (
        "https://www.google.com/maps/dir/?api=1"
        f"&origin={origin_latitude},{origin_longitude}"
        f"&destination={destination_latitude},{destination_longitude}"
    )


def parse_decimal_coordinate(value):
    if value in [None, ""]:
        return None

    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def parse_note_coordinate(note, label):
    raw_value = get_note_value(note, label)
    return parse_decimal_coordinate(raw_value)


def get_patient_latitude(patient):
    return patient.latitude or parse_note_coordinate(patient.note, "Latitude")


def get_patient_longitude(patient):
    return patient.longitude or parse_note_coordinate(patient.note, "Longitude")


def get_patient_address_text(patient):
    return patient.address_text or get_note_value(patient.note, "Manzil")


def haversine_distance_meters(lat1, lon1, lat2, lon2):
    if None in [lat1, lon1, lat2, lon2]:
        return None

    radius = 6371000
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    delta_phi = math.radians(float(lat2) - float(lat1))
    delta_lambda = math.radians(float(lon2) - float(lon1))
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def format_distance(distance_meters):
    if distance_meters is None:
        return "-"

    if distance_meters < 1000:
        return _("%(meters)d m") % {"meters": int(round(distance_meters))}

    return _("%(kilometers).1f km") % {"kilometers": distance_meters / 1000}


def estimate_travel_minutes(distance_meters):
    if distance_meters is None:
        return None

    # City-speed fallback for UI estimates when Google Maps API is not used.
    return max(1, int(math.ceil(distance_meters / 350)))


def format_travel_minutes(minutes):
    if minutes is None:
        return "-"

    return _("%(minutes)d daqiqa") % {"minutes": minutes}


def get_doctor_location_status(doctor):
    if not doctor or not doctor.location_tracking_enabled or not doctor.last_location_updated_at:
        return {
            "label": _("🔴 Aloqa yo‘q"),
            "short_label": _("Aloqa yo‘q"),
            "class": "status-cancelled",
            "state": "offline",
        }

    age = timezone.now() - doctor.last_location_updated_at

    if age <= timedelta(minutes=LOCATION_ACTIVE_MINUTES):
        return {
            "label": _("🟢 Faol"),
            "short_label": _("Faol"),
            "class": "status-completed",
            "state": "active",
        }

    if age <= timedelta(minutes=LOCATION_STALE_MINUTES):
        return {
            "label": _("🟡 Eskirgan"),
            "short_label": _("Eskirgan"),
            "class": "status-pending",
            "state": "stale",
        }

    return {
        "label": _("🔴 Aloqa yo‘q"),
        "short_label": _("Aloqa yo‘q"),
        "class": "status-cancelled",
        "state": "offline",
    }


def get_note_datetime(note, label):
    raw_value = get_note_value(note, label)

    if not raw_value:
        return None

    try:
        return timezone.datetime.strptime(raw_value, "%d.%m.%Y %H:%M").replace(
            tzinfo=timezone.get_current_timezone()
        )
    except ValueError:
        return None


def get_vet_timeline(patient):
    steps = [
        ("assigned", _("Biriktirilgan"), patient.created_at),
        ("accepted", _("Qabul qilingan"), get_note_datetime(patient.note, VET_STAGE_CONFIG["accepted"]["label"])),
    ]

    if patient.can_travel:
        steps.extend([
            ("on_way", _("Yo‘lda"), get_note_datetime(patient.note, VET_STAGE_CONFIG["on_way"]["label"])),
            ("arrived", _("Yetib bordi"), get_note_datetime(patient.note, VET_STAGE_CONFIG["arrived"]["label"])),
        ])
    else:
        steps.append(
            ("in_progress", _("Jarayonda"), get_note_datetime(patient.note, VET_STAGE_CONFIG["in_progress"]["label"]))
        )

    steps.append(("completed", _("Yakunlandi"), patient.updated_at if patient.status == "completed" else None))

    return [
        {
            "key": key,
            "label": label,
            "time": event_time,
            "is_done": bool(event_time),
        }
        for key, label, event_time in steps
    ]


def get_compact_status(patient):
    status_map = {
        "new": {"label": _("Yangi"), "icon": "🆕", "class": "status-new"},
        "assigned_to_vet": {"label": _("Biriktirilgan"), "icon": "👨‍⚕️", "class": "status-assigned"},
        "accepted": {"label": _("Qabul qildi"), "icon": "✅", "class": "status-assigned"},
        "en_route": {"label": _("Yo‘lda"), "icon": "📍", "class": "status-new"},
        "arrived": {"label": _("Yetib bordi"), "icon": "📌", "class": "status-completed"},
        "sent_to_lab": {"label": _("Jarayonda"), "icon": "🔄", "class": "status-pending"},
        "sent_to_diagnostic": {"label": _("Jarayonda"), "icon": "🔄", "class": "status-pending"},
        "returned_to_vet": {"label": _("Jarayonda"), "icon": "🔄", "class": "status-pending"},
        "completed": {"label": _("Yakunlandi"), "icon": "✅", "class": "status-completed"},
        "cancelled": {"label": _("Bekor"), "icon": "❌", "class": "status-cancelled"},
        "rejected": {"label": _("Bekor"), "icon": "❌", "class": "status-cancelled"},
    }

    return status_map.get(
        patient.status,
        {"label": patient.get_status_display(), "icon": "🔄", "class": "status-pending"},
    )


def enrich_admin_application(patient):
    patient.service_type = get_application_service_type(patient)
    patient.service_label = ADMIN_SERVICE_LABELS.get(patient.service_type, ADMIN_SERVICE_LABELS["clinic"])
    patient.address_text = get_patient_address_text(patient)
    patient.latitude_value = get_patient_latitude(patient)
    patient.longitude_value = get_patient_longitude(patient)
    patient.problem_text = get_application_note_value(patient.note, "Muammo tavsifi / izoh")
    patient.compact_status = get_compact_status(patient)
    patient.map_url = (
        build_coordinate_map_url(patient.latitude_value, patient.longitude_value)
        or build_map_url(patient.address_text)
    )
    return patient


def has_vet_marker(patient, marker):
    return marker in (patient.note or "")


def append_vet_stage(patient, stage):
    stage_order = {
        "accepted": ["accepted"],
        "in_progress": ["accepted", "in_progress"],
        "on_way": ["accepted", "on_way"],
        "arrived": ["accepted", "on_way", "arrived"],
    }
    note = patient.note or ""

    for stage_name in stage_order.get(stage, [stage]):
        config = VET_STAGE_CONFIG[stage_name]

        if config["marker"] not in note:
            now_text = timezone.now().strftime("%d.%m.%Y %H:%M")
            note = f"{note}\n{config['marker']}\n{config['label']}: {now_text}".strip()

    patient.note = note
    patient.status = VET_STAGE_CONFIG[stage]["status"]
    patient.save()
    update_doctor_dynamic_status(patient.selected_doctor)


def remove_vet_stage_markers(note):
    cleaned_note = note or ""

    for marker in VET_STAGE_MARKERS:
        cleaned_note = cleaned_note.replace(marker, "")

    return cleaned_note.strip()


def mark_arrived_if_near_patient(doctor_profile):
    if not doctor_profile or doctor_profile.last_latitude is None or doctor_profile.last_longitude is None:
        return []

    arrived_codes = []
    active_patients = NewPatient.objects.filter(
        selected_doctor=doctor_profile,
    ).exclude(
        status__in=["new", "completed", "cancelled", "arrived"]
    )

    for patient in active_patients:
        enriched_patient = enrich_vet_patient(patient)

        if not enriched_patient.can_travel or not enriched_patient.is_on_way:
            continue

        distance = haversine_distance_meters(
            doctor_profile.last_latitude,
            doctor_profile.last_longitude,
            enriched_patient.latitude_value,
            enriched_patient.longitude_value,
        )

        if distance is not None and distance <= ARRIVAL_RADIUS_METERS:
            append_vet_stage(patient, "arrived")
            arrived_codes.append(patient.patient_code)

    return arrived_codes


def enrich_vet_patient(patient):
    patient.service_type = get_patient_service_type(patient)
    patient.service_label = SERVICE_LABELS.get(patient.service_type, SERVICE_LABELS["clinic"])
    patient.address_text = get_patient_address_text(patient)
    patient.latitude_value = get_patient_latitude(patient)
    patient.longitude_value = get_patient_longitude(patient)
    patient.problem_text = (
        get_note_value(patient.note, "Muammo tavsifi / izoh")
        or get_note_value(patient.note, "Xizmat turi")
        or patient.note
        or "-"
    )
    patient.map_url = (
        build_coordinate_map_url(patient.latitude_value, patient.longitude_value)
        or build_map_url(patient.address_text)
    )
    patient.map_embed_url = build_coordinate_embed_url(patient.latitude_value, patient.longitude_value)
    patient.route_distance = None
    patient.route_distance_text = "-"
    patient.directions_url = ""

    if patient.selected_doctor:
        doctor_latitude = patient.selected_doctor.last_latitude
        doctor_longitude = patient.selected_doctor.last_longitude
        patient.route_distance = haversine_distance_meters(
            doctor_latitude,
            doctor_longitude,
            patient.latitude_value,
            patient.longitude_value,
        )
        patient.route_distance_text = format_distance(patient.route_distance)
        patient.directions_url = build_directions_url(
            doctor_latitude,
            doctor_longitude,
            patient.latitude_value,
            patient.longitude_value,
        )

    patient.can_travel = patient.service_type in ["vet_call", "danger"]
    patient.estimated_minutes = estimate_travel_minutes(patient.route_distance)
    patient.estimated_minutes_text = format_travel_minutes(patient.estimated_minutes)
    patient.estimated_arrival_time = (
        timezone.localtime(timezone.now() + timedelta(minutes=patient.estimated_minutes)).strftime("%H:%M")
        if patient.estimated_minutes is not None
        else "-"
    )
    patient.is_accepted = (
        has_vet_marker(patient, ACCEPTED_MARKER)
        or patient.status in ["accepted", "en_route", "arrived"]
    )
    patient.is_in_progress = has_vet_marker(patient, IN_PROGRESS_MARKER)
    patient.is_on_way = has_vet_marker(patient, ON_WAY_MARKER) or patient.status == "en_route"
    patient.is_arrived = has_vet_marker(patient, ARRIVED_MARKER) or patient.status == "arrived"

    if patient.status == "completed":
        patient.display_status = _("Yakunlandi")
    elif patient.status == "cancelled":
        patient.display_status = _("Bekor")
    elif patient.is_arrived:
        patient.display_status = _("Yetib bordi")
    elif patient.is_on_way:
        patient.display_status = _("Yo‘lda")
    elif patient.is_in_progress:
        patient.display_status = _("Jarayonda")
    elif patient.is_accepted:
        patient.display_status = _("Qabul qildi")
    elif patient.status == "assigned_to_vet":
        patient.display_status = _("Biriktirilgan")
    else:
        patient.display_status = patient.get_status_display()

    return patient


def get_vet_status(active_patients):
    active = [
        patient for patient in active_patients
        if patient.status not in ["completed", "cancelled"]
    ]

    if not active:
        return _("Bo‘sh")

    if any(patient.service_type == "danger" for patient in active):
        return _("Band")

    if any(patient.service_type == "vet_call" for patient in active):
        return _("Chaqiruvda")

    return _("Klinikada")


def get_doctor_status_code(active_patients):
    active = [
        patient for patient in active_patients
        if patient.status not in ["completed", "cancelled"]
    ]

    if not active:
        return "free"

    if any(patient.service_type == "danger" for patient in active):
        return "busy"

    if any(patient.service_type == "vet_call" for patient in active):
        return "on_call"

    return "clinic"


def update_doctor_dynamic_status(doctor):
    if not doctor:
        return

    active_patients = [
        enrich_vet_patient(patient)
        for patient in NewPatient.objects.filter(selected_doctor=doctor).exclude(status__in=["new", "completed", "cancelled"])
    ]
    status_code = get_doctor_status_code(active_patients)

    if getattr(doctor, "current_status", None) != status_code:
        doctor.current_status = status_code
        doctor.save(update_fields=["current_status"])


def get_vet_patient_or_403(request, patient_id):
    patient = NewPatient.objects.select_related("selected_doctor").get(id=patient_id)

    if request.user.is_superuser:
        return patient

    doctor_profile = DoctorProfile.objects.filter(user=request.user, is_active=True).first()

    if not doctor_profile or patient.selected_doctor != doctor_profile:
        return None

    return patient


def redirect_back_to_vet_dashboard(request):
    return redirect(request.META.get("HTTP_REFERER") or "veterinar_dashboard")


def get_vet_base_patients(request, include_new=False):
    doctor_profile = DoctorProfile.objects.filter(user=request.user, is_active=True).first()

    if request.user.is_superuser:
        qs = NewPatient.objects.all()
    elif doctor_profile:
        qs = NewPatient.objects.filter(selected_doctor=doctor_profile)
    else:
        qs = NewPatient.objects.none()

    if not include_new:
        qs = qs.exclude(status__in=["new", "cancelled"])

    return doctor_profile, qs


def is_recent_for_reassign(patient):
    return patient.created_at.date() >= timezone.localdate() - timedelta(days=1)


def is_recent_for_extra_visit(patient):
    return timezone.now() - patient.updated_at <= timedelta(days=3)


def get_admin_doctor_status(doctor):
    active_patients = NewPatient.objects.filter(
        selected_doctor=doctor
    ).exclude(
        status__in=["new", "completed", "cancelled"]
    )

    if not active_patients.exists():
        return {
            "label": _("Bo‘sh"),
            "class": "status-completed",
            "icon": "fa-solid fa-circle",
        }

    if active_patients.filter(Q(service_type="danger") | Q(note__icontains="Xavfli holat")).exists():
        return {
            "label": _("Band"),
            "class": "status-cancelled",
            "icon": "fa-solid fa-circle",
        }

    if active_patients.filter(Q(service_type="vet_call") | Q(note__icontains="Veterinar chaqirish")).exists():
        return {
            "label": _("Xizmatda"),
            "class": "status-pending",
            "icon": "fa-solid fa-circle",
        }

    return {
        "label": _("Mijoz qabulida"),
        "class": "status-assigned",
        "icon": "fa-solid fa-circle",
    }


def get_admin_doctor_select_status(doctor):
    active_patients = [
        enrich_vet_patient(patient)
        for patient in NewPatient.objects.filter(selected_doctor=doctor)
        .exclude(status__in=["new", "completed", "cancelled"])
        .order_by("-updated_at")
    ]

    travel_task = next(
        (
            patient
            for patient in active_patients
            if patient.service_type in ["vet_call", "danger"]
            and patient.status in ["en_route", "arrived"]
        ),
        None,
    )

    danger_task = next(
        (
            patient
            for patient in active_patients
            if patient.service_type == "danger"
            and patient.status not in ["en_route", "arrived"]
        ),
        None,
    )

    call_task = next(
        (
            patient
            for patient in active_patients
            if patient.service_type == "vet_call"
            and patient.status not in ["en_route", "arrived"]
        ),
        None,
    )

    if travel_task:
        return {
            "label": _("Safarda / %(code)s") % {"code": travel_task.patient_code},
            "class": "status-pending",
            "risk": "busy",
            "warning": _("Tanlangan veterinar hozir safarda."),
        }

    if danger_task:
        return {
            "label": _("Xavfli ariza / %(code)s") % {"code": danger_task.patient_code},
            "class": "status-cancelled",
            "risk": "busy",
            "warning": _("Tanlangan veterinarga xavfli ariza biriktirilgan."),
        }

    if call_task:
        return {
            "label": _("Chaqiruv biriktirilgan / %(code)s") % {"code": call_task.patient_code},
            "class": "status-pending",
            "risk": "on_call",
            "warning": _("Tanlangan veterinarga chaqiruv biriktirilgan."),
        }

    if active_patients:
        return {
            "label": _("Klinikada / band"),
            "class": "status-assigned",
            "risk": "clinic_busy",
            "warning": _("Tanlangan veterinar klinikada boshqa ariza bilan band."),
        }

    location_status = get_doctor_location_status(doctor)

    if location_status["state"] == "offline":
        return {
            "label": _("Aloqa yo‘q"),
            "class": "status-cancelled",
            "risk": "offline",
            "warning": _("Tanlangan veterinarning geolokatsiya aloqasi yo‘q."),
        }

    return {
        "label": _("Klinikada / bo‘sh"),
        "class": "status-completed",
        "risk": "",
        "warning": "",
    }


def get_admin_doctor_options():
    options = []

    for doctor in DoctorProfile.objects.filter(is_active=True).order_by("full_name"):
        status = get_admin_doctor_select_status(doctor)
        options.append({
            "profile": doctor,
            "status": status,
            "label": f"{doctor.full_name} — {status['label']}",
        })

    return options


def generate_manual_telegram_id():
    last_manual_patient = NewPatient.objects.filter(
        telegram_id__lt=0
    ).order_by("telegram_id").first()

    if not last_manual_patient:
        return -1

    return last_manual_patient.telegram_id - 1


# =========================
# DASHBOARD HOME / COMMON
# =========================

@login_required
def dashboard_home(request):
    user = request.user

    if user.is_superuser:
        return redirect("/admin/")

    if user_in_group(user, "Administrator"):
        return redirect("administrator_dashboard")

    if user_in_group(user, "Veterinar"):
        return redirect("veterinar_dashboard")

    if user_in_group(user, "Laboratoriya"):
        return redirect("laboratoriya_dashboard")

    if user_in_group(user, "Diagnostika"):
        return redirect("diagnostika_dashboard")

    return HttpResponseForbidden(
        _("Sizga dashboard uchun rol biriktirilmagan. Superadmin bilan bog‘laning.")
    )


@login_required
def patients_status(request):
    user = request.user

    if user.is_superuser or user_in_group(user, "Administrator"):
        patients = NewPatient.objects.all().order_by("-updated_at")

    elif user_in_group(user, "Veterinar"):
        doctor_profile = DoctorProfile.objects.filter(user=user, is_active=True).first()

        if not doctor_profile:
            return HttpResponseForbidden(_("Sizga veterinar profili biriktirilmagan."))

        patients = NewPatient.objects.filter(selected_doctor=doctor_profile).order_by("-updated_at")

    elif user_in_group(user, "Laboratoriya"):
        patients = NewPatient.objects.filter(lab_results__isnull=False).distinct().order_by("-updated_at")

    elif user_in_group(user, "Diagnostika"):
        patients = NewPatient.objects.filter(diagnostic_results__isnull=False).distinct().order_by("-updated_at")

    else:
        return HttpResponseForbidden(_("Sizda bemorlar holatini ko‘rish huquqi yo‘q."))

    return render(request, "dashboard/patients_status.html", {"patients": patients})


@login_required
def patient_card(request, patient_id):
    try:
        patient = NewPatient.objects.select_related("selected_doctor").get(id=patient_id)
    except NewPatient.DoesNotExist:
        messages.error(request, _("Bemor topilmadi."))
        return redirect("dashboard_home")

    user = request.user
    doctor_profile = None

    if user.is_superuser or user_in_group(user, "Administrator"):
        pass

    elif user_in_group(user, "Veterinar"):
        doctor_profile = DoctorProfile.objects.filter(user=user, is_active=True).first()

        if not doctor_profile or patient.selected_doctor != doctor_profile:
            return HttpResponseForbidden(_("Sizda bu bemor kartasini ko‘rish huquqi yo‘q."))

    elif user_in_group(user, "Laboratoriya"):
        if not LabResult.objects.filter(patient=patient).exists():
            return HttpResponseForbidden(_("Sizda bu bemor kartasini ko‘rish huquqi yo‘q."))

    elif user_in_group(user, "Diagnostika"):
        if not DiagnosticResult.objects.filter(patient=patient).exists():
            return HttpResponseForbidden(_("Sizda bu bemor kartasini ko‘rish huquqi yo‘q."))

    else:
        return HttpResponseForbidden(_("Sizda bu sahifaga kirish huquqi yo‘q."))

    lab_results = LabResult.objects.filter(patient=patient).select_related(
        "veterinarian",
        "lab_worker",
    ).order_by("-updated_at")

    diagnostic_results = DiagnosticResult.objects.filter(patient=patient).select_related(
        "lab_result",
        "diagnostic_worker",
        "lab_updated_by",
    ).order_by("-updated_at")

    visits = Visit.objects.filter(new_patient=patient).select_related(
        "doctor",
        "pet",
    ).order_by("-created_at")

    can_finish_visit = False

    if user.is_superuser:
        can_finish_visit = patient.status != "completed" or is_recent_for_extra_visit(patient)

    elif user_in_group(user, "Veterinar"):
        if doctor_profile is None:
            doctor_profile = DoctorProfile.objects.filter(user=user, is_active=True).first()

        can_finish_visit = (
            doctor_profile is not None
            and patient.selected_doctor == doctor_profile
            and (patient.status != "completed" or is_recent_for_extra_visit(patient))
        )

    context = {
        "patient": patient,
        "lab_results": lab_results,
        "diagnostic_results": diagnostic_results,
        "visits": visits,
        "back_url": request.META.get("HTTP_REFERER", "/dashboard/"),
        "can_finish_visit": can_finish_visit,
        "finish_mode": request.GET.get("finish") == "1",
    }

    return render(request, "dashboard/patient_card.html", context)


# =========================
# ADMINISTRATOR
# =========================

@login_required
def administrator_dashboard(request):
    if not user_in_group(request.user, "Administrator") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda Administrator dashboardiga kirish huquqi yo‘q."))

    raw_service_filter = request.GET.get("service", "").strip()
    service_filter = normalize_service_type(raw_service_filter) if raw_service_filter else ""
    new_patients = NewPatient.objects.filter(status="new")

    if service_filter == "clinic":
        new_patients = new_patients.filter(
            service_type="clinic"
        ).exclude(
            Q(note__icontains="Veterinar chaqirish") | Q(note__icontains="Xavfli holat")
        )
    elif service_filter == "vet_call":
        new_patients = new_patients.filter(
            Q(service_type="vet_call") | Q(note__icontains="Veterinar chaqirish")
        )
    elif service_filter == "danger":
        new_patients = new_patients.filter(
            Q(service_type="danger") | Q(note__icontains="Xavfli holat")
        )
    else:
        service_filter = ""

    new_patients = [
        enrich_admin_application(patient)
        for patient in new_patients.order_by("-created_at")
    ]

    doctors = DoctorProfile.objects.filter(is_active=True).order_by("full_name")
    doctor_options = get_admin_doctor_options()
    delayed_call_threshold = timezone.now() - timedelta(minutes=30)

    admin_stats = {
        "today": NewPatient.objects.filter(created_at__date=timezone.localdate()).count(),
        "new": NewPatient.objects.filter(status="new").count(),
        "in_progress": NewPatient.objects.exclude(status__in=["new", "completed", "cancelled"]).count(),
        "completed": NewPatient.objects.filter(status="completed").count(),
        "active_doctors": doctors.count(),
        "delayed_calls": NewPatient.objects.filter(
            Q(service_type="vet_call") | Q(service_type="danger") | Q(note__icontains="Veterinar chaqirish") | Q(note__icontains="Xavfli holat"),
            created_at__lt=delayed_call_threshold,
        ).exclude(status__in=["completed", "cancelled"]).count(),
    }

    context = {
        "new_patients": new_patients,
        "doctors": doctors,
        "doctor_options": doctor_options,
        "admin_stats": admin_stats,
        "animal_types": NewPatient.ANIMAL_TYPES,
        "active_service_filter": service_filter,
        "active_service_filter_title": ADMIN_SERVICE_LABELS.get(service_filter),
        "today_date": timezone.localdate().isoformat(),
    }

    return render(request, "dashboard/administrator.html", context)


@login_required
def create_quick_application(request):
    if not user_in_group(request.user, "Administrator") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda bu amalni bajarish huquqi yo‘q."))

    if request.method != "POST":
        return redirect("administrator_dashboard")

    full_name = request.POST.get("full_name", "").strip()
    phone = request.POST.get("phone", "").strip()
    animal_type = request.POST.get("animal_type", "").strip()
    animal_name = request.POST.get("animal_name", "").strip()
    service_type = normalize_service_type(request.POST.get("service_type", "").strip())
    address = request.POST.get("address", "").strip()
    description = request.POST.get("description", "").strip()

    if not full_name or not phone or not animal_type or not animal_name or not service_type:
        messages.error(request, _("Tezkor ariza uchun majburiy maydonlarni to‘ldiring."))
        return redirect("administrator_dashboard")

    if service_type in ["vet_call", "danger"] and not address:
        messages.error(request, _("Veterinar chaqirish yoki xavfli holat uchun manzil kiritilishi kerak."))
        return redirect("administrator_dashboard")

    note_parts = [
        _("Telefon orqali kiritilgan ariza"),
        _("Xizmat turi: %(service)s") % {"service": ADMIN_SERVICE_LABELS[service_type]},
    ]

    if address:
        note_parts.append(_("Manzil: %(address)s") % {"address": address})

    if description:
        note_parts.append(_("Muammo tavsifi / izoh: %(description)s") % {"description": description})

    NewPatient.objects.create(
        full_name=full_name,
        phone=phone,
        telegram_id=generate_manual_telegram_id(),
        telegram_username=None,
        animal_name=animal_name,
        animal_type=animal_type,
        service_type=service_type,
        address_text=address or ("Klinika ichida" if service_type == "clinic" else ""),
        selected_doctor=None,
        status="new",
        note="\n".join(str(part) for part in note_parts),
    )

    messages.success(request, _("Tezkor ariza yangi arizalar ro‘yxatiga qo‘shildi."))
    return redirect("administrator_dashboard")


@login_required
def assign_patient_to_vet(request, patient_id):
    if not user_in_group(request.user, "Administrator") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda bu amalni bajarish huquqi yo‘q."))

    if request.method == "POST":
        doctor_id = request.POST.get("doctor_id")

        try:
            patient = NewPatient.objects.get(id=patient_id)
            doctor = DoctorProfile.objects.get(id=doctor_id, is_active=True)

            patient.selected_doctor = doctor
            patient.status = "assigned_to_vet"
            patient.save()
            update_doctor_dynamic_status(doctor)

            doctor_status = get_admin_doctor_select_status(doctor)

            if doctor_status.get("warning"):
                messages.warning(request, doctor_status["warning"])

            messages.success(
                request,
                _("%(patient)s bemori %(doctor)s veterinarga yuborildi.") % {
                    "patient": patient.full_name,
                    "doctor": doctor.full_name,
                },
            )

        except NewPatient.DoesNotExist:
            messages.error(request, _("Bemor topilmadi."))

        except DoctorProfile.DoesNotExist:
            messages.error(request, _("Veterinar topilmadi."))

    return redirect("administrator_dashboard")


@login_required
def cancel_patient(request, patient_id):
    if not user_in_group(request.user, "Administrator") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda bu amalni bajarish huquqi yo‘q."))

    if request.method == "POST":
        try:
            patient = NewPatient.objects.get(id=patient_id)
            doctor = patient.selected_doctor

            if patient.status == "completed":
                messages.error(request, _("Yakunlangan bemorni bekor qilib bo‘lmaydi."))
                return redirect("administrator_dashboard")

            patient.status = "cancelled"
            patient.save()
            update_doctor_dynamic_status(doctor)

            messages.success(request, _("%(patient)s bemori bekor qilindi.") % {"patient": patient.full_name})

        except NewPatient.DoesNotExist:
            messages.error(request, _("Bemor topilmadi."))

    return redirect("administrator_dashboard")


@login_required
def redirect_patient_to_vet(request, patient_id):
    if not user_in_group(request.user, "Administrator") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda bu amalni bajarish huquqi yo‘q."))

    if request.method == "POST":
        doctor_id = request.POST.get("doctor_id")

        try:
            patient = NewPatient.objects.get(id=patient_id)
            doctor = DoctorProfile.objects.get(id=doctor_id, is_active=True)
            old_doctor = patient.selected_doctor

            if patient.status == "completed":
                messages.error(request, _("Yakunlangan bemorni qayta yo‘naltirib bo‘lmaydi."))
                return redirect("administrator_dashboard")

            patient.selected_doctor = doctor
            patient.status = "assigned_to_vet"
            patient.save()
            update_doctor_dynamic_status(old_doctor)
            update_doctor_dynamic_status(doctor)

            messages.success(
                request,
                _("%(patient)s bemori %(doctor)s veterinarga qayta yo‘naltirildi.") % {
                    "patient": patient.full_name,
                    "doctor": doctor.full_name,
                },
            )

        except NewPatient.DoesNotExist:
            messages.error(request, _("Bemor topilmadi."))

        except DoctorProfile.DoesNotExist:
            messages.error(request, _("Veterinar topilmadi."))

    return redirect("administrator_dashboard")


def enrich_history_application(patient):
    enrich_admin_application(patient)
    patient.can_reassign = (
        is_recent_for_reassign(patient)
        and patient.status not in ["completed", "cancelled"]
    )
    patient.action_summary = _("Ariza yaratildi")

    if patient.status == "assigned_to_vet" and patient.selected_doctor:
        patient.action_summary = _("Veterinarga biriktirildi")
    elif patient.status == "completed":
        patient.action_summary = _("Ariza yakunlandi")
    elif patient.status == "cancelled":
        patient.action_summary = _("Ariza bekor qilindi")
    elif patient.status in ["sent_to_lab", "sent_to_diagnostic", "returned_to_vet", "accepted"]:
        patient.action_summary = _("Jarayonda")

    return patient


@login_required
def admin_history(request):
    if not user_in_group(request.user, "Administrator") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda Tarix sahifasiga kirish huquqi yo‘q."))

    query = request.GET.get("q", "").strip()
    date_filter = request.GET.get("date", "").strip()
    parsed_date = parse_date(date_filter)

    applications = NewPatient.objects.select_related("selected_doctor").all()

    if parsed_date:
        applications = applications.filter(created_at__date=parsed_date)
    else:
        date_filter = ""

    if query:
        applications = applications.filter(
            Q(patient_code__icontains=query)
            | Q(full_name__icontains=query)
            | Q(phone__icontains=query)
            | Q(animal_name__icontains=query)
            | Q(note__icontains=query)
            | Q(selected_doctor__full_name__icontains=query)
        )

    applications = [
        enrich_history_application(patient)
        for patient in applications.order_by("-updated_at")
    ]

    context = {
        "applications": applications,
        "owners": Owner.objects.all().order_by("-created_at")[:12],
        "pets": Pet.objects.select_related("owner").order_by("-created_at")[:12],
        "doctors": DoctorProfile.objects.filter(is_active=True).order_by("full_name"),
        "query": query,
        "date_filter": date_filter,
        "all_count": NewPatient.objects.count(),
        "owners_count": Owner.objects.count(),
        "pets_count": Pet.objects.count(),
        "completed_count": NewPatient.objects.filter(status="completed").count(),
        "cancelled_count": NewPatient.objects.filter(status="cancelled").count(),
    }

    return render(request, "dashboard/admin_history.html", context)


@login_required
def admin_history_redirect_patient(request, patient_id):
    if not user_in_group(request.user, "Administrator") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda bu amalni bajarish huquqi yo‘q."))

    if request.method == "POST":
        doctor_id = request.POST.get("doctor_id")

        try:
            patient = NewPatient.objects.get(id=patient_id)

            if not is_recent_for_reassign(patient):
                messages.error(request, _("Eski arizalarni qayta biriktirib bo‘lmaydi."))
                return redirect("admin_history")

            if patient.status in ["completed", "cancelled"]:
                messages.error(request, _("Yakunlangan yoki bekor qilingan arizani qayta biriktirib bo‘lmaydi."))
                return redirect("admin_history")

            doctor = DoctorProfile.objects.get(id=doctor_id, is_active=True)
            old_doctor = patient.selected_doctor
            patient.selected_doctor = doctor
            patient.status = "assigned_to_vet"
            patient.save()
            update_doctor_dynamic_status(old_doctor)
            update_doctor_dynamic_status(doctor)

            messages.success(
                request,
                _("%(patient)s arizasi %(doctor)s veterinarga qayta biriktirildi.") % {
                    "patient": patient.full_name,
                    "doctor": doctor.full_name,
                },
            )

        except NewPatient.DoesNotExist:
            messages.error(request, _("Bemor topilmadi."))

        except DoctorProfile.DoesNotExist:
            messages.error(request, _("Veterinar topilmadi."))

    return redirect("admin_history")


@login_required
def admin_staff_location(request):
    if not user_in_group(request.user, "Administrator") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda Administrator sahifasiga kirish huquqi yo‘q."))

    doctors = []

    for doctor in DoctorProfile.objects.filter(is_active=True).order_by("full_name"):
        active_patients = NewPatient.objects.filter(selected_doctor=doctor).exclude(
            status__in=["new", "completed", "cancelled"]
        ).order_by("-updated_at")
        active_count = active_patients.count()
        current_task = enrich_vet_patient(active_patients.first()) if active_count else None
        location_status = get_doctor_location_status(doctor)

        doctor_latitude = doctor.last_latitude
        doctor_longitude = doctor.last_longitude
        clinic_distance = haversine_distance_meters(
            doctor_latitude,
            doctor_longitude,
            CLINIC_LATITUDE,
            CLINIC_LONGITUDE,
        )

        customer_latitude = get_patient_latitude(current_task) if current_task else None
        customer_longitude = get_patient_longitude(current_task) if current_task else None
        customer_distance = haversine_distance_meters(
            doctor_latitude,
            doctor_longitude,
            customer_latitude,
            customer_longitude,
        )

        map_url = build_coordinate_map_url(doctor_latitude, doctor_longitude)
        if not map_url and current_task:
            map_url = current_task.map_url

        movement_status = location_status.copy()

        if location_status["state"] == "active" and current_task:
            on_way_time = get_note_datetime(current_task.note, "Yo‘lga chiqdi")
            is_still_at_clinic = (
                clinic_distance is not None
                and clinic_distance <= CLINIC_RADIUS_METERS
            )

            if customer_distance is not None and customer_distance <= CUSTOMER_NEAR_RADIUS_METERS:
                movement_status = {
                    "label": _("🟢 Manzilga yaqin"),
                    "short_label": _("Manzilga yaqin"),
                    "class": "status-completed",
                    "state": "near_customer",
                }
            elif current_task.is_on_way and is_still_at_clinic:
                late_from_clinic = (
                    on_way_time is not None
                    and timezone.now() - on_way_time >= timedelta(minutes=15)
                )
                movement_status = {
                    "label": _("🟡 Hali klinikada, kechikmoqda"),
                    "short_label": _("Hali klinikada"),
                    "class": "status-cancelled" if late_from_clinic else "status-pending",
                    "state": "still_clinic_late" if late_from_clinic else "still_clinic",
                }
            elif current_task.is_on_way:
                movement_status = {
                    "label": _("🔵 Yo‘lda"),
                    "short_label": _("Yo‘lda"),
                    "class": "status-new",
                    "state": "on_way",
                }

        doctors.append({
            "profile": doctor,
            "status": get_admin_doctor_status(doctor),
            "active_count": active_count,
            "current_task": current_task,
            "location_status": location_status,
            "movement_status": movement_status,
            "last_location_at": doctor.last_location_updated_at,
            "clinic_distance": format_distance(clinic_distance),
            "customer_distance": format_distance(customer_distance),
            "map_url": map_url,
        })

    return render(request, "dashboard/admin_staff_location.html", {"doctors": doctors})


@login_required
def admin_settings(request):
    if not user_in_group(request.user, "Administrator") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda Administrator sahifasiga kirish huquqi yo‘q."))

    return render(request, "dashboard/admin_settings.html")


@login_required
def admin_profile(request):
    if not user_in_group(request.user, "Administrator") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda Administrator sahifasiga kirish huquqi yo‘q."))

    context = {
        "new_count": NewPatient.objects.filter(status="new").count(),
        "completed_count": NewPatient.objects.filter(status="completed").count(),
    }

    return render(request, "dashboard/admin_profile.html", context)


# =========================
# VETERINAR
# =========================

@login_required
def veterinar_dashboard(request):
    if not user_in_group(request.user, "Veterinar") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda Veterinar dashboardiga kirish huquqi yo‘q."))

    doctor_profile, base_patients = get_vet_base_patients(request)
    raw_service_filter = request.GET.get("service", "").strip()
    service_filter = normalize_service_type(raw_service_filter) if raw_service_filter else ""
    scope_filter = request.GET.get("scope", "").strip()

    completed_total_count = base_patients.filter(status="completed").count()

    active_qs = base_patients.exclude(status="completed").order_by("-created_at")

    if scope_filter == "today":
        active_qs = base_patients.filter(
            created_at__date=timezone.localdate()
        ).exclude(status="cancelled").order_by("-created_at")
    elif scope_filter == "in_progress":
        active_qs = base_patients.exclude(
            status__in=["new", "assigned_to_vet", "completed", "cancelled"]
        ).order_by("-updated_at")
    active_patients = [enrich_vet_patient(patient) for patient in active_qs]
    update_doctor_dynamic_status(doctor_profile)

    if service_filter not in SERVICE_LABELS:
        service_filter = ""

    filtered_active_patients = [
        patient for patient in active_patients
        if not service_filter or patient.service_type == service_filter
    ]

    today_count = base_patients.filter(created_at__date=timezone.localdate()).count()
    in_progress_count = sum(1 for patient in active_patients if patient.is_in_progress or patient.is_accepted)
    danger_count = sum(1 for patient in active_patients if patient.service_type == "danger")

    context = {
        "doctor_profile": doctor_profile,
        "active_patients": filtered_active_patients,
        "all_active_patients": active_patients,
        "today_count": today_count,
        "in_progress_count": in_progress_count,
        "completed_count": completed_total_count,
        "danger_count": danger_count,
        "vet_status": get_vet_status(active_patients),
        "location_status": get_doctor_location_status(doctor_profile)["label"],
        "active_service_filter": service_filter,
        "active_scope_filter": scope_filter,
        "active_service_filter_title": (
            _("Bugungi arizalarim")
            if scope_filter == "today"
            else _("Jarayondagi ishlarim")
            if scope_filter == "in_progress"
            else SERVICE_LABELS.get(service_filter)
        ),
    }

    return render(request, "dashboard/veterinar.html", context)


@login_required
def vet_update_location(request):
    if not user_in_group(request.user, "Veterinar") and not request.user.is_superuser:
        return JsonResponse({"ok": False, "error": _("Ruxsat yo‘q.")}, status=403)

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": _("Faqat POST so‘rov qabul qilinadi.")}, status=405)

    doctor_profile = DoctorProfile.objects.filter(user=request.user, is_active=True).first()

    if not doctor_profile:
        return JsonResponse({"ok": False, "error": _("Veterinar profili topilmadi.")}, status=404)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = request.POST

    latitude = parse_decimal_coordinate(payload.get("latitude"))
    longitude = parse_decimal_coordinate(payload.get("longitude"))
    accuracy = payload.get("accuracy")

    if latitude is None or longitude is None:
        return JsonResponse({"ok": False, "error": _("Lokatsiya koordinatalari noto‘g‘ri.")}, status=400)

    if not (-90 <= float(latitude) <= 90 and -180 <= float(longitude) <= 180):
        return JsonResponse({"ok": False, "error": _("Lokatsiya chegaradan tashqarida.")}, status=400)

    try:
        accuracy_value = float(accuracy) if accuracy not in [None, ""] else None
    except (TypeError, ValueError):
        accuracy_value = None

    doctor_profile.last_latitude = latitude
    doctor_profile.last_longitude = longitude
    doctor_profile.last_location_accuracy = accuracy_value
    doctor_profile.last_location_updated_at = timezone.now()
    doctor_profile.location_tracking_enabled = True
    doctor_profile.save(update_fields=[
        "last_latitude",
        "last_longitude",
        "last_location_accuracy",
        "last_location_updated_at",
        "location_tracking_enabled",
    ])

    location_status = get_doctor_location_status(doctor_profile)
    arrived_codes = mark_arrived_if_near_patient(doctor_profile)

    return JsonResponse({
        "ok": True,
        "status": location_status["short_label"],
        "status_label": location_status["label"],
        "updated_at": doctor_profile.last_location_updated_at.strftime("%d.%m.%Y %H:%M"),
        "arrived_codes": arrived_codes,
    })


@login_required
def vet_route_page(request, patient_id):
    if not user_in_group(request.user, "Veterinar") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda bu sahifani ko‘rish huquqi yo‘q."))

    try:
        patient = get_vet_patient_or_403(request, patient_id)
    except NewPatient.DoesNotExist:
        messages.error(request, _("Bemor topilmadi."))
        return redirect("veterinar_dashboard")

    if patient is None:
        return HttpResponseForbidden(_("Bu ariza sizga biriktirilmagan."))

    patient = enrich_vet_patient(patient)
    doctor_profile = patient.selected_doctor

    context = {
        "patient": patient,
        "doctor_profile": doctor_profile,
        "location_status": get_doctor_location_status(doctor_profile)["label"],
        "vet_status": get_vet_status([patient]),
    }

    return render(request, "dashboard/vet_route.html", context)


@login_required
def vet_application_detail(request, patient_id):
    if not user_in_group(request.user, "Veterinar") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda bu sahifani ko‘rish huquqi yo‘q."))

    try:
        patient = get_vet_patient_or_403(request, patient_id)
    except NewPatient.DoesNotExist:
        messages.error(request, _("Bemor topilmadi."))
        return redirect("veterinar_dashboard")

    if patient is None:
        return HttpResponseForbidden(_("Bu ariza sizga biriktirilmagan."))

    patient = enrich_vet_patient(patient)
    doctor_profile = patient.selected_doctor

    context = {
        "patient": patient,
        "doctor_profile": doctor_profile,
        "timeline": get_vet_timeline(patient),
        "location_status": get_doctor_location_status(doctor_profile)["label"],
        "vet_status": get_vet_status([patient]),
    }

    return render(request, "dashboard/vet_application_detail.html", context)


@login_required
def vet_update_application_stage(request, patient_id, stage):
    if not user_in_group(request.user, "Veterinar") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda bu amalni bajarish huquqi yo‘q."))

    if request.method != "POST":
        return redirect_back_to_vet_dashboard(request)

    if stage not in VET_STAGE_CONFIG:
        messages.error(request, _("Noto‘g‘ri amal tanlandi."))
        return redirect_back_to_vet_dashboard(request)

    try:
        patient = get_vet_patient_or_403(request, patient_id)

        if patient is None:
            return HttpResponseForbidden(_("Bu ariza sizga biriktirilmagan."))

        if patient.status == "completed":
            messages.info(request, _("Bu ariza avval yakunlangan."))
            return redirect_back_to_vet_dashboard(request)

        append_vet_stage(patient, stage)
        messages.success(request, VET_STAGE_CONFIG[stage]["message"])

    except NewPatient.DoesNotExist:
        messages.error(request, _("Bemor topilmadi."))

    return redirect_back_to_vet_dashboard(request)


@login_required
def vet_mark_in_progress(request, patient_id):
    return vet_update_application_stage(request, patient_id, "in_progress")


@login_required
def vet_complete_application(request, patient_id):
    if not user_in_group(request.user, "Veterinar") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda bu amalni bajarish huquqi yo‘q."))

    if request.method != "POST":
        return redirect("patient_card", patient_id=patient_id)

    final_conclusion = request.POST.get("final_conclusion", "").strip()
    recommendation = request.POST.get("recommendation", "").strip()
    extra_note = request.POST.get("extra_note", "").strip()
    final_action = request.POST.get("final_action", "complete_send")

    if final_action not in ["save_only", "complete", "complete_send"]:
        final_action = "complete_send"

    if not final_conclusion:
        messages.error(request, _("Umumiy xulosa yozilishi kerak."))
        return redirect(f"/dashboard/patient-card/{patient_id}/?finish=1#final-exam")

    try:
        patient = get_vet_patient_or_403(request, patient_id)

        if patient is None:
            return HttpResponseForbidden(_("Bu ariza sizga biriktirilmagan."))

        if patient.status == "completed" and not is_recent_for_extra_visit(patient):
            messages.error(request, _("Bu arizaga qo‘shimcha ko‘rik yozish muddati tugagan."))
            return redirect("patient_card", patient_id=patient.id)

        now_text = timezone.now().strftime("%d.%m.%Y %H:%M")

        telegram_text = (
            "✅ <b>Arizangiz yakunlandi</b>\n\n"
            f"👨‍⚕️ <b>Veterinar:</b> {escape(request.user.get_full_name() or request.user.username)}\n"
            f"🐾 <b>Hayvon:</b> {escape(patient.animal_name or '-')}\n\n"
            f"📋 <b>Umumiy xulosa:</b>\n{escape(final_conclusion)}"
        )

        if recommendation:
            telegram_text += f"\n\n💊 <b>Tavsiya:</b>\n{escape(recommendation)}"

        if extra_note:
            telegram_text += f"\n\n📝 <b>Qo‘shimcha izoh:</b>\n{escape(extra_note)}"

        note_parts = [
            patient.note or "",
            (
                _("Veterinar xulosasi saqlandi: %(date)s")
                if final_action == "save_only"
                else _("Veterinar ko‘rigi yakunlandi: %(date)s")
            ) % {"date": now_text},
            _("Umumiy xulosa: %(text)s") % {"text": final_conclusion},
        ]

        if recommendation:
            note_parts.append(_("Tavsiya: %(text)s") % {"text": recommendation})

        if extra_note:
            note_parts.append(_("Qo‘shimcha izoh: %(text)s") % {"text": extra_note})

        patient.note = "\n".join(part for part in note_parts if part).strip()

        if final_action == "save_only":
            patient.save(update_fields=["note", "updated_at"])
            messages.success(request, _("Ko‘rik xulosasi saqlandi."))
            return redirect(f"/dashboard/patient-card/{patient.id}/?finish=1#final-exam")

        visit = Visit.objects.create(
            doctor=request.user,
            new_patient=patient,
            pet=None,
            complaint=patient.note or "",
            diagnosis=final_conclusion,
            treatment=recommendation,
            message=extra_note,
            is_sent=False,
        )

        patient.note = "\n".join([
            remove_vet_stage_markers(patient.note),
            _("Ko‘rik kodi: %(code)s") % {"code": visit.visit_code},
        ]).strip()
        patient.status = "completed"
        patient.save(update_fields=["note", "status", "updated_at"])
        update_doctor_dynamic_status(patient.selected_doctor)

        if final_action == "complete":
            messages.success(request, _("Ko‘rik yakunlandi."))
            return redirect("patient_card", patient_id=patient.id)

        telegram_id = getattr(patient, "telegram_id", None)

        try:
            telegram_chat_id = int(telegram_id or 0)
        except (TypeError, ValueError):
            telegram_chat_id = 0

        if telegram_chat_id > 0:
            lab_result = LabResult.objects.filter(patient=patient).order_by("-updated_at").first()
            diagnostic_result = DiagnosticResult.objects.filter(patient=patient).order_by("-updated_at").first()
            pdf_path = None

            try:
                patient_lang = getattr(patient, "language", "uz") or "uz"
                pdf_path = generate_visit_pdf(visit, lang=patient_lang)
                caption_texts = PDF_CAPTIONS.get(patient_lang, PDF_CAPTIONS["uz"])
            
                telegram_result = send_telegram_document(
                    telegram_chat_id,
                    pdf_path,
                    caption=(
                        caption_texts["title"]
                        + f"\n{caption_texts['code']}: {visit.visit_code}"
                    ),
                )
            except Exception as exc:
                telegram_result = {
                    "ok": False,
                    "description": str(exc),
                }
            finally:
                if pdf_path and os.path.exists(pdf_path):
                    try:
                        os.remove(pdf_path)
                    except OSError:
                        pass

            if telegram_result.get("ok"):
                visit.is_sent = True
                visit.save(update_fields=["is_sent"])
                messages.success(
                    request,
                    _("Ko‘rik yakunlandi va PDF mijozga Telegram orqali yuborildi.")
                )
            else:
                messages.warning(
                    request,
                    _("Ko‘rik yakunlandi, lekin PDF Telegramga yuborilmadi: %(error)s") % {
                        "error": telegram_result.get("description", _("Noma’lum xato"))
                    }
                )
        else:
            messages.warning(
                request,
                _("Mijoz Telegram orqali ulanmagan.")
            )

        return redirect("patient_card", patient_id=patient.id)

    except NewPatient.DoesNotExist:
        messages.error(request, _("Bemor topilmadi."))

    return redirect("veterinar_dashboard")


@login_required
def vet_history(request):
    if not user_in_group(request.user, "Veterinar") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda Veterinar tarixiga kirish huquqi yo‘q."))

    doctor_profile, base_patients = get_vet_base_patients(request)
    history_date = request.GET.get("history_date", "").strip()
    query = request.GET.get("q", "").strip()
    history_qs = base_patients.filter(status="completed")
    parsed_history_date = parse_date(history_date)

    if parsed_history_date:
        history_qs = history_qs.filter(updated_at__date=parsed_history_date)
    else:
        history_date = ""

    if query:
        history_qs = history_qs.filter(
            Q(patient_code__icontains=query)
            | Q(full_name__icontains=query)
            | Q(phone__icontains=query)
            | Q(animal_name__icontains=query)
            | Q(note__icontains=query)
        )

    history_patients = [enrich_vet_patient(patient) for patient in history_qs.order_by("-updated_at")]

    context = {
        "doctor_profile": doctor_profile,
        "history_patients": history_patients,
        "applications": history_patients,
        "history_date": history_date,
        "query": query,
    }

    return render(request, "dashboard/vet_history.html", context)


@login_required
def vet_reopen_application(request, patient_id):
    if not user_in_group(request.user, "Veterinar") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda bu amalni bajarish huquqi yo‘q."))

    try:
        patient = get_vet_patient_or_403(request, patient_id)

        if patient is None:
            return HttpResponseForbidden(_("Bu ariza sizga biriktirilmagan."))

        if not is_recent_for_extra_visit(patient):
            messages.error(request, _("Faqat 2-3 kun ichidagi arizaga qo‘shimcha ko‘rik yozish mumkin."))
            return redirect("vet_history")

        return redirect(f"/dashboard/patient-card/{patient.id}/?finish=1#final-exam")

    except NewPatient.DoesNotExist:
        messages.error(request, _("Bemor topilmadi."))

    return redirect("vet_history")


@login_required
def vet_profile(request):
    if not user_in_group(request.user, "Veterinar") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda Veterinar profiliga kirish huquqi yo‘q."))

    doctor_profile, base_patients = get_vet_base_patients(request)
    active_patients = [enrich_vet_patient(patient) for patient in base_patients.exclude(status="completed")]
    update_doctor_dynamic_status(doctor_profile)

    context = {
        "doctor_profile": doctor_profile,
        "vet_status": get_vet_status(active_patients),
        "location_status": get_doctor_location_status(doctor_profile)["label"],
        "today_count": base_patients.filter(created_at__date=timezone.localdate()).count(),
        "completed_count": base_patients.filter(status="completed").count(),
        "active_count": len(active_patients),
    }

    return render(request, "dashboard/vet_profile.html", context)


# =========================
# LABORATORIYA / DIAGNOSTIKA
# =========================

@login_required
def send_patient_to_lab(request, patient_id):
    if not user_in_group(request.user, "Veterinar") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda laboratoriyaga yuborish huquqi yo‘q."))

    if request.method == "POST":
        try:
            patient = get_vet_patient_or_403(request, patient_id)

            if patient is None:
                return HttpResponseForbidden(_("Bu ariza sizga biriktirilmagan."))

            analysis_name = request.POST.get("analysis_name", "").strip() or _("Umumiy analiz")
            comment = request.POST.get("comment", "").strip()

            LabResult.objects.create(
                patient=patient,
                veterinarian=request.user,
                analysis_name=analysis_name,
                comment=comment,
                status="waiting",
            )

            patient.status = "sent_to_lab"
            patient.save(update_fields=["status", "updated_at"])

            messages.success(request, _("Bemor laboratoriyaga yuborildi."))

        except NewPatient.DoesNotExist:
            messages.error(request, _("Bemor topilmadi."))

    return redirect("veterinar_dashboard")


@login_required
def edit_vet_lab_request(request, lab_result_id):
    if not user_in_group(request.user, "Veterinar") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda bu amalni bajarish huquqi yo‘q."))

    try:
        lab_result = LabResult.objects.select_related("patient").get(id=lab_result_id)
    except LabResult.DoesNotExist:
        messages.error(request, _("Laboratoriya so‘rovi topilmadi."))
        return redirect("veterinar_dashboard")

    if request.method == "POST":
        lab_result.analysis_name = request.POST.get("analysis_name", lab_result.analysis_name).strip()
        lab_result.comment = request.POST.get("comment", lab_result.comment or "").strip()
        lab_result.save()
        messages.success(request, _("Laboratoriya so‘rovi yangilandi."))
        return redirect("patient_card", patient_id=lab_result.patient.id)

    return render(request, "dashboard/edit/edit_vet_lab_request.html", {"lab_result": lab_result})


@login_required
def laboratoriya_dashboard(request):
    if not user_in_group(request.user, "Laboratoriya") and not request.user.is_superuser:
        return redirect("administrator_dashboard")

    active_lab_results = LabResult.objects.filter(
        patient__status="sent_to_lab",
        status="waiting",
    ).select_related("patient", "veterinarian").order_by("-created_at")

    history_lab_results = LabResult.objects.exclude(
        patient__status="sent_to_lab",
        status="waiting",
    ).select_related("patient", "veterinarian", "lab_worker").order_by("-updated_at")

    return render(
        request,
        "dashboard/laboratoriya.html",
        {
            "active_lab_results": active_lab_results,
            "history_lab_results": history_lab_results,
        },
    )


@login_required
def send_lab_result_to_diagnostic(request, lab_result_id):
    if not user_in_group(request.user, "Laboratoriya") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda bu amalni bajarish huquqi yo‘q."))

    if request.method == "POST":
        try:
            lab_result = LabResult.objects.select_related("patient").get(id=lab_result_id)
            result = request.POST.get("result", "").strip()
            comment = request.POST.get("comment", "").strip()

            lab_result.result = result
            lab_result.lab_comment = comment
            lab_result.lab_worker = request.user
            lab_result.status = "sent_to_diagnostic"
            lab_result.save()

            patient = lab_result.patient
            patient.status = "sent_to_diagnostic"
            patient.save()

            DiagnosticResult.objects.create(
                patient=patient,
                lab_result=lab_result,
                diagnostic_worker=None,
                conclusion="",
                recommendation="",
                status="waiting",
            )

            messages.success(request, _("%(patient)s bemorining analiz natijasi diagnostikaga yuborildi.") % {
                "patient": patient.full_name
            })

        except LabResult.DoesNotExist:
            messages.error(request, _("Laboratoriya natijasi topilmadi."))

    return redirect("laboratoriya_dashboard")


@login_required
def edit_lab_result(request, lab_result_id):
    if not user_in_group(request.user, "Laboratoriya") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda bu amalni bajarish huquqi yo‘q."))

    try:
        lab_result = LabResult.objects.select_related("patient", "veterinarian", "lab_worker").get(id=lab_result_id)
    except LabResult.DoesNotExist:
        messages.error(request, _("Laboratoriya yozuvi topilmadi."))
        return redirect("laboratoriya_dashboard")

    if request.method == "POST":
        lab_result.result = request.POST.get("result", lab_result.result or "").strip()
        lab_result.lab_comment = request.POST.get("lab_comment", lab_result.lab_comment or "").strip()
        lab_result.lab_worker = request.user
        lab_result.save()

        diagnostics = DiagnosticResult.objects.filter(lab_result=lab_result).exclude(patient__status="completed")

        for diagnostic in diagnostics:
            diagnostic.is_lab_updated = True
            diagnostic.lab_updated_at = timezone.now()
            diagnostic.lab_updated_by = request.user
            diagnostic.save()

        messages.success(request, _("Laboratoriya natijasi tahrirlandi."))
        return redirect("laboratoriya_dashboard")

    return render(request, "dashboard/edit/edit_lab_result.html", {"lab_result": lab_result})


@login_required
def view_lab_result(request, lab_result_id):
    try:
        lab_result = LabResult.objects.select_related("patient", "veterinarian", "lab_worker").get(id=lab_result_id)
    except LabResult.DoesNotExist:
        messages.error(request, _("Laboratoriya natijasi topilmadi."))
        return redirect("dashboard_home")

    return render(
        request,
        "dashboard/view_lab_result.html",
        {
            "lab_result": lab_result,
            "patient": lab_result.patient,
            "back_url": request.META.get("HTTP_REFERER", "/dashboard/"),
            "can_edit_lab_result": request.user.is_superuser or user_in_group(request.user, "Laboratoriya"),
        },
    )


@login_required
def diagnostika_dashboard(request):
    if not user_in_group(request.user, "Diagnostika") and not request.user.is_superuser:
        return redirect("administrator_dashboard")

    active_diagnostics = DiagnosticResult.objects.filter(
        patient__status="sent_to_diagnostic",
        status="waiting",
    ).select_related("patient", "lab_result", "diagnostic_worker", "lab_updated_by").order_by("-created_at")

    history_diagnostics = DiagnosticResult.objects.exclude(
        patient__status="sent_to_diagnostic",
        status="waiting",
    ).select_related("patient", "lab_result", "diagnostic_worker", "lab_updated_by").order_by("-updated_at")

    return render(
        request,
        "dashboard/diagnostika.html",
        {
            "active_diagnostics": active_diagnostics,
            "history_diagnostics": history_diagnostics,
        },
    )


@login_required
def return_diagnostic_to_vet(request, diagnostic_id):
    if not user_in_group(request.user, "Diagnostika") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda bu amalni bajarish huquqi yo‘q."))

    if request.method == "POST":
        try:
            diagnostic = DiagnosticResult.objects.select_related("patient", "lab_result").get(id=diagnostic_id)
            diagnostic.conclusion = request.POST.get("conclusion", "").strip()
            diagnostic.recommendation = request.POST.get("recommendation", "").strip()
            diagnostic.diagnostic_worker = request.user
            diagnostic.status = "returned_to_vet"
            diagnostic.is_lab_updated = False
            diagnostic.lab_updated_at = None
            diagnostic.lab_updated_by = None
            diagnostic.save()

            patient = diagnostic.patient
            patient.status = "returned_to_vet"
            patient.save()

            messages.success(request, _("%(patient)s bemori veterinarga qaytarildi.") % {"patient": patient.full_name})

        except DiagnosticResult.DoesNotExist:
            messages.error(request, _("Diagnostika yozuvi topilmadi."))

    return redirect("diagnostika_dashboard")


@login_required
def edit_diagnostic_result(request, diagnostic_id):
    if not user_in_group(request.user, "Diagnostika") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda bu amalni bajarish huquqi yo‘q."))

    try:
        diagnostic = DiagnosticResult.objects.select_related("patient", "lab_result", "lab_updated_by").get(id=diagnostic_id)
    except DiagnosticResult.DoesNotExist:
        messages.error(request, _("Diagnostika yozuvi topilmadi."))
        return redirect("diagnostika_dashboard")

    if request.method == "POST":
        diagnostic.conclusion = request.POST.get("conclusion", diagnostic.conclusion or "").strip()
        diagnostic.recommendation = request.POST.get("recommendation", diagnostic.recommendation or "").strip()
        diagnostic.diagnostic_worker = request.user
        diagnostic.is_lab_updated = False
        diagnostic.lab_updated_at = None
        diagnostic.lab_updated_by = None
        diagnostic.save()

        messages.success(request, _("Diagnostika xulosasi tahrirlandi."))
        return redirect("diagnostika_dashboard")

    return render(request, "dashboard/edit/edit_diagnostic_result.html", {"diagnostic": diagnostic})


@login_required
def view_diagnostic_result(request, diagnostic_id):
    try:
        diagnostic = DiagnosticResult.objects.select_related("patient", "lab_result", "diagnostic_worker", "lab_updated_by").get(id=diagnostic_id)
    except DiagnosticResult.DoesNotExist:
        messages.error(request, _("Diagnostika natijasi topilmadi."))
        return redirect("dashboard_home")

    return render(
        request,
        "dashboard/view_diagnostic_result.html",
        {
            "diagnostic": diagnostic,
            "patient": diagnostic.patient,
            "lab_result": diagnostic.lab_result,
            "back_url": request.META.get("HTTP_REFERER", "/dashboard/"),
            "can_edit_diagnostic_result": request.user.is_superuser or user_in_group(request.user, "Diagnostika"),
        },
    )


# =========================
# PDF / FINAL VISIT
# =========================

def register_pdf_fonts():
    font_path = r"C:\Windows\Fonts\arial.ttf"
    bold_font_path = r"C:\Windows\Fonts\arialbd.ttf"

    try:
        pdfmetrics.registerFont(TTFont("Arial", font_path))
        pdfmetrics.registerFont(TTFont("Arial-Bold", bold_font_path))
        return "Arial", "Arial-Bold"
    except Exception:
        return "Helvetica", "Helvetica-Bold"


def create_visit_pdf(visit, lab_result=None, diagnostic_result=None):
    normal_font, bold_font = register_pdf_fonts()
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, f"{visit.visit_code}.pdf")

    c = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4
    margin = 45
    y = height - 45

    def draw_wrapped_text(text, x, y_pos, font=normal_font, size=10, gap=14, width_chars=85):
        if text is None or str(text).strip() == "":
            text = "-"

        c.setFont(font, size)
        lines = textwrap.wrap(str(text), width=width_chars)
        current_y = y_pos

        for line in lines:
            if current_y < 70:
                c.showPage()
                current_y = height - 60

            c.setFont(font, size)
            c.drawString(x, current_y, line)
            current_y -= gap

        return current_y

    c.setFont(bold_font, 18)
    c.drawString(margin, y, "VetClinic - Yakuniy ko‘rik xulosasi")
    y -= 35

    patient = visit.new_patient

    rows = [
        ("Ko‘rik kodi", visit.visit_code),
        ("Bemor kodi", patient.patient_code if patient else "-"),
        ("Mijoz", patient.full_name if patient else "-"),
        ("Telefon", patient.phone if patient else "-"),
        ("Hayvon", patient.animal_name if patient else "-"),
        ("Veterinar", visit.doctor.get_full_name() if visit.doctor else "-"),
        ("Ko‘rik vaqti", visit.created_at.strftime("%d.%m.%Y %H:%M")),
    ]

    c.setFont(normal_font, 10)

    for label, value in rows:
        c.drawString(margin, y, f"{label}: {value or '-'}")
        y -= 18

    y -= 10
    c.setFont(bold_font, 12)
    c.drawString(margin, y, "Umumiy xulosa:")
    y -= 20
    y = draw_wrapped_text(visit.diagnosis or "-", margin, y)

    y -= 10
    c.setFont(bold_font, 12)
    c.drawString(margin, y, "Tavsiya:")
    y -= 20
    y = draw_wrapped_text(visit.treatment or "-", margin, y)

    if lab_result:
        y -= 10
        c.setFont(bold_font, 12)
        c.drawString(margin, y, "Laboratoriya natijasi:")
        y -= 20
        y = draw_wrapped_text(lab_result.result or "-", margin, y)

    if diagnostic_result:
        y -= 10
        c.setFont(bold_font, 12)
        c.drawString(margin, y, "Diagnostika xulosasi:")
        y -= 20
        draw_wrapped_text(diagnostic_result.conclusion or "-", margin, y)

    c.save()
    return file_path


@login_required
def final_visit(request, patient_id):
    if not user_in_group(request.user, "Veterinar") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda bu amalni bajarish huquqi yo‘q."))

    return redirect(f"/dashboard/patient-card/{patient_id}/?finish=1#final-exam")


@login_required
def send_visit_pdf_to_telegram(request, visit_id):
    try:
        visit = Visit.objects.select_related("new_patient", "doctor").get(id=visit_id)
    except Visit.DoesNotExist:
        messages.error(request, _("Ko‘rik topilmadi."))
        return redirect("dashboard_home")

    patient = visit.new_patient

    if not patient:
        messages.error(request, _("Bemor topilmadi."))
        return redirect("dashboard_home")

    if not patient.telegram_id or int(patient.telegram_id) <= 0:
        messages.warning(request, _("Mijoz Telegram orqali ulanmagan."))
        return redirect("patient_card", patient_id=patient.id)

    lab_result = LabResult.objects.filter(patient=patient).order_by("-updated_at").first()
    diagnostic_result = DiagnosticResult.objects.filter(patient=patient).order_by("-updated_at").first()

    pdf_path = create_visit_pdf(visit, lab_result=lab_result, diagnostic_result=diagnostic_result)
    result = send_telegram_document(
        patient.telegram_id,
        pdf_path,
        caption=_("Yakuniy ko‘rik PDF xulosasi")
    )

    try:
        os.remove(pdf_path)
    except OSError:
        pass

    if result.get("ok"):
        visit.is_sent = True
        visit.save(update_fields=["is_sent"])
        messages.success(request, _("PDF Telegram orqali yuborildi."))
    else:
        messages.warning(
            request,
            _("PDF yuborilmadi: %(error)s") % {
                "error": result.get("description", _("Noma’lum xato"))
            }
        )

    return redirect("patient_card", patient_id=patient.id)


@require_POST
def complete_visit(request, visit_id):
    visit = get_object_or_404(Visit, id=visit_id)

    # Visitni yakunlash
    if hasattr(visit, "status"):
        visit.status = "completed"

    if hasattr(visit, "is_completed"):
        visit.is_completed = True

    visit.save()

    try:
        asyncio.run(send_visit_pdf_document_async(visit))
        messages.success(request, "Ko‘rik yakunlandi va PDF Telegram orqali yuborildi.")
    except Exception as exc:
        messages.warning(
            request,
            f"Ko‘rik yakunlandi, lekin PDF Telegramga yuborilmadi: {exc}"
        )

    return redirect("patients:visit_detail", visit_id=visit.id)
