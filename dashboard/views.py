import os
import tempfile
import textwrap

from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.dateparse import parse_datetime
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.http import HttpResponseForbidden

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from patients.models import (
    NewPatient,
    DoctorProfile,
    LabResult,
    DiagnosticResult,
    Owner,
    Pet,
    Visit,
)

from patients.telegram import send_telegram_message, send_telegram_document


# =========================
# YORDAMCHI FUNKSIYALAR
# =========================

def user_in_group(user, group_name):
    return user.groups.filter(name=group_name).exists()


def custom_logout(request):
    logout(request)
    return redirect("login")


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
        doctor_profile = DoctorProfile.objects.filter(
            user=user,
            is_active=True
        ).first()

        if not doctor_profile:
            return HttpResponseForbidden(_("Sizga veterinar profili biriktirilmagan."))

        patients = NewPatient.objects.filter(
            selected_doctor=doctor_profile
        ).order_by("-updated_at")

    elif user_in_group(user, "Laboratoriya"):
        patients = NewPatient.objects.filter(
            lab_results__isnull=False
        ).distinct().order_by("-updated_at")

    elif user_in_group(user, "Diagnostika"):
        patients = NewPatient.objects.filter(
            diagnostic_results__isnull=False
        ).distinct().order_by("-updated_at")

    else:
        return HttpResponseForbidden(_("Sizda bemorlar holatini ko‘rish huquqi yo‘q."))

    context = {
        "patients": patients,
    }

    return render(request, "dashboard/patients_status.html", context)

@login_required
def patient_card(request, patient_id):
    try:
        patient = NewPatient.objects.select_related(
            "selected_doctor"
        ).get(id=patient_id)
    except NewPatient.DoesNotExist:
        messages.error(request, _("Bemor topilmadi."))
        return redirect("dashboard_home")

    user = request.user

    if user.is_superuser or user_in_group(user, "Administrator"):
        pass

    elif user_in_group(user, "Veterinar"):
        doctor_profile = DoctorProfile.objects.filter(
            user=user,
            is_active=True
        ).first()

        if not doctor_profile or patient.selected_doctor != doctor_profile:
            return HttpResponseForbidden(
                _("Sizda bu bemor kartasini ko‘rish huquqi yo‘q.")
            )

    elif user_in_group(user, "Laboratoriya"):
        if not LabResult.objects.filter(patient=patient).exists():
            return HttpResponseForbidden(
                _("Sizda bu bemor kartasini ko‘rish huquqi yo‘q.")
            )

    elif user_in_group(user, "Diagnostika"):
        if not DiagnosticResult.objects.filter(patient=patient).exists():
            return HttpResponseForbidden(
                _("Sizda bu bemor kartasini ko‘rish huquqi yo‘q.")
            )

    else:
        return HttpResponseForbidden(_("Sizda bu sahifaga kirish huquqi yo‘q."))

    lab_results = LabResult.objects.filter(
        patient=patient
    ).select_related(
        "veterinarian",
        "lab_worker"
    ).order_by("-updated_at")

    diagnostic_results = DiagnosticResult.objects.filter(
        patient=patient
    ).select_related(
        "lab_result",
        "diagnostic_worker",
        "lab_updated_by"
    ).order_by("-updated_at")

    visits = Visit.objects.filter(
        new_patient=patient
    ).select_related(
        "doctor",
        "pet"
    ).order_by("-created_at")

    context = {
        "patient": patient,
        "lab_results": lab_results,
        "diagnostic_results": diagnostic_results,
        "visits": visits,
        "back_url": request.META.get("HTTP_REFERER", "/dashboard/"),
    }

    return render(request, "dashboard/patient_card.html", context)

# =========================
# ADMINISTRATOR
# =========================

@login_required
def administrator_dashboard(request):
    if not user_in_group(request.user, "Administrator") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda Administrator dashboardiga kirish huquqi yo‘q."))

    new_patients = NewPatient.objects.filter(
        status="new"
    ).order_by("-created_at")

    history_patients = NewPatient.objects.exclude(
        status="new"
    ).order_by("-updated_at")

    doctors = DoctorProfile.objects.filter(
        is_active=True
    ).order_by("full_name")

    context = {
        "new_patients": new_patients,
        "history_patients": history_patients,
        "doctors": doctors,
    }

    return render(request, "dashboard/administrator.html", context)


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

            messages.success(
                request,
                _("%(patient)s bemori %(doctor)s veterinarga yuborildi.") % {"patient": patient.full_name, "doctor": doctor.full_name}
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

            if patient.status == "completed":
                messages.error(request, _("Yakunlangan bemorni bekor qilib bo‘lmaydi."))
                return redirect("administrator_dashboard")

            patient.status = "cancelled"
            patient.save()

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

            if patient.status == "completed":
                messages.error(request, _("Yakunlangan bemorni qayta yo‘naltirib bo‘lmaydi."))
                return redirect("administrator_dashboard")

            patient.selected_doctor = doctor
            patient.status = "assigned_to_vet"
            patient.save()

            messages.success(
                request,
                _("%(patient)s bemori %(doctor)s veterinarga qayta yo‘naltirildi.") % {"patient": patient.full_name, "doctor": doctor.full_name}
            )

        except NewPatient.DoesNotExist:
            messages.error(request, _("Bemor topilmadi."))

        except DoctorProfile.DoesNotExist:
            messages.error(request, _("Veterinar topilmadi."))

    return redirect("administrator_dashboard")


# =========================
# VETERINAR
# =========================

@login_required
def veterinar_dashboard(request):
    if not user_in_group(request.user, "Veterinar") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda Veterinar dashboardiga kirish huquqi yo‘q."))

    doctor_profile = DoctorProfile.objects.filter(
        user=request.user,
        is_active=True
    ).first()

    if request.user.is_superuser:
        active_patients = NewPatient.objects.filter(
            status__in=["assigned_to_vet", "returned_to_vet"]
        ).order_by("-created_at")

        history_patients = NewPatient.objects.exclude(
            status__in=["new", "assigned_to_vet", "returned_to_vet"]
        ).order_by("-updated_at")

        lab_requests = LabResult.objects.select_related(
            "patient",
            "veterinarian",
        ).order_by("-updated_at")

    elif doctor_profile:
        active_patients = NewPatient.objects.filter(
            selected_doctor=doctor_profile,
            status__in=["assigned_to_vet", "returned_to_vet"]
        ).order_by("-created_at")

        history_patients = NewPatient.objects.filter(
            selected_doctor=doctor_profile
        ).exclude(
            status__in=["assigned_to_vet", "returned_to_vet"]
        ).order_by("-updated_at")

        lab_requests = LabResult.objects.filter(
            patient__selected_doctor=doctor_profile
        ).select_related(
            "patient",
            "veterinarian",
        ).order_by("-updated_at")

    else:
        active_patients = NewPatient.objects.none()
        history_patients = NewPatient.objects.none()
        lab_requests = LabResult.objects.none()

    context = {
        "doctor_profile": doctor_profile,
        "active_patients": active_patients,
        "history_patients": history_patients,
        "lab_requests": lab_requests,
    }

    return render(request, "dashboard/veterinar.html", context)


@login_required
def send_patient_to_lab(request, patient_id):
    if not user_in_group(request.user, "Veterinar") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda bu amalni bajarish huquqi yo‘q."))

    if request.method == "POST":
        analysis_name = request.POST.get("analysis_name")
        comment = request.POST.get("comment")

        doctor_profile = DoctorProfile.objects.filter(
            user=request.user,
            is_active=True
        ).first()

        try:
            patient = NewPatient.objects.get(id=patient_id)

            if not request.user.is_superuser:
                if not doctor_profile or patient.selected_doctor != doctor_profile:
                    return HttpResponseForbidden(_("Bu bemor sizga biriktirilmagan."))

            LabResult.objects.create(
                patient=patient,
                veterinarian=request.user,
                analysis_name=analysis_name,
                comment=comment,
                status="waiting",
            )

            patient.status = "sent_to_lab"
            patient.save()

            messages.success(
                request,
                _("%(patient)s bemori laboratoriyaga yuborildi.") % {"patient": patient.full_name}
            )

        except NewPatient.DoesNotExist:
            messages.error(request, _("Bemor topilmadi."))

    return redirect("veterinar_dashboard")


@login_required
def edit_vet_lab_request(request, lab_result_id):
    if not user_in_group(request.user, "Veterinar") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda bu amalni bajarish huquqi yo‘q."))

    try:
        lab_result = LabResult.objects.select_related(
            "patient",
            "veterinarian",
        ).get(id=lab_result_id)
    except LabResult.DoesNotExist:
        messages.error(request, _("Laboratoriya so‘rovi topilmadi."))
        return redirect("veterinar_dashboard")

    patient = lab_result.patient

    doctor_profile = DoctorProfile.objects.filter(
        user=request.user,
        is_active=True
    ).first()

    if not request.user.is_superuser:
        if not doctor_profile or patient.selected_doctor != doctor_profile:
            return HttpResponseForbidden(_("Bu bemor sizga biriktirilmagan."))

    if patient.status == "completed":
        messages.error(request, _("Yakunlangan bemorning analiz so‘rovini tahrirlab bo‘lmaydi."))
        return redirect("veterinar_dashboard")

    if lab_result.status != "waiting":
        messages.error(
            request,
            _("Laboratoriya allaqachon natija kiritgan. Endi analiz turini o‘zgartirib bo‘lmaydi.")
        )
        return redirect("veterinar_dashboard")

    if request.method == "POST":
        lab_result.analysis_name = request.POST.get("analysis_name")
        lab_result.comment = request.POST.get("comment")
        lab_result.save()

        messages.success(request, _("Laboratoriyaga yuborilgan analiz so‘rovi tahrirlandi."))
        return redirect("veterinar_dashboard")

    context = {
        "lab_result": lab_result,
        "patient": patient,
    }

    return render(request, "dashboard/edit/edit_vet_lab_request.html", context)


# =========================
# LABORATORIYA
# =========================

@login_required
def laboratoriya_dashboard(request):
    if not user_in_group(request.user, "Laboratoriya") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda Laboratoriya dashboardiga kirish huquqi yo‘q."))

    active_lab_results = LabResult.objects.filter(
        patient__status="sent_to_lab",
        status="waiting"
    ).select_related(
        "patient",
        "veterinarian"
    ).order_by("-created_at")

    history_lab_results = LabResult.objects.exclude(
        patient__status="sent_to_lab",
        status="waiting"
    ).select_related(
        "patient",
        "veterinarian",
        "lab_worker"
    ).order_by("-updated_at")

    context = {
        "active_lab_results": active_lab_results,
        "history_lab_results": history_lab_results,
    }

    return render(request, "dashboard/laboratoriya.html", context)


@login_required
def send_lab_result_to_diagnostic(request, lab_result_id):
    if not user_in_group(request.user, "Laboratoriya") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda bu amalni bajarish huquqi yo‘q."))

    if request.method == "POST":
        result = request.POST.get("result")
        comment = request.POST.get("comment")

        try:
            lab_result = LabResult.objects.select_related("patient").get(id=lab_result_id)

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

            messages.success(
                request,
                _("%(patient)s bemorining analiz natijasi diagnostikaga yuborildi.") % {"patient": patient.full_name}
            )

        except LabResult.DoesNotExist:
            messages.error(request, _("Laboratoriya natijasi topilmadi."))

    return redirect("laboratoriya_dashboard")


@login_required
def edit_lab_result(request, lab_result_id):
    if not user_in_group(request.user, "Laboratoriya") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda bu amalni bajarish huquqi yo‘q."))

    try:
        lab_result = LabResult.objects.select_related(
            "patient",
            "veterinarian",
            "lab_worker"
        ).get(id=lab_result_id)
    except LabResult.DoesNotExist:
        messages.error(request, _("Laboratoriya yozuvi topilmadi."))
        return redirect("laboratoriya_dashboard")

    if lab_result.patient.status == "completed":
        messages.error(request, _("Yakunlangan bemorni tahrirlab bo‘lmaydi."))
        return redirect("laboratoriya_dashboard")

    if request.method == "POST":
        lab_result.result = request.POST.get("result")
        lab_result.lab_comment = request.POST.get("lab_comment")
        lab_result.lab_worker = request.user
        lab_result.save()

        diagnostics = DiagnosticResult.objects.filter(
            lab_result=lab_result
        ).exclude(
            patient__status="completed"
        )

        for diagnostic in diagnostics:
            diagnostic.is_lab_updated = True
            diagnostic.lab_updated_at = timezone.now()
            diagnostic.lab_updated_by = request.user
            diagnostic.save()

        messages.success(
            request,
            _("Laboratoriya natijasi tahrirlandi. Diagnostika xodimiga ogohlantirish chiqariladi.")
        )
        return redirect("laboratoriya_dashboard")

    context = {
        "lab_result": lab_result,
    }

    return render(request, "dashboard/edit/edit_lab_result.html", context)



@login_required
def view_lab_result(request, lab_result_id):
    try:
        lab_result = LabResult.objects.select_related(
            "patient",
            "veterinarian",
            "lab_worker"
        ).get(id=lab_result_id)

    except LabResult.DoesNotExist:
        messages.error(request, _("Laboratoriya natijasi topilmadi."))
        return redirect("dashboard_home")

    user = request.user
    patient = lab_result.patient

    if user.is_superuser or user_in_group(user, "Administrator"):
        pass

    elif user_in_group(user, "Veterinar"):
        doctor_profile = DoctorProfile.objects.filter(
            user=user,
            is_active=True
        ).first()

        if not doctor_profile or patient.selected_doctor != doctor_profile:
            return HttpResponseForbidden(
                "Sizda bu laboratoriya natijasini ko‘rish huquqi yo‘q."
            )

    elif user_in_group(user, "Laboratoriya") or user_in_group(user, "Diagnostika"):
        pass

    else:
        return HttpResponseForbidden(_("Sizda bu sahifaga kirish huquqi yo‘q."))

    context = {
        "lab_result": lab_result,
        "patient": patient,
        "back_url": request.META.get("HTTP_REFERER", "/dashboard/"),
        "can_edit_lab_result": user.is_superuser or user_in_group(user, "Laboratoriya"),
    }

    return render(request, "dashboard/view_lab_result.html", context)

# =========================
# DIAGNOSTIKA
# =========================

@login_required
def diagnostika_dashboard(request):
    if not user_in_group(request.user, "Diagnostika") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda Diagnostika dashboardiga kirish huquqi yo‘q."))

    active_diagnostics = DiagnosticResult.objects.filter(
        patient__status="sent_to_diagnostic",
        status="waiting"
    ).select_related(
        "patient",
        "lab_result",
        "diagnostic_worker",
        "lab_updated_by",
    ).order_by("-created_at")

    history_diagnostics = DiagnosticResult.objects.exclude(
        patient__status="sent_to_diagnostic",
        status="waiting"
    ).select_related(
        "patient",
        "lab_result",
        "diagnostic_worker",
        "lab_updated_by",
    ).order_by("-updated_at")

    context = {
        "active_diagnostics": active_diagnostics,
        "history_diagnostics": history_diagnostics,
    }

    return render(request, "dashboard/diagnostika.html", context)


@login_required
def return_diagnostic_to_vet(request, diagnostic_id):
    if not user_in_group(request.user, "Diagnostika") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda bu amalni bajarish huquqi yo‘q."))

    if request.method == "POST":
        conclusion = request.POST.get("conclusion")
        recommendation = request.POST.get("recommendation")

        try:
            diagnostic = DiagnosticResult.objects.select_related(
                "patient",
                "lab_result"
            ).get(id=diagnostic_id)

            diagnostic.conclusion = conclusion
            diagnostic.recommendation = recommendation
            diagnostic.diagnostic_worker = request.user
            diagnostic.status = "returned_to_vet"

            diagnostic.is_lab_updated = False
            diagnostic.lab_updated_at = None
            diagnostic.lab_updated_by = None

            diagnostic.save()

            patient = diagnostic.patient
            patient.status = "returned_to_vet"
            patient.save()

            messages.success(
                request,
                _("%(patient)s bemori veterinarga qaytarildi.") % {"patient": patient.full_name}
            )

        except DiagnosticResult.DoesNotExist:
            messages.error(request, _("Diagnostika yozuvi topilmadi."))

    return redirect("diagnostika_dashboard")


@login_required
def edit_diagnostic_result(request, diagnostic_id):
    if not user_in_group(request.user, "Diagnostika") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda bu amalni bajarish huquqi yo‘q."))

    try:
        diagnostic = DiagnosticResult.objects.select_related(
            "patient",
            "lab_result",
            "lab_updated_by",
        ).get(id=diagnostic_id)
    except DiagnosticResult.DoesNotExist:
        messages.error(request, _("Diagnostika yozuvi topilmadi."))
        return redirect("diagnostika_dashboard")

    if diagnostic.patient.status == "completed":
        messages.error(request, _("Yakunlangan bemorni tahrirlab bo‘lmaydi."))
        return redirect("diagnostika_dashboard")

    if request.method == "POST":
        diagnostic.conclusion = request.POST.get("conclusion")
        diagnostic.recommendation = request.POST.get("recommendation")
        diagnostic.diagnostic_worker = request.user

        diagnostic.is_lab_updated = False
        diagnostic.lab_updated_at = None
        diagnostic.lab_updated_by = None

        diagnostic.save()

        messages.success(request, _("Diagnostika xulosasi tahrirlandi."))
        return redirect("diagnostika_dashboard")

    context = {
        "diagnostic": diagnostic,
    }

    return render(request, "dashboard/edit/edit_diagnostic_result.html", context)

@login_required
def view_diagnostic_result(request, diagnostic_id):
    try:
        diagnostic = DiagnosticResult.objects.select_related(
            "patient",
            "lab_result",
            "diagnostic_worker",
            "lab_updated_by",
        ).get(id=diagnostic_id)

    except DiagnosticResult.DoesNotExist:
        messages.error(request, _("Diagnostika natijasi topilmadi."))
        return redirect("dashboard_home")

    user = request.user
    patient = diagnostic.patient

    if user.is_superuser or user_in_group(user, "Administrator"):
        pass

    elif user_in_group(user, "Veterinar"):
        doctor_profile = DoctorProfile.objects.filter(
            user=user,
            is_active=True
        ).first()

        if not doctor_profile or patient.selected_doctor != doctor_profile:
            return HttpResponseForbidden(
                "Sizda bu diagnostika natijasini ko‘rish huquqi yo‘q."
            )

    elif user_in_group(user, "Diagnostika"):
        pass

    elif user_in_group(user, "Laboratoriya"):
        pass

    else:
        return HttpResponseForbidden(_("Sizda bu sahifaga kirish huquqi yo‘q."))

    context = {
        "diagnostic": diagnostic,
        "patient": patient,
        "lab_result": diagnostic.lab_result,
        "back_url": request.META.get("HTTP_REFERER", "/dashboard/"),
        "can_edit_diagnostic_result": user.is_superuser or user_in_group(user, "Diagnostika"),
    }

    return render(request, "dashboard/view_diagnostic_result.html", context)


# =========================
# PDF
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

    primary = (22 / 255, 120 / 255, 110 / 255)
    dark = (35 / 255, 45 / 255, 55 / 255)
    light_bg = (245 / 255, 248 / 255, 250 / 255)
    border = (210 / 255, 220 / 255, 225 / 255)

    margin = 45
    y = height - 45

    def draw_wrapped_text(text, x, y_pos, font=normal_font, size=10, gap=14, width_chars=85):
        if text is None or str(text).strip() == "":
            text = "-"

        c.setFont(font, size)
        c.setFillColorRGB(*dark)

        lines = textwrap.wrap(str(text), width=width_chars)
        current_y = y_pos

        for line in lines:
            if current_y < 70:
                c.showPage()
                current_y = height - 60

            c.setFont(font, size)
            c.setFillColorRGB(*dark)
            c.drawString(x, current_y, line)
            current_y -= gap

        return current_y

    def section_title(title, y_pos):
        if y_pos < 90:
            c.showPage()
            y_pos = height - 60

        c.setFillColorRGB(*primary)
        c.roundRect(margin, y_pos - 22, width - 2 * margin, 28, 6, fill=1, stroke=0)

        c.setFillColorRGB(1, 1, 1)
        c.setFont(bold_font, 11)
        c.drawString(margin + 12, y_pos - 14, title)

        return y_pos - 40

    def info_row(label, value, x1, y_pos):
        c.setFont(bold_font, 9)
        c.setFillColorRGB(0.35, 0.35, 0.35)
        c.drawString(x1, y_pos, str(label))

        c.setFont(normal_font, 10)
        c.setFillColorRGB(*dark)
        c.drawString(x1, y_pos - 14, str(value) if value else "-")

    c.setFillColorRGB(*primary)
    c.roundRect(margin, y - 70, width - 2 * margin, 70, 10, fill=1, stroke=0)

    c.setFillColorRGB(1, 1, 1)
    c.circle(margin + 38, y - 35, 22, fill=1, stroke=0)

    c.setFillColorRGB(*primary)
    c.setFont(bold_font, 18)
    c.drawCentredString(margin + 38, y - 42, "V")

    c.setFillColorRGB(1, 1, 1)
    c.setFont(bold_font, 18)
    c.drawString(margin + 75, y - 30, "VetClinic")

    c.setFont(normal_font, 10)
    c.drawString(margin + 75, y - 47, "Veterinariya klinikasi")

    c.setFont(bold_font, 12)
    c.drawRightString(width - margin - 10, y - 30, "KO'RIK VARAQASI")

    c.setFont(normal_font, 9)
    c.drawRightString(width - margin - 10, y - 47, f"Raqam: {visit.visit_code}")

    y -= 95

    patient = visit.new_patient
    pet = visit.pet

    c.setFillColorRGB(*light_bg)
    c.roundRect(margin, y - 92, width - 2 * margin, 92, 8, fill=1, stroke=0)

    c.setStrokeColorRGB(*border)
    c.roundRect(margin, y - 92, width - 2 * margin, 92, 8, fill=0, stroke=1)

    info_row("Bemor F.I.Sh", patient.full_name if patient else "-", margin + 15, y - 25)
    info_row("Telefon", patient.phone if patient else "-", margin + 190, y - 25)
    info_row("Hayvon nomi", pet.name if pet else "-", margin + 345, y - 25)

    info_row(
        "Hayvon turi",
        patient.get_animal_type_display() if patient else "-",
        margin + 15,
        y - 65
    )

    info_row(
        "Ko'rik vaqti",
        visit.created_at.strftime("%d.%m.%Y %H:%M"),
        margin + 190,
        y - 65
    )

    if visit.doctor:
        doctor_name = visit.doctor.get_full_name() or visit.doctor.username
    else:
        doctor_name = "-"

    info_row(
        "Veterinar",
        doctor_name,
        margin + 345,
        y - 65
    )

    y -= 120

    y = section_title("1. Shikoyat", y)
    y = draw_wrapped_text(visit.complaint or "-", margin + 12, y)
    y -= 12

    if lab_result:
        y = section_title("2. Laboratoriya natijasi", y)
        y = draw_wrapped_text(f"Analiz turi: {lab_result.analysis_name}", margin + 12, y)
        y = draw_wrapped_text(f"Natija: {lab_result.result or '-'}", margin + 12, y)
        y = draw_wrapped_text(f"Veterinar izohi: {lab_result.comment or '-'}", margin + 12, y)
        y = draw_wrapped_text(f"Laboratoriya izohi: {lab_result.lab_comment or '-'}", margin + 12, y)
        y -= 12

    if diagnostic_result:
        y = section_title("3. Diagnostika xulosasi", y)
        y = draw_wrapped_text(diagnostic_result.conclusion or "-", margin + 12, y)
        y = draw_wrapped_text(f"Tavsiya: {diagnostic_result.recommendation or '-'}", margin + 12, y)
        y -= 12

    y = section_title("4. Yakuniy tashxis", y)
    y = draw_wrapped_text(visit.diagnosis or "-", margin + 12, y)
    y -= 12

    y = section_title("5. Davolash", y)
    y = draw_wrapped_text(visit.treatment or "-", margin + 12, y)
    y -= 12

    if visit.next_visit:
        y = section_title("6. Qayta kelish sanasi", y)
        y = draw_wrapped_text(visit.next_visit.strftime("%d.%m.%Y %H:%M"), margin + 12, y)
        y -= 12

    c.setStrokeColorRGB(*border)
    c.line(margin, 45, width - margin, 45)

    c.setFillColorRGB(0.45, 0.45, 0.45)
    c.setFont(normal_font, 8)
    c.drawString(margin, 30, "VetClinic elektron kartoteka tizimi orqali shakllantirildi.")
    c.drawRightString(width - margin, 30, "Telegram orqali yuborilgan PDF hujjat")

    c.save()
    return file_path


# =========================
# FINAL VISIT
# =========================

@login_required
def final_visit(request, patient_id):
    if not user_in_group(request.user, "Veterinar") and not request.user.is_superuser:
        return HttpResponseForbidden(_("Sizda bu amalni bajarish huquqi yo‘q."))

    try:
        patient = NewPatient.objects.get(id=patient_id)
    except NewPatient.DoesNotExist:
        messages.error(request, _("Bemor topilmadi."))
        return redirect("veterinar_dashboard")

    doctor_profile = DoctorProfile.objects.filter(
        user=request.user,
        is_active=True
    ).first()

    if not request.user.is_superuser:
        if not doctor_profile or patient.selected_doctor != doctor_profile:
            return HttpResponseForbidden(_("Bu bemor sizga biriktirilmagan."))

    if patient.status not in ["returned_to_vet", "completed"]:
        messages.error(
            request,
            _("Bu bemor hali yakuniy ko‘rik uchun tayyor emas.")
        )
        return redirect("veterinar_dashboard")

    lab_result = LabResult.objects.filter(
        patient=patient
    ).order_by("-updated_at").first()

    diagnostic_result = DiagnosticResult.objects.filter(
        patient=patient
    ).order_by("-updated_at").first()

    last_visit = Visit.objects.filter(
        new_patient=patient
    ).order_by("-created_at").first()

    if request.method == "POST":
        complaint = request.POST.get("complaint")
        diagnosis = request.POST.get("diagnosis")
        treatment = request.POST.get("treatment")
        next_visit_raw = request.POST.get("next_visit")

        next_visit = parse_datetime(next_visit_raw) if next_visit_raw else None

        owner, created = Owner.objects.get_or_create(
            phone=patient.phone,
            defaults={
                "full_name": patient.full_name,
                "telegram_id": patient.telegram_id,
            }
        )

        if not owner.telegram_id and patient.telegram_id:
            owner.telegram_id = patient.telegram_id
            owner.save()

        pet, created = Pet.objects.get_or_create(
            owner=owner,
            name=patient.animal_name or "Noma'lum",
            animal_type=patient.animal_type or "other",
        )

        visit = Visit.objects.create(
            doctor=request.user,
            new_patient=patient,
            pet=pet,
            complaint=complaint,
            diagnosis=diagnosis,
            treatment=treatment,
            next_visit=next_visit,
        )

        message = (
            f"✅ Ko‘rik varaqasi yuborildi\n\n"
            f"👤 Bemor: {patient.full_name}\n"
            f"🐾 Hayvon: {patient.animal_name or '-'}\n"
            f"🩺 Tashxis: {diagnosis}\n"
            f"💊 Davolash: {treatment or '-'}"
        )

        visit.message = message
        visit.save()

        pdf_path = None

        try:
            message_result = send_telegram_message(patient.telegram_id, message)

            if not message_result or not message_result.get("ok"):
                messages.warning(
                    request,
                    _("Ko‘rik saqlandi, lekin Telegram xabar yuborilmadi: %(error)s") % {
                        "error": message_result.get("description") if message_result else _("Natija qaytmadi")
                    }
                )
                return redirect("veterinar_dashboard")

            pdf_path = create_visit_pdf(
                visit=visit,
                lab_result=lab_result,
                diagnostic_result=diagnostic_result
            )

            pdf_result = send_telegram_document(
                patient.telegram_id,
                pdf_path,
                caption=_("Ko‘rik varaqasi PDF")
            )

            if not pdf_result or not pdf_result.get("ok"):
                messages.warning(
                    request,
                    _("Ko‘rik saqlandi, lekin PDF yuborilmadi: %(error)s") % {
                        "error": pdf_result.get("description") if pdf_result else _("Natija qaytmadi")
                    }
                )
                return redirect("veterinar_dashboard")

            visit.is_sent = True
            visit.save()

            patient.status = "completed"
            patient.save()

        except Exception as e:
            messages.warning(
                request,
                _("Ko‘rik saqlandi, lekin Telegramga yuborishda xatolik bo‘ldi: %(error)s") % {"error": e}
            )
            return redirect("veterinar_dashboard")

        finally:
            if pdf_path and os.path.exists(pdf_path):
                os.remove(pdf_path)

        messages.success(
            request,
            _("Ko‘rik/PDF Telegram orqali yuborildi.")
        )
        return redirect("veterinar_dashboard")

    context = {
        "patient": patient,
        "lab_result": lab_result,
        "diagnostic_result": diagnostic_result,
        "last_visit": last_visit,
    }

    return render(request, "dashboard/edit/final_visit.html", context)