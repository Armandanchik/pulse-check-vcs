from django.urls import path

from . import dashboard_views, views

app_name = "feedback"

urlpatterns = [
    path("g/<str:token>/", views.feedback_form, name="form"),
    path("dashboard/", dashboard_views.home, name="dashboard"),
    path("dashboard/program/<int:pk>/", dashboard_views.program_detail, name="program"),
    path("dashboard/group/<int:pk>/", dashboard_views.group_detail, name="group"),
    path("dashboard/session/<int:pk>/", dashboard_views.session_detail, name="session"),
    path("dashboard/export.<str:file_format>", dashboard_views.export, name="export"),
]
