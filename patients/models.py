from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _


class Owner(models.Model):
    owner_code = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        verbose_name=_("Egasi kodi")
    )
    full_name = models.CharField(
        max_length=255,
        verbose_name=_("Egasi F.I.Sh")
    )
    phone = models.CharField(
        max_length=20,
        unique=True,
        verbose_name=_("Telefon")
    )
    telegram_id = models.BigIntegerField(
        blank=True,
        null=True,
        unique=True,
        verbose_name=_("Telegram ID")
    )
    address = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Manzil")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Ro‘yxatga olingan vaqt")
    )

    class Meta:
        verbose_name = _("Hayvon egasi")
        verbose_name_plural = _("Hayvon egalari")

    def save(self, *args, **kwargs):
        if not self.owner_code:
            last_owner = Owner.objects.order_by("-id").first()
            next_id = 1 if not last_owner else last_owner.id + 1
            self.owner_code = f"EGA-{next_id:06d}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.owner_code} | {self.full_name} | {self.phone}"


class Pet(models.Model):
    ANIMAL_TYPES = [
        ("dog", _("It")),
        ("cat", _("Mushuk")),
        ("cow", _("Sigir")),
        ("horse", _("Ot")),
        ("sheep", _("Qo‘y")),
        ("goat", _("Echki")),
        ("bird", _("Qush")),
        ("other", _("Boshqa")),
    ]

    pet_code = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        verbose_name=_("Hayvon kodi")
    )
    owner = models.ForeignKey(
        Owner,
        on_delete=models.CASCADE,
        verbose_name=_("Egasi")
    )
    name = models.CharField(
        max_length=100,
        verbose_name=_("Hayvon nomi")
    )
    animal_type = models.CharField(
        max_length=50,
        choices=ANIMAL_TYPES,
        verbose_name=_("Hayvon turi")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Ro‘yxatga olingan vaqt")
    )

    class Meta:
        verbose_name = _("Hayvon")
        verbose_name_plural = _("Hayvonlar")

    def save(self, *args, **kwargs):
        if not self.pet_code:
            last_pet = Pet.objects.order_by("-id").first()
            next_id = 1 if not last_pet else last_pet.id + 1
            self.pet_code = f"HAY-{next_id:06d}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.pet_code} | {self.name} | {self.owner.full_name}"


class DoctorProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        verbose_name=_("Doktor akkaunti")
    )
    full_name = models.CharField(
        max_length=255,
        verbose_name=_("F.I.Sh")
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("Telefon")
    )
    specialization = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Mutaxassisligi")
    )
    experience = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Ish tajribasi")
    )
    resume = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Rezyume")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Faolmi?")
    )
    last_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        verbose_name=_("Oxirgi kenglik")
    )
    last_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        verbose_name=_("Oxirgi uzunlik")
    )
    last_location_accuracy = models.FloatField(
        blank=True,
        null=True,
        verbose_name=_("Lokatsiya aniqligi")
    )
    last_location_updated_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("Oxirgi lokatsiya vaqti")
    )
    location_tracking_enabled = models.BooleanField(
        default=False,
        verbose_name=_("Geolokatsiya tracking yoqilganmi?")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Yaratilgan vaqt")
    )

    class Meta:
        verbose_name = _("Veterinar doktor")
        verbose_name_plural = _("Veterinar doktorlar")

    def __str__(self):
        return self.full_name


class NewPatient(models.Model):
    STATUS_CHOICES = [
        ("new", _("Yangi ariza")),
        ("assigned_to_vet", _("Veterinarga yuborildi")),
        ("sent_to_lab", _("Laboratoriyaga yuborildi")),
        ("sent_to_diagnostic", _("Diagnostikaga yuborildi")),
        ("returned_to_vet", _("Veterinarga qaytdi")),
        ("completed", _("Yakunlandi")),
        ("cancelled", _("Bekor qilindi")),

        # Eski yozuvlar buzilmasligi uchun vaqtincha qoldiramiz
        ("accepted", _("Qabul qilindi")),
        ("rejected", _("Rad etildi")),
    ]

    ANIMAL_TYPES = Pet.ANIMAL_TYPES

    patient_code = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        verbose_name=_("Bemor kodi")
    )
    full_name = models.CharField(
        max_length=255,
        verbose_name=_("F.I.Sh")
    )
    phone = models.CharField(
        max_length=20,
        verbose_name=_("Telefon")
    )
    telegram_id = models.BigIntegerField(
        unique=True,
        verbose_name=_("Telegram ID")
    )
    telegram_username = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Telegram username")
    )

    animal_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Hayvon nomi")
    )
    animal_type = models.CharField(
        max_length=50,
        choices=ANIMAL_TYPES,
        blank=True,
        null=True,
        verbose_name=_("Hayvon turi")
    )

    selected_doctor = models.ForeignKey(
        DoctorProfile,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_("Tanlangan doktor")
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="new",
        verbose_name=_("Holati")
    )
    note = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Izoh")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Kelgan vaqti")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Yangilangan vaqt")
    )

    class Meta:
        verbose_name = _("Yangi bemor")
        verbose_name_plural = _("Yangi bemorlar")

    def save(self, *args, **kwargs):
        if not self.patient_code:
            last_patient = NewPatient.objects.order_by("-id").first()
            next_id = 1 if not last_patient else last_patient.id + 1
            self.patient_code = f"BEM-{next_id:06d}"

        super().save(*args, **kwargs)

    def __str__(self):
        doctor_name = (
            self.selected_doctor.full_name
            if self.selected_doctor
            else _("Doktor tanlanmagan")
        )
        animal = self.animal_name if self.animal_name else _("Hayvon yozilmagan")
        return f"{self.patient_code} | {self.full_name} | {animal} | {doctor_name}"


class Visit(models.Model):
    visit_code = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        verbose_name=_("Ko‘rik raqami")
    )
    doctor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_("Mas’ul doktor")
    )
    new_patient = models.ForeignKey(
        NewPatient,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_("Yangi bemor")
    )
    pet = models.ForeignKey(
        Pet,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("Hayvon")
    )

    complaint = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Shikoyat")
    )
    diagnosis = models.TextField(
        verbose_name=_("Tashxis")
    )
    treatment = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Davolash")
    )
    next_visit = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("Qayta kelish sanasi")
    )

    message = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Xabar matni")
    )
    is_sent = models.BooleanField(
        default=False,
        verbose_name=_("Yuborildimi?")
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Ko‘rik vaqti")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Yangilangan vaqt")
    )

    class Meta:
        verbose_name = _("Ko‘rik")
        verbose_name_plural = _("Ko‘riklar")

    def save(self, *args, **kwargs):
        if not self.visit_code:
            last_visit = Visit.objects.order_by("-id").first()
            next_id = 1 if not last_visit else last_visit.id + 1
            self.visit_code = f"KOR-{next_id:06d}"

        super().save(*args, **kwargs)

    def __str__(self):
        pet_name = self.pet.name if self.pet else _("Hayvon tanlanmagan")
        diagnosis_text = self.diagnosis[:30] if self.diagnosis else _("Tashxis yo‘q")
        return f"{self.visit_code} | {pet_name} | {diagnosis_text}"


class LabResult(models.Model):
    STATUS_CHOICES = [
        ("waiting", _("Kutilmoqda")),
        ("done", _("Tayyor")),
        ("sent_to_diagnostic", _("Diagnostikaga yuborildi")),
    ]

    patient = models.ForeignKey(
        NewPatient,
        on_delete=models.CASCADE,
        related_name="lab_results",
        verbose_name=_("Bemor")
    )
    veterinarian = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="lab_requests",
        verbose_name=_("Yuborgan veterinar")
    )
    lab_worker = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="lab_results_created",
        verbose_name=_("Laboratoriya xodimi")
    )
    analysis_name = models.CharField(
        max_length=255,
        verbose_name=_("Analiz nomi")
    )
    result = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Analiz natijasi")
    )
    comment = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Veterinar izohi")
    )

    lab_comment = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Laboratoriya izohi")
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="waiting",
        verbose_name=_("Holati")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Yaratilgan vaqt")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Yangilangan vaqt")
    )

    class Meta:
        verbose_name = _("Laboratoriya natijasi")
        verbose_name_plural = _("Laboratoriya natijalari")

    def __str__(self):
        return f"{self.patient.patient_code} | {self.analysis_name}"


class DiagnosticResult(models.Model):
    STATUS_CHOICES = [
        ("waiting", _("Kutilmoqda")),
        ("done", _("Tayyor")),
        ("returned_to_vet", _("Veterinarga qaytarildi")),
    ]

    patient = models.ForeignKey(
        NewPatient,
        on_delete=models.CASCADE,
        related_name="diagnostic_results",
        verbose_name=_("Bemor")
    )
    lab_result = models.ForeignKey(
        LabResult,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="diagnostic_results",
        verbose_name=_("Laboratoriya natijasi")
    )
    diagnostic_worker = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="diagnostic_results_created",
        verbose_name=_("Diagnostika xodimi")
    )
    conclusion = models.TextField(
        verbose_name=_("Diagnostik xulosa")
    )
    recommendation = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Tavsiya")
    )
       
    is_lab_updated = models.BooleanField(
        default=False,
        verbose_name=_("Laboratoriya natijasi tahrirlanganmi?")
    )

    lab_updated_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("Laboratoriya tahrirlagan vaqt")
    )

    lab_updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="lab_update_notifications",
        verbose_name=_("Laboratoriya tahrirlagan xodim")
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="waiting",
        verbose_name=_("Holati")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Yaratilgan vaqt")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Yangilangan vaqt")
    )

    class Meta:
        verbose_name = _("Diagnostika natijasi")
        verbose_name_plural = _("Diagnostika natijalari")

    def __str__(self):
        return f"{self.patient.patient_code} | Diagnostika"


class MyVisit(Visit):
    class Meta:
        proxy = True
        verbose_name = _("Mening bemorim")
        verbose_name_plural = _("Mening bemorlarim")
