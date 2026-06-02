import tempfile
import textwrap

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def _get_patient(visit):
    return (
        getattr(visit, "new_patient", None)
        or getattr(visit, "patient", None)
        or getattr(visit, "application", None)
    )


def _safe_text(value, default="-"):
    return str(value or default)


def _draw_wrapped(pdf, text, x, y, max_chars=86, line_height=14):
    for paragraph in _safe_text(text).splitlines() or ["-"]:
        for line in textwrap.wrap(paragraph, width=max_chars) or [""]:
            if y < 70:
                pdf.showPage()
                pdf.setFont("Helvetica", 10)
                y = A4[1] - 60

            pdf.drawString(x, y, line)
            y -= line_height

    return y


def generate_visit_pdf(visit):
    patient = _get_patient(visit)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp_file.close()

    pdf = canvas.Canvas(temp_file.name, pagesize=A4)
    width, height = A4
    y = height - 54

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawCentredString(width / 2, y, "VET Farm & Pet Clinic")
    y -= 24

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawCentredString(width / 2, y, "Yakuniy ko'rik xulosasi")
    y -= 34

    pdf.setFont("Helvetica", 10)
    info_rows = [
        ("Ko'rik kodi", getattr(visit, "visit_code", "-")),
        ("Mijoz", getattr(patient, "full_name", "-")),
        ("Telefon", getattr(patient, "phone", "-")),
        ("Hayvon", getattr(patient, "animal_name", "-")),
        ("Veterinar", getattr(getattr(visit, "doctor", None), "get_full_name", lambda: "-")()),
        ("Vaqt", getattr(visit, "created_at", "-")),
    ]

    for label, value in info_rows:
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(50, y, f"{label}:")
        pdf.setFont("Helvetica", 10)
        pdf.drawString(150, y, _safe_text(value))
        y -= 18

    y -= 8
    pdf.line(50, y, width - 50, y)
    y -= 24

    sections = [
        ("Shikoyat", getattr(visit, "complaint", "")),
        ("Umumiy xulosa", getattr(visit, "diagnosis", "")),
        ("Tavsiya", getattr(visit, "treatment", "")),
        ("Qo'shimcha izoh", getattr(visit, "message", "")),
    ]

    for title, body in sections:
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(50, y, f"{title}:")
        y -= 16
        pdf.setFont("Helvetica", 10)
        y = _draw_wrapped(pdf, body or "-", 50, y)
        y -= 14

    pdf.save()
    return temp_file.name
