from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),

    # Public web sayt
    path("", include("website.urls")),

    # Ichki dashboard
    path("dashboard/", include("dashboard.urls")),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()