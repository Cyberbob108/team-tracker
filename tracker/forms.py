from django import forms
from django.contrib.auth import get_user_model

from .models import Issue, Project, WorkLog

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["key", "name", "description", "is_archived"]


class IssueForm(forms.ModelForm):
    class Meta:
        model = Issue
        fields = ["type", "parent", "title", "description", "status", "priority",
                  "assignee", "due_date", "estimate_hours"]
        widgets = {"due_date": DATE}

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.project = project or self.instance.project  # needed by Issue.clean()
        self.fields["parent"].queryset = (Issue.objects.filter(project=self.instance.project)
                                          .exclude(type="subtask").exclude(pk=self.instance.pk))
        self.fields["assignee"].queryset = get_user_model().objects.filter(is_active=True)


class WorkLogForm(forms.ModelForm):
    class Meta:
        model = WorkLog
        fields = ["date", "hours", "note"]
        widgets = {"date": DATE}
