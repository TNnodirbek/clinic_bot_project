from django.shortcuts import render
from patients.models import DoctorProfile


def home(request):
    return render(request, "website/home.html")


def about(request):
    return render(request, "website/about.html")


def services(request):
    return render(request, "website/services.html")


def doctors(request):
    doctors = DoctorProfile.objects.filter(is_active=True).order_by("full_name")
    return render(request, "website/doctors.html", {"doctors": doctors})


def news(request):
    return render(request, "website/news.html")


def contact(request):
    return render(request, "website/contact.html")
