from django.urls import path
from . import views

app_name = "website"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("services/", views.services, name="services"),
    path("doctors/", views.doctors, name="doctors"),
    path("news/", views.news, name="news"),
    path("contact/", views.contact, name="contact"),
]