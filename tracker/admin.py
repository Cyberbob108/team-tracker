from django.contrib import admin

from .models import Issue, Project, WorkLog

admin.site.register(Project, list_display=("key", "name", "is_archived"))
admin.site.register(Issue, list_display=("__str__", "type", "status", "assignee"), list_filter=("project", "type", "status"))
admin.site.register(WorkLog, list_display=("issue", "user", "date", "hours"))
