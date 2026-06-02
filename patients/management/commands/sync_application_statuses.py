from django.core.management.base import BaseCommand
from django.utils import timezone

from patients.models import NewPatient, DoctorProfile
from dashboard.views import (
    ACCEPTED_MARKER,
    IN_PROGRESS_MARKER,
    ON_WAY_MARKER,
    ARRIVED_MARKER,
    update_doctor_dynamic_status,
)


class Command(BaseCommand):
    help = "Sync old application statuses, service types, and doctor statuses."

    def handle(self, *args, **options):
        updated_patients = 0

        patients = NewPatient.objects.exclude(
            status__in=["new", "completed", "cancelled"]
        )

        for patient in patients:
            old_status = patient.status
            old_service_type = patient.service_type
            note = patient.note or ""

            new_status = old_status
            new_service_type = old_service_type

            if ARRIVED_MARKER in note:
                new_status = "arrived"
            elif ON_WAY_MARKER in note:
                new_status = "en_route"
            elif IN_PROGRESS_MARKER in note or ACCEPTED_MARKER in note:
                new_status = "accepted"

            if "Xavfli holat" in note or "Xavfli holatlar" in note:
                new_service_type = "danger"
            elif "Veterinar chaqirish" in note:
                new_service_type = "vet_call"
            elif "Klinikada davolash" in note:
                new_service_type = "clinic"

            update_fields = []

            if patient.status != new_status:
                patient.status = new_status
                update_fields.append("status")

            if patient.service_type != new_service_type:
                patient.service_type = new_service_type
                update_fields.append("service_type")

            if update_fields:
                patient.updated_at = timezone.now()
                update_fields.append("updated_at")
                patient.save(update_fields=update_fields)
                updated_patients += 1
                self.stdout.write(
                    f"{patient.patient_code}: "
                    f"status {old_status} -> {patient.status}, "
                    f"service_type {old_service_type} -> {patient.service_type}"
                )

        for doctor in DoctorProfile.objects.all():
            update_doctor_dynamic_status(doctor)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Updated patients: {updated_patients}. Doctor statuses synced."
            )
        )
