import os
import tempfile
import textwrap

from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import GroupAdmin as DefaultGroupAdmin
from django.contrib.admin.sites import NotRegistered
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .models import( 
                    Owner,
                    Pet,
                    Visit,
                    MyVisit,
                    DoctorProfile,
                    NewPatient,
                    LabResult,
                    DiagnosticResult,
                    )
from .telegram import send_telegram_message, send_telegram_document

from django.utils.safestring import mark_safe
from django.utils.html import escape

def clean_text(value):
    if value is None:
        return ""

    text = str(value)

    replacements = {
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "ў": "o'",
        "Ў": "O'",
        "ғ": "g'",
        "Ғ": "G'",
        "қ": "q",
        "Қ": "Q",
        "ҳ": "h",
        "Ҳ": "H",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


def build_visit_message(visit):
    owner = visit.pet.owner if visit.pet else None
    pet = visit.pet

    owner_name = owner.full_name if owner else _("Hurmatli mijoz")
    pet_name = pet.name if pet else _("hayvoningiz")

    text = f"{_('Assalomu alaykum')}, {owner_name}.\n\n"
    text += f"{pet_name} {_('uchun ko‘rik ma’lumotlari')}:\n"

    if visit.complaint:
        text += f"\n{_('Shikoyat')}: {visit.complaint}"

    if visit.diagnosis:
        text += f"\n{_('Tashxis')}: {visit.diagnosis}"

    if visit.treatment:
        text += f"\n{_('Davolash')}: {visit.treatment}"

    if visit.next_visit:
        date_text = visit.next_visit.strftime("%d.%m.%Y %H:%M")
        text += f"\n\n{_('Qayta kelish sanasi')}: {date_text}"

    if visit.message:
        text += f"\n\n{_('Qo‘shimcha xabar')}:\n{visit.message}"

    text += f"\n\n{_('Ko‘rik varaqasi PDF shaklida ham yuborildi.')}"

    return text


def draw_wrapped_text(pdf, text, x, y, max_width_chars=90, line_height=14):
    text = clean_text(text)

    if not text:
        return y

    lines = []

    for paragraph in text.split("\n"):
        wrapped = textwrap.wrap(paragraph, width=max_width_chars)

        if wrapped:
            lines.extend(wrapped)
        else:
            lines.append("")

    for line in lines:
        if y < 60:
            pdf.showPage()
            pdf.setFont("Helvetica", 11)
            y = 800

        pdf.drawString(x, y, line)
        y -= line_height

    return y


def create_visit_pdf(visit):
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp_file.close()

    pdf_path = temp_file.name
    pdf = canvas.Canvas(pdf_path, pagesize=A4)

    width, height = A4
    y = height - 50

    owner = visit.pet.owner if visit.pet else None
    pet = visit.pet

    owner_name = owner.full_name if owner else _("Aniqlanmagan")
    owner_phone = owner.phone if owner else _("Aniqlanmagan")
    pet_name = pet.name if pet else _("Aniqlanmagan")
    pet_type = pet.get_animal_type_display() if pet else _("Aniqlanmagan")

    doctor_name = _("Aniqlanmagan")

    if visit.doctor:
        doctor_profile = DoctorProfile.objects.filter(user=visit.doctor).first()

        if doctor_profile:
            doctor_name = doctor_profile.full_name
        else:
            doctor_name = visit.doctor.username

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawCentredString(width / 2, y, clean_text(_("Veterinariya klinikasi")))
    y -= 25

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawCentredString(width / 2, y, clean_text(_("Ko‘rik varaqasi")))
    y -= 35

    pdf.setFont("Helvetica", 11)

    info_lines = [
        f"{_('Ko‘rik raqami')}: {visit.visit_code}",
        f"{_('Egasi F.I.Sh')}: {owner_name}",
        f"{_('Telefon')}: {owner_phone}",
        f"{_('Hayvon nomi')}: {pet_name}",
        f"{_('Hayvon turi')}: {pet_type}",
        f"{_('Mas’ul doktor')}: {doctor_name}",
        f"{_('Ko‘rik sanasi')}: {visit.created_at.strftime('%d.%m.%Y %H:%M') if visit.created_at else '-'}",
    ]

    if visit.next_visit:
        info_lines.append(
            f"{_('Qayta kelish sanasi')}: {visit.next_visit.strftime('%d.%m.%Y %H:%M')}"
        )

    for line in info_lines:
        pdf.drawString(50, y, clean_text(line))
        y -= 18

    y -= 10
    pdf.line(50, y, width - 50, y)
    y -= 25

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y, clean_text(_("Shikoyat") + ":"))
    y -= 18
    pdf.setFont("Helvetica", 11)
    y = draw_wrapped_text(pdf, visit.complaint or _("Kiritilmagan"), 50, y)

    y -= 10
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y, clean_text(_("Tashxis") + ":"))
    y -= 18
    pdf.setFont("Helvetica", 11)
    y = draw_wrapped_text(pdf, visit.diagnosis or _("Kiritilmagan"), 50, y)

    y -= 10
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y, clean_text(_("Davolash") + ":"))
    y -= 18
    pdf.setFont("Helvetica", 11)
    y = draw_wrapped_text(pdf, visit.treatment or _("Kiritilmagan"), 50, y)

    if visit.message:
        y -= 10
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y, clean_text(_("Qo‘shimcha xabar") + ":"))
        y -= 18
        pdf.setFont("Helvetica", 11)
        y = draw_wrapped_text(pdf, visit.message, 50, y)

    y -= 30

    if y < 90:
        pdf.showPage()
        y = height - 60

    pdf.setFont("Helvetica", 10)
    pdf.drawString(
        50,
        y,
        clean_text(_("Ushbu varaqa elektron kartoteka tizimi orqali shakllantirildi."))
    )

    pdf.save()

    return pdf_path


class MyPatientsFilter(admin.SimpleListFilter):
    title = _("Bemorlar")
    parameter_name = "my_patients"

    def lookups(self, request, model_admin):
        return (
            ("mine", _("Mening bemorlarim")),
            ("all", _("Barcha bemorlar")),
        )

    def queryset(self, request, queryset):
        if self.value() == "mine":
            return queryset.filter(doctor=request.user)

        return queryset


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = (
        "owner_code",
        "full_name",
        "phone",
        "telegram_id",
        "address",
        "created_at",
    )

    search_fields = (
        "owner_code",
        "full_name",
        "phone",
        "telegram_id",
        "address",
    )

    readonly_fields = (
        "owner_code",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Pet)
class PetAdmin(admin.ModelAdmin):
    list_display = (
        "pet_code",
        "name",
        "animal_type",
        "owner",
        "created_at",
    )

    search_fields = (
        "pet_code",
        "name",
        "owner__full_name",
        "owner__phone",
        "owner__owner_code",
    )

    list_filter = (
        "animal_type",
    )

    readonly_fields = (
        "pet_code",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = (
        "visit_code",
        "pet",
        "get_owner",
        "doctor",
        "new_patient",
        "diagnosis",
        "next_visit",
        "is_sent",
        "created_at",
    )

    search_fields = (
        "visit_code",
        "pet__name",
        "pet__pet_code",
        "pet__owner__full_name",
        "pet__owner__phone",
        "pet__owner__owner_code",
        "new_patient__patient_code",
        "new_patient__full_name",
        "new_patient__phone",
        "diagnosis",
        "doctor__username",
        "doctor__first_name",
        "doctor__last_name",
    )

    list_filter = (
        MyPatientsFilter,
        "doctor",
        "pet__animal_type",
        "is_sent",
        "next_visit",
        "created_at",
    )

    readonly_fields = (
        "visit_code",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (_("Ko‘rik ma’lumotlari"), {
            "fields": (
                "visit_code",
                "doctor",
                "new_patient",
                "pet",
            )
        }),
        (_("Tibbiy ma’lumotlar"), {
            "fields": (
                "complaint",
                "diagnosis",
                "treatment",
                "next_visit",
            )
        }),
        (_("Telegram xabar"), {
            "fields": (
                "message",
                "is_sent",
            )
        }),
        (_("Vaqt ma’lumotlari"), {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )

    actions = [
        "send_message_to_owner",
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.is_superuser:
            return qs

        return qs.filter(doctor=request.user)

    def get_fieldsets(self, request, obj=None):
        if request.user.is_superuser:
            return self.fieldsets

        return (
            (_("Ko‘rik ma’lumotlari"), {
                "fields": (
                    "visit_code",
                    "new_patient",
                )
            }),
            (_("Tibbiy ma’lumotlar"), {
                "fields": (
                    "complaint",
                    "diagnosis",
                    "treatment",
                    "next_visit",
                )
            }),
            (_("Telegram xabar"), {
                "fields": (
                    "message",
                    "is_sent",
                )
            }),
            (_("Vaqt ma’lumotlari"), {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            }),
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "new_patient" and not request.user.is_superuser:
            kwargs["queryset"] = NewPatient.objects.filter(
                selected_doctor__user=request.user,
                status="new"
            )

        if db_field.name == "pet" and not request.user.is_superuser:
            kwargs["queryset"] = Pet.objects.filter(
                visit__doctor=request.user
            ).distinct()

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_owner(self, obj):
        if obj.pet and obj.pet.owner:
            return obj.pet.owner.full_name

        if obj.new_patient:
            return obj.new_patient.full_name

        return _("Egasi aniqlanmagan")

    get_owner.short_description = _("Egasi")

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.doctor = request.user

        if not obj.doctor:
            obj.doctor = request.user

        if obj.new_patient:
            new_patient = obj.new_patient

            owner, created_owner = Owner.objects.get_or_create(
                phone=new_patient.phone,
                defaults={
                    "full_name": new_patient.full_name,
                    "telegram_id": new_patient.telegram_id,
                }
            )

            owner.full_name = new_patient.full_name
            owner.phone = new_patient.phone
            owner.telegram_id = new_patient.telegram_id
            owner.save()

            if not obj.pet:
                animal_name = new_patient.animal_name or _("Noma’lum hayvon")
                animal_type = new_patient.animal_type or "other"

                pet, created_pet = Pet.objects.get_or_create(
                    owner=owner,
                    name=animal_name,
                    animal_type=animal_type,
                )

                obj.pet = pet

            new_patient.status = "accepted"
            new_patient.save()

        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def send_message_to_owner(self, request, queryset):
        success_count = 0
        error_count = 0

        for visit in queryset:
            if not request.user.is_superuser and visit.doctor != request.user:
                error_count += 1
                self.message_user(
                    request,
                    _("{} sizga tegishli emas.").format(visit.visit_code),
                    level="ERROR"
                )
                continue

            if not visit.pet or not visit.pet.owner:
                error_count += 1
                self.message_user(
                    request,
                    _("{} uchun hayvon egasi topilmadi.").format(visit.visit_code),
                    level="ERROR"
                )
                continue

            owner = visit.pet.owner

            if not owner.telegram_id:
                error_count += 1
                self.message_user(
                    request,
                    _("{} uchun Telegram ID yo‘q.").format(owner.full_name),
                    level="ERROR"
                )
                continue

            message_text = build_visit_message(visit)

            if not message_text:
                error_count += 1
                self.message_user(
                    request,
                    _("{} uchun xabar matni shakllanmadi.").format(owner.full_name),
                    level="ERROR"
                )
                continue

            pdf_path = None

            try:
                result = send_telegram_message(owner.telegram_id, message_text)

                if not result.get("ok"):
                    error_count += 1
                    self.message_user(
                        request,
                        _("Xatolik: {}").format(result.get("description")),
                        level="ERROR"
                    )
                    continue

                pdf_path = create_visit_pdf(visit)

                pdf_result = send_telegram_document(
                    owner.telegram_id,
                    pdf_path,
                    caption=str(_("Ko‘rik varaqasi PDF"))
                )

                if pdf_result.get("ok"):
                    visit.is_sent = True
                    visit.save()
                    success_count += 1
                else:
                    error_count += 1
                    self.message_user(
                        request,
                        _("PDF yuborishda xatolik: {}").format(
                            pdf_result.get("description")
                        ),
                        level="ERROR"
                    )

            finally:
                if pdf_path and os.path.exists(pdf_path):
                    os.remove(pdf_path)

        self.message_user(
            request,
            _("Yuborildi: {} ta. Xato: {} ta.").format(success_count, error_count)
        )

    send_message_to_owner.short_description = _(
        "Tanlangan ko‘riklar bo‘yicha Telegram xabar yuborish"
    )


@admin.register(MyVisit)
class MyVisitAdmin(admin.ModelAdmin):
    list_display = (
        "visit_code",
        "pet",
        "get_owner",
        "doctor",
        "new_patient",
        "diagnosis",
        "next_visit",
        "is_sent",
        "created_at",
    )

    search_fields = (
        "visit_code",
        "pet__name",
        "pet__pet_code",
        "pet__owner__full_name",
        "pet__owner__phone",
        "pet__owner__owner_code",
        "new_patient__patient_code",
        "new_patient__full_name",
        "new_patient__phone",
        "diagnosis",
    )

    list_filter = (
        "pet__animal_type",
        "is_sent",
        "next_visit",
        "created_at",
    )

    readonly_fields = (
        "visit_code",
        "doctor",
        "new_patient",
        "pet",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (_("Ko‘rik ma’lumotlari"), {
            "fields": (
                "visit_code",
                "doctor",
                "new_patient",
                "pet",
            )
        }),
        (_("Tibbiy ma’lumotlar"), {
            "fields": (
                "complaint",
                "diagnosis",
                "treatment",
                "next_visit",
            )
        }),
        (_("Telegram xabar"), {
            "fields": (
                "message",
                "is_sent",
            )
        }),
        (_("Vaqt ma’lumotlari"), {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )

    actions = [
        "send_message_to_owner",
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.is_superuser:
            return qs

        return qs.filter(doctor=request.user)

    def get_owner(self, obj):
        if obj.pet and obj.pet.owner:
            return obj.pet.owner.full_name

        if obj.new_patient:
            return obj.new_patient.full_name

        return _("Egasi aniqlanmagan")

    get_owner.short_description = _("Egasi")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True

        if obj is None:
            return True

        return obj.doctor == request.user

    def has_delete_permission(self, request, obj=None):
        return False

    def send_message_to_owner(self, request, queryset):
        success_count = 0
        error_count = 0

        for visit in queryset:
            if not request.user.is_superuser and visit.doctor != request.user:
                error_count += 1
                self.message_user(
                    request,
                    _("{} sizga tegishli emas.").format(visit.visit_code),
                    level="ERROR"
                )
                continue

            if not visit.pet or not visit.pet.owner:
                error_count += 1
                self.message_user(
                    request,
                    _("{} uchun hayvon egasi topilmadi.").format(visit.visit_code),
                    level="ERROR"
                )
                continue

            owner = visit.pet.owner

            if not owner.telegram_id:
                error_count += 1
                self.message_user(
                    request,
                    _("{} uchun Telegram ID yo‘q.").format(owner.full_name),
                    level="ERROR"
                )
                continue

            message_text = build_visit_message(visit)

            if not message_text:
                error_count += 1
                self.message_user(
                    request,
                    _("{} uchun xabar matni shakllanmadi.").format(owner.full_name),
                    level="ERROR"
                )
                continue

            pdf_path = None

            try:
                result = send_telegram_message(owner.telegram_id, message_text)

                if not result.get("ok"):
                    error_count += 1
                    self.message_user(
                        request,
                        _("Xatolik: {}").format(result.get("description")),
                        level="ERROR"
                    )
                    continue

                pdf_path = create_visit_pdf(visit)

                pdf_result = send_telegram_document(
                    owner.telegram_id,
                    pdf_path,
                    caption=str(_("Ko‘rik varaqasi PDF"))
                )

                if pdf_result.get("ok"):
                    visit.is_sent = True
                    visit.save()
                    success_count += 1
                else:
                    error_count += 1
                    self.message_user(
                        request,
                        _("PDF yuborishda xatolik: {}").format(
                            pdf_result.get("description")
                        ),
                        level="ERROR"
                    )

            finally:
                if pdf_path and os.path.exists(pdf_path):
                    os.remove(pdf_path)

        self.message_user(
            request,
            _("Yuborildi: {} ta. Xato: {} ta.").format(success_count, error_count)
        )

    send_message_to_owner.short_description = _(
        "Tanlangan bemorlarga Telegram xabar yuborish"
    )


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "user",
        "phone",
        "specialization",
        "experience",
        "is_active",
        "created_at",
    )

    search_fields = (
        "full_name",
        "phone",
        "specialization",
        "experience",
        "user__username",
        "user__first_name",
        "user__last_name",
    )

    list_filter = (
        "is_active",
    )

    readonly_fields = (
        "created_at",
    )

    fieldsets = (
        (_("Doktor akkaunti"), {
            "fields": (
                "user",
                "is_active",
            )
        }),
        (_("Shaxsiy ma’lumotlar"), {
            "fields": (
                "full_name",
                "phone",
                "specialization",
                "experience",
            )
        }),
        (_("Rezyume"), {
            "fields": (
                "resume",
            )
        }),
        (_("Vaqt ma’lumotlari"), {
            "fields": (
                "created_at",
            )
        }),
    )

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(NewPatient)
class NewPatientAdmin(admin.ModelAdmin):
    list_display = (
        "patient_code",
        "full_name",
        "phone",
        "telegram_id",
        "telegram_username",
        "animal_name",
        "animal_type",
        "selected_doctor",
        "status",
        "created_at",
    )

    search_fields = (
        "patient_code",
        "full_name",
        "phone",
        "telegram_id",
        "telegram_username",
        "animal_name",
        "selected_doctor__full_name",
        "selected_doctor__user__username",
    )

    list_filter = (
        "status",
        "selected_doctor",
        "animal_type",
        "created_at",
    )

    readonly_fields = (
        "patient_code",
        "telegram_id",
        "telegram_username",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (_("Bemor ma’lumotlari"), {
            "fields": (
                "patient_code",
                "full_name",
                "phone",
                "telegram_id",
                "telegram_username",
            )
        }),
        (_("Hayvon ma’lumotlari"), {
            "fields": (
                "animal_name",
                "animal_type",
            )
        }),
        (_("Doktor va holat"), {
            "fields": (
                "selected_doctor",
                "status",
                "note",
            )
        }),
        (_("Vaqt ma’lumotlari"), {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.is_superuser:
            return qs

        return qs.filter(selected_doctor__user=request.user)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

@admin.register(LabResult)
class LabResultAdmin(admin.ModelAdmin):
    list_display = (
        "patient",
        "analysis_name",
        "veterinarian",
        "lab_worker",
        "status",
        "created_at",
    )

    search_fields = (
        "patient__patient_code",
        "patient__full_name",
        "patient__phone",
        "analysis_name",
        "result",
        "comment",
        "veterinarian__username",
        "lab_worker__username",
    )

    list_filter = (
        "status",
        "created_at",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (
        ("Bemor va veterinar", {
            "fields": (
                "patient",
                "veterinarian",
                "lab_worker",
            )
        }),
        ("Analiz ma’lumotlari", {
            "fields": (
                "analysis_name",
                "result",
                "comment",
                "status",
            )
        }),
        ("Vaqt ma’lumotlari", {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )


@admin.register(DiagnosticResult)
class DiagnosticResultAdmin(admin.ModelAdmin):
    list_display = (
        "patient",
        "lab_result",
        "diagnostic_worker",
        "status",
        "created_at",
    )

    search_fields = (
        "patient__patient_code",
        "patient__full_name",
        "patient__phone",
        "conclusion",
        "recommendation",
        "diagnostic_worker__username",
    )

    list_filter = (
        "status",
        "created_at",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (
        ("Bemor va laboratoriya", {
            "fields": (
                "patient",
                "lab_result",
                "diagnostic_worker",
            )
        }),
        ("Diagnostika ma’lumotlari", {
            "fields": (
                "conclusion",
                "recommendation",
                "status",
            )
        }),
        ("Vaqt ma’lumotlari", {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )

# =========================
# CUSTOM GROUP ADMIN
# =========================
# =========================

class CustomGroupAdmin(DefaultGroupAdmin):
    list_display = (
        "name",
        "user_count",
        "users_short_list",
    )

    readonly_fields = (
        "group_users_table",
    )

    fieldsets = (
        ("Guruh ma’lumotlari", {
            "fields": (
                "name",
                "group_users_table",
            )
        }),
        ("Ruxsatlar", {
            "fields": (
                "permissions",
            )
        }),
    )

    def user_count(self, obj):
        return obj.user_set.count()

    user_count.short_description = "Hodimlar soni"

    def users_short_list(self, obj):
        users = obj.user_set.all()

        if not users.exists():
            return "Hodim yo‘q"

        names = []

        for user in users[:5]:
            full_name = user.get_full_name()

            if full_name:
                names.append(full_name)
            else:
                names.append(user.username)

        if users.count() > 5:
            names.append("...")

        return ", ".join(names)

    users_short_list.short_description = "Guruhdagi hodimlar"

    def group_users_table(self, obj):
        users = obj.user_set.all().order_by("first_name", "last_name", "username")

        if not users.exists():
            return "Bu guruhga hali hodim biriktirilmagan."

        rows = ""

        for user in users:
            full_name = user.get_full_name() or user.username
            doctor_profile = DoctorProfile.objects.filter(user=user).first()

            if doctor_profile:
                position = doctor_profile.specialization or "Veterinar"
                phone = doctor_profile.phone or "-"
            else:
                position = obj.name
                phone = "-"

            status = "Faol" if user.is_active else "Faol emas"

            rows += f"""
                <tr>
                    <td style="border:1px solid #ddd; padding:8px;">{escape(user.username)}</td>
                    <td style="border:1px solid #ddd; padding:8px;">{escape(full_name)}</td>
                    <td style="border:1px solid #ddd; padding:8px;">{escape(position)}</td>
                    <td style="border:1px solid #ddd; padding:8px;">{escape(phone)}</td>
                    <td style="border:1px solid #ddd; padding:8px;">{escape(status)}</td>
                </tr>
            """

        html = f"""
            <div style="overflow-x:auto; margin-top:10px;">
                <table style="
                    width:100%;
                    border-collapse:collapse;
                    background:#fff;
                ">
                    <thead>
                        <tr style="background:#f5f5f5;">
                            <th style="border:1px solid #ddd; padding:8px;">Login</th>
                            <th style="border:1px solid #ddd; padding:8px;">F.I.Sh</th>
                            <th style="border:1px solid #ddd; padding:8px;">Lavozim / Mutaxassislik</th>
                            <th style="border:1px solid #ddd; padding:8px;">Telefon</th>
                            <th style="border:1px solid #ddd; padding:8px;">Holati</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows}
                    </tbody>
                </table>
            </div>
        """

        return mark_safe(html)

    group_users_table.short_description = "Ushbu guruhdagi hodimlar"


try:
    admin.site.unregister(Group)
except NotRegistered:
    pass

admin.site.register(Group, CustomGroupAdmin)