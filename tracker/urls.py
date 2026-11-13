from django.urls import path

from . import views

urlpatterns = [
    path("", views.my_work, name="my_work"),
    path("projects/", views.project_list, name="projects"),
    path("projects/new/", views.project_edit, name="project_new"),
    path("projects/<str:key>/", views.project_detail, name="project"),
    path("projects/<str:key>/edit/", views.project_edit, name="project_edit"),
    path("projects/<str:key>/issues/new/", views.issue_edit, name="issue_new"),
    path("issues/<str:key>/<int:number>/", views.issue_detail, name="issue"),
    path("issues/<str:key>/<int:number>/edit/", views.issue_edit, name="issue_edit"),
    path("issues/<str:key>/<int:number>/status/", views.issue_status, name="issue_status"),
    path("issues/<str:key>/<int:number>/delete/", views.issue_delete, name="issue_delete"),
    path("issues/<str:key>/<int:number>/log/", views.worklog_add, name="worklog_add"),
    path("worklogs/<int:pk>/edit/", views.worklog_edit, name="worklog_edit"),
    path("worklogs/<int:pk>/delete/", views.worklog_delete, name="worklog_delete"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/user/<int:user_id>/", views.person_logs, name="person_logs"),
]
