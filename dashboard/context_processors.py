from django.utils.translation import gettext as _
from django.utils import timezone
from django.urls import reverse
from django.db.models import Q
from patients.models import NewPatient, DoctorProfile


def user_in_group(user, group_name):
    return user.groups.filter(name=group_name).exists()


def relative_time_text(dt):
    if not dt:
        return ""

    now = timezone.localtime(timezone.now())
    local_dt = timezone.localtime(dt)
    diff = now - local_dt

    seconds = max(int(diff.total_seconds()), 0)
    minutes = seconds // 60
    hours = minutes // 60
    days = diff.days

    if minutes < 1:
        return _("hozirgina")
    if minutes < 60:
        return _("%(count)s daqiqa oldin") % {"count": minutes}
    if hours < 24:
        return _("%(count)s soat oldin") % {"count": hours}
    if days == 1:
        return _("bir kun oldin")
    if days < 7:
        return _("%(count)s kun oldin") % {"count": days}
    if days < 30:
        weeks = max(days // 7, 1)
        return _("%(count)s hafta oldin") % {"count": weeks}

    return local_dt.strftime("%d %b %Y")


def dashboard_notifications(request):
    user = request.user

    if not user.is_authenticated:
        return {
            "dashboard_notification_count": 0,
            "dashboard_notifications": [],
            "dashboard_is_admin_user": False,
            "dashboard_is_vet_user": False,
        }

    notifications = []

    if user.is_superuser or user_in_group(user, "Administrator"):
        new_patients = NewPatient.objects.filter(status="new")

        danger_qs = new_patients.filter(
            Q(service_type="danger") | Q(note__icontains="Xavfli holat")
        )
        call_qs = new_patients.filter(
            Q(service_type__in=["vet_call", "call"]) | Q(note__icontains="Veterinar chaqirish")
        ).exclude(
            Q(service_type="danger") | Q(note__icontains="Xavfli holat")
        )
        clinic_qs = new_patients.filter(
            Q(service_type="clinic") | Q(note__icontains="Klinikada davolash")
        ).exclude(
            Q(service_type__in=["vet_call", "call", "danger"])
            | Q(note__icontains="Veterinar chaqirish")
            | Q(note__icontains="Xavfli holat")
        )

        clinic_count = clinic_qs.count()
        call_count = call_qs.count()
        danger_count = danger_qs.count()
        clinic_time = clinic_qs.order_by("-created_at").values_list("created_at", flat=True).first()
        call_time = call_qs.order_by("-created_at").values_list("created_at", flat=True).first()
        danger_time = danger_qs.order_by("-created_at").values_list("created_at", flat=True).first()

        notification_items = [
            {
                "title": _("Klinikada davolash"),
                "message": _("%(count)s ta yangi ariza") % {"count": clinic_count},
                "icon": "fa-solid fa-house-medical",
                "url": reverse("administrator_dashboard") + "?service=clinic#new-applications",
                "count": clinic_count,
                "time": clinic_time,
                "time_text": relative_time_text(clinic_time),
            },
            {
                "title": _("Veterinar chaqirish"),
                "message": _("%(count)s ta yangi ariza") % {"count": call_count},
                "icon": "fa-solid fa-truck-medical",
                "url": reverse("administrator_dashboard") + "?service=vet_call#new-applications",
                "count": call_count,
                "time": call_time,
                "time_text": relative_time_text(call_time),
            },
            {
                "title": _("Xavfli holatlar"),
                "message": _("%(count)s ta yangi xabar") % {"count": danger_count},
                "icon": "fa-solid fa-triangle-exclamation",
                "url": reverse("administrator_dashboard") + "?service=danger#new-applications",
                "count": danger_count,
                "time": danger_time,
                "time_text": relative_time_text(danger_time),
            },
        ]

        notifications.extend(
            item for item in notification_items if item["count"] > 0
        )

    elif user_in_group(user, "Veterinar"):
        doctor = DoctorProfile.objects.filter(user=user, is_active=True).first()
        assigned_patients = NewPatient.objects.filter(selected_doctor=doctor) if doctor else NewPatient.objects.none()
        active_patients = assigned_patients.exclude(status__in=["new", "completed", "cancelled"])

        today_count = assigned_patients.filter(
            created_at__date=timezone.localdate()
        ).exclude(status="cancelled").count()
        assigned_count = active_patients.filter(status="assigned_to_vet").count()
        danger_count = active_patients.filter(
            Q(service_type="danger") | Q(note__icontains="Xavfli holat")
        ).count()
        today_time = assigned_patients.filter(
            created_at__date=timezone.localdate()
        ).exclude(status="cancelled").order_by("-created_at").values_list("created_at", flat=True).first()
        assigned_time = active_patients.filter(
            status="assigned_to_vet"
        ).order_by("-created_at").values_list("created_at", flat=True).first()
        danger_time = active_patients.filter(
            Q(service_type="danger") | Q(note__icontains="Xavfli holat")
        ).order_by("-created_at").values_list("created_at", flat=True).first()

        notification_items = [
            {
                "title": _("Bugungi arizalarim"),
                "message": _("%(count)s ta bugungi ariza") % {"count": today_count},
                "icon": "fa-regular fa-clipboard",
                "url": "/dashboard/veterinar/?scope=today#my-applications",
                "count": today_count,
                "time": today_time,
                "time_text": relative_time_text(today_time),
            },
            {
                "title": _("Yangi biriktirilgan"),
                "message": _("%(count)s ta qabul qilinmagan ariza") % {"count": assigned_count},
                "icon": "fa-solid fa-user-doctor",
                "url": "/dashboard/veterinar/#my-applications",
                "count": assigned_count,
                "time": assigned_time,
                "time_text": relative_time_text(assigned_time),
            },
            {
                "title": _("Xavfli holatlar"),
                "message": _("%(count)s ta xavfli holat") % {"count": danger_count},
                "icon": "fa-solid fa-triangle-exclamation",
                "url": "/dashboard/veterinar/?service=danger#my-applications",
                "count": danger_count,
                "time": danger_time,
                "time_text": relative_time_text(danger_time),
            },
        ]

        notifications.extend(
            item for item in notification_items if item["count"] > 0
        )

    total_count = sum(item["count"] for item in notifications)

    return {
        "dashboard_notification_count": total_count,
        "dashboard_notifications": notifications,
        "dashboard_is_admin_user": user.is_superuser or user_in_group(user, "Administrator"),
        "dashboard_is_vet_user": user_in_group(user, "Veterinar"),
    }
