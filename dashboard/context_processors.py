from django.utils.translation import gettext as _
from django.utils import timezone
from django.db.models import Q
from patients.models import NewPatient, DoctorProfile


def user_in_group(user, group_name):
    return user.groups.filter(name=group_name).exists()


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

        clinic_count = new_patients.filter(
            service_type="clinic"
        ).exclude(
            Q(note__icontains="Veterinar chaqirish") | Q(note__icontains="Xavfli holat")
        ).count()
        call_count = new_patients.filter(
            Q(service_type="vet_call") | Q(note__icontains="Veterinar chaqirish")
        ).count()
        danger_count = new_patients.filter(
            Q(service_type="danger") | Q(note__icontains="Xavfli holat")
        ).count()

        notification_items = [
            {
                "title": _("Klinikada davolash"),
                "message": _("%(count)s ta yangi ariza") % {"count": clinic_count},
                "icon": "fa-solid fa-house-medical",
                "url": "/dashboard/administrator/?service=clinic#new-applications",
                "count": clinic_count,
            },
            {
                "title": _("Veterinar chaqirish"),
                "message": _("%(count)s ta yangi ariza") % {"count": call_count},
                "icon": "fa-solid fa-truck-medical",
                "url": "/dashboard/administrator/?service=vet_call#new-applications",
                "count": call_count,
            },
            {
                "title": _("Xavfli holatlar"),
                "message": _("%(count)s ta yangi xabar") % {"count": danger_count},
                "icon": "fa-solid fa-triangle-exclamation",
                "url": "/dashboard/administrator/?service=danger#new-applications",
                "count": danger_count,
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

        notification_items = [
            {
                "title": _("Bugungi arizalarim"),
                "message": _("%(count)s ta bugungi ariza") % {"count": today_count},
                "icon": "fa-regular fa-clipboard",
                "url": "/dashboard/veterinar/?scope=today#my-applications",
                "count": today_count,
            },
            {
                "title": _("Yangi biriktirilgan"),
                "message": _("%(count)s ta qabul qilinmagan ariza") % {"count": assigned_count},
                "icon": "fa-solid fa-user-doctor",
                "url": "/dashboard/veterinar/#my-applications",
                "count": assigned_count,
            },
            {
                "title": _("Xavfli holatlar"),
                "message": _("%(count)s ta xavfli holat") % {"count": danger_count},
                "icon": "fa-solid fa-triangle-exclamation",
                "url": "/dashboard/veterinar/?service=danger#my-applications",
                "count": danger_count,
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
