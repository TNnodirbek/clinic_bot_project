from django.utils.translation import gettext as _
from patients.models import NewPatient


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

        clinic_count = new_patients.exclude(
            note__icontains="Veterinar chaqirish"
        ).exclude(
            note__icontains="Xavfli holat"
        ).count()
        call_count = new_patients.filter(
            note__icontains="Veterinar chaqirish"
        ).count()
        danger_count = new_patients.filter(
            note__icontains="Xavfli holat"
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

    total_count = sum(item["count"] for item in notifications)

    return {
        "dashboard_notification_count": total_count,
        "dashboard_notifications": notifications,
        "dashboard_is_admin_user": user.is_superuser or user_in_group(user, "Administrator"),
        "dashboard_is_vet_user": user_in_group(user, "Veterinar"),
    }
