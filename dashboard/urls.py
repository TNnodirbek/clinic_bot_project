from django.urls import path
from django.contrib.auth import views as auth_views

from . import views


urlpatterns = [
    # Login / Logout
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="dashboard/login.html"),
        name="login",
    ),
    path("logout/", views.custom_logout, name="logout"),

    # Dashboard home
    path("", views.dashboard_home, name="dashboard_home"),

    # Bemor kartasi va statuslar
    path(
        "patient-card/<int:patient_id>/",
        views.patient_card,
        name="patient_card",
    ),
    path(
        "patients-status/",
        views.patients_status,
        name="patients_status",
    ),

    # Administrator
    path(
        "administrator/",
        views.administrator_dashboard,
        name="administrator_dashboard",
    ),
    path(
        "administrator/quick-application/",
        views.create_quick_application,
        name="create_quick_application",
    ),
    path(
        "administrator/assign/<int:patient_id>/",
        views.assign_patient_to_vet,
        name="assign_patient_to_vet",
    ),
    path(
        "administrator/cancel/<int:patient_id>/",
        views.cancel_patient,
        name="cancel_patient",
    ),
    path(
        "administrator/redirect/<int:patient_id>/",
        views.redirect_patient_to_vet,
        name="redirect_patient_to_vet",
    ),
    path(
        "administrator/staff-location/",
        views.admin_staff_location,
        name="admin_staff_location",
    ),
    path(
        "administrator/history/",
        views.admin_history,
        name="admin_history",
    ),
    path(
        "administrator/history/redirect/<int:patient_id>/",
        views.admin_history_redirect_patient,
        name="admin_history_redirect_patient",
    ),
    path(
        "administrator/settings/",
        views.admin_settings,
        name="admin_settings",
    ),
    path(
        "administrator/profile/",
        views.admin_profile,
        name="admin_profile",
    ),

    # Veterinar
    path(
        "veterinar/",
        views.veterinar_dashboard,
        name="veterinar_dashboard",
    ),
    path(
        "veterinar/in-progress/<int:patient_id>/",
        views.vet_mark_in_progress,
        name="vet_mark_in_progress",
    ),
    path(
        "veterinar/action/<int:patient_id>/<str:stage>/",
        views.vet_update_application_stage,
        name="vet_update_application_stage",
    ),
    path(
        "veterinar/location/update/",
        views.vet_update_location,
        name="vet_update_location",
    ),
    path(
        "veterinar/complete/<int:patient_id>/",
        views.vet_complete_application,
        name="vet_complete_application",
    ),
    path(
        "veterinar/history/",
        views.vet_history,
        name="vet_history",
    ),
    path(
        "veterinar/reopen/<int:patient_id>/",
        views.vet_reopen_application,
        name="vet_reopen_application",
    ),
    path(
        "veterinar/profile/",
        views.vet_profile,
        name="vet_profile",
    ),
    path(
        "veterinar/send-to-lab/<int:patient_id>/",
        views.send_patient_to_lab,
        name="send_patient_to_lab",
    ),
    path(
        "veterinar/final-visit/<int:patient_id>/",
        views.final_visit,
        name="final_visit",
    ),
    path(
        "veterinar/edit-lab-request/<int:lab_result_id>/",
        views.edit_vet_lab_request,
        name="edit_vet_lab_request",
    ),

    # Laboratoriya
    path(
        "laboratoriya/",
        views.laboratoriya_dashboard,
        name="laboratoriya_dashboard",
    ),
    path(
        "laboratoriya/send-to-diagnostic/<int:lab_result_id>/",
        views.send_lab_result_to_diagnostic,
        name="send_lab_result_to_diagnostic",
    ),
    path(
        "laboratoriya/edit/<int:lab_result_id>/",
        views.edit_lab_result,
        name="edit_lab_result",
    ),
    path(
        "laboratoriya/view/<int:lab_result_id>/",
        views.view_lab_result,
        name="view_lab_result",
    ),

    # Diagnostika
    path(
        "diagnostika/",
        views.diagnostika_dashboard,
        name="diagnostika_dashboard",
    ),
    path(
        "diagnostika/return-to-vet/<int:diagnostic_id>/",
        views.return_diagnostic_to_vet,
        name="return_diagnostic_to_vet",
    ),
    path(
        "diagnostika/edit/<int:diagnostic_id>/",
        views.edit_diagnostic_result,
        name="edit_diagnostic_result",
    ),
    path(
        "diagnostika/view/<int:diagnostic_id>/",
        views.view_diagnostic_result,
        name="view_diagnostic_result",
    ),
]
