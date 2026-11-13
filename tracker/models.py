from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models, transaction
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

# Single source of truth for choices: add a status/type/priority here and nowhere else.
STATUSES = [("todo", "To Do"), ("in_progress", "In Progress"), ("done", "Done")]
PRIORITIES = [("low", "Low"), ("medium", "Medium"), ("high", "High")]
TYPES = [("epic", "Epic"), ("story", "Story"), ("task", "Task"), ("subtask", "Sub-task")]
ALLOWED_CHILDREN = {"epic": ("story", "task"), "story": ("subtask",), "task": ("subtask",), "subtask": ()}


class Project(models.Model):
    key = models.CharField(max_length=5, unique=True,
                           validators=[RegexValidator(r"^[A-Z]{2,5}$", "Use 2-5 uppercase letters.")])
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_archived = models.BooleanField(default=False)
    next_issue_number = models.PositiveIntegerField(default=1, editable=False)

    def __str__(self):
        return f"{self.key} - {self.name}"


class Issue(models.Model):
    STATUS_CHOICES = STATUSES  # lets templates build status dropdowns

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="issues")
    number = models.PositiveIntegerField(editable=False)
    type = models.CharField(max_length=10, choices=TYPES, default="task")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=STATUSES, default="todo")
    priority = models.CharField(max_length=8, choices=PRIORITIES, default="medium")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name="assigned")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, editable=False,
                                 on_delete=models.SET_NULL, related_name="reported")
    due_date = models.DateField(null=True, blank=True)
    estimate_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("project", "number")
        ordering = ["number"]

    def __str__(self):
        return f"{self.key} {self.title}"

    @property
    def key(self):
        return f"{self.project.key}-{self.number}"

    def get_absolute_url(self):
        return reverse("issue", args=[self.project.key, self.number])

    def clean(self):
        p = self.parent
        if p and self.type not in ALLOWED_CHILDREN[p.type]:
            raise ValidationError({"parent": f"A {self.get_type_display()} can't sit under a {p.get_type_display()}."})
        if self.type == "subtask" and not p:
            raise ValidationError({"parent": "A sub-task needs a parent story or task."})
        if p and self.project_id and p.project_id != self.project_id:
            raise ValidationError({"parent": "Parent must be in the same project."})
        if self.pk and self.children.exclude(type__in=ALLOWED_CHILDREN[self.type]).exists():
            raise ValidationError({"type": "Existing child issues don't fit this type."})

    def save(self, *args, **kwargs):
        if self._state.adding and not self.number:
            with transaction.atomic():
                p = Project.objects.select_for_update().get(pk=self.project_id)
                self.number = p.next_issue_number
                Project.objects.filter(pk=p.pk).update(next_issue_number=p.next_issue_number + 1)
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)

    def descendant_ids(self):
        ids, level = [self.pk], [self.pk]
        while level:
            level = list(Issue.objects.filter(parent_id__in=level).values_list("pk", flat=True))
            ids += level
        return ids

    def hours_logged(self):
        """Own work logs plus all descendants'."""
        return WorkLog.objects.filter(issue_id__in=self.descendant_ids()).aggregate(s=Sum("hours"))["s"] or Decimal(0)

    def progress(self):
        """Percent of direct children that are done; None if no children."""
        total = self.children.count()
        return self.children.filter(status="done").count() * 100 // total if total else None


class WorkLog(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="worklogs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="worklogs")
    date = models.DateField()
    hours = models.DecimalField(max_digits=4, decimal_places=2,
                                validators=[MinValueValidator(Decimal("0.25")), MaxValueValidator(Decimal("24"))])
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def clean(self):
        if self.date and self.date > timezone.localdate():
            raise ValidationError({"date": "Date can't be in the future."})
