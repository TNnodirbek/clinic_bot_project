from django.utils.translation import gettext as _
from patients.models import NewPatient, DoctorProfile, LabResult, DiagnosticResult


def user_in_group(user, group_name):
    return user.groups.filter(name=group_name).exists()


def dashboard_notifications(request):
    user = request.user

    if not user.is_authenticated:
        return {
            "dashboard_notification_count": 0,
            "dashboard_notifications": [],
        }

    notifications = []

    # Administrator / Superadmin: yangi arizalar
    if user.is_superuser or user_in_group(user, "Administrator"):
        new_count = NewPatient.objects.filter(status="new").count()

        if new_count > 0:
            notifications.append({
                "title": _("Yangi arizalar"),
                "message": _("%(count)s ta yangi ariza kelgan") % {"count": new_count},
                "icon": "fa-solid fa-clipboard-list",
                "url": "/dashboard/administrator/#new-applications",
                "count": new_count,
            })

    # Veterinar / Superadmin: faol bemorlar
    if user.is_superuser or user_in_group(user, "Veterinar"):
        if user.is_superuser:
            vet_count = NewPatient.objects.filter(
                status__in=["assigned_to_vet", "returned_to_vet"]
            ).count()
        else:
            doctor_profile = DoctorProfile.objects.filter(
                user=user,
                is_active=True
            ).first()

            if doctor_profile:
                vet_count = NewPatient.objects.filter(
                    selected_doctor=doctor_profile,
                    status__in=["assigned_to_vet", "returned_to_vet"]
                ).count()
            else:
                vet_count = 0

        if vet_count > 0:
            notifications.append({
                "title": _("Veterinar bemorlari"),
                "message": _("%(count)s ta faol bemor bor") % {"count": vet_count},
                "icon": "fa-solid fa-user-doctor",
                "url": "/dashboard/veterinar/#active-patients",
                "count": vet_count,
            })

    # Laboratoriya / Superadmin: kutilayotgan analizlar
    if user.is_superuser or user_in_group(user, "Laboratoriya"):
        lab_count = LabResult.objects.filter(
            patient__status="sent_to_lab",
            status="waiting"
        ).count()

        if lab_count > 0:
            notifications.append({
                "title": _("Laboratoriya"),
                "message": _("%(count)s ta analiz natija kutmoqda") % {"count": lab_count},
                "icon": "fa-solid fa-flask",
                "url": "/dashboard/laboratoriya/#active-lab-results",
                "count": lab_count,
            })

    # Diagnostika / Superadmin: kutilayotgan diagnostika
    if user.is_superuser or user_in_group(user, "Diagnostika"):
        diagnostic_count = DiagnosticResult.objects.filter(
            patient__status="sent_to_diagnostic",
            status="waiting"
        ).count()

        if diagnostic_count > 0:
            notifications.append({
                "title": _("Diagnostika"),
                "message": _("%(count)s ta xulosa kutmoqda") % {"count": diagnostic_count},
                "icon": "fa-solid fa-stethoscope",
                "url": "/dashboard/diagnostika/#active-diagnostics",
                "count": diagnostic_count,
            })

    total_count = sum(item["count"] for item in notifications)

    return {
        "dashboard_notification_count": total_count,
        "dashboard_notifications": notifications,
    }