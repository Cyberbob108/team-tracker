from datetime import date, timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import IssueForm, ProjectForm, WorkLogForm
from .models import PRIORITIES, STATUSES, TYPES, Issue, Project, WorkLog

User = get_user_model()


def staff_only(view):
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper


def back(request, fallback):
    nxt = request.POST.get("next", "")
    if nxt and url_has_allowed_host_and_scheme(nxt, {request.get_host()}):
        return redirect(nxt)
    return redirect(fallback)


def week_range():
    today = timezone.localdate()
    mon = today - timedelta(days=today.weekday())
    return mon, mon + timedelta(days=6)


def date_range(request):
    mon, sun = week_range()

    def parse(s, default):
        try:
            return date.fromisoformat(s)
        except (TypeError, ValueError):
            return default
    return parse(request.GET.get("start"), mon), parse(request.GET.get("end"), sun)


# ---------- projects ----------
@login_required
def project_list(request):
    ps = Project.objects.annotate(open_count=Count("issues", filter=~Q(issues__status="done"))).order_by("key")
    return render(request, "projects.html", {"projects": ps})


@staff_only
def project_edit(request, key=None):
    p = get_object_or_404(Project, key=key) if key else None
    form = ProjectForm(request.POST or None, instance=p)
    if request.method == "POST" and form.is_valid():
        return redirect("project", form.save().key)
    return render(request, "form.html", {"form": form, "title": f"Edit {p.key}" if p else "New project"})


@login_required
def project_detail(request, key):
    p = get_object_or_404(Project, key=key)
    g = request.GET
    qs = p.issues.select_related("project", "assignee")
    if g.get("type") in dict(TYPES):
        qs = qs.filter(type=g["type"])
    if g.get("status") in dict(STATUSES):
        qs = qs.filter(status=g["status"])
    if g.get("assignee", "").isdigit():
        qs = qs.filter(assignee_id=g["assignee"])
    if g.get("q"):
        qs = qs.filter(title__icontains=g["q"])
    if g.get("epic", "").isdigit():
        epic = p.issues.filter(pk=g["epic"], type="epic").first()
        if epic:
            qs = qs.filter(pk__in=epic.descendant_ids())
    issues = list(qs)
    return render(request, "project.html", {
        "project": p, "issues": issues, "view": "list" if g.get("view") == "list" else "board",
        "cols": [(c, label, [i for i in issues if i.status == c]) for c, label in STATUSES],
        "epics": p.issues.filter(type="epic"), "users": User.objects.filter(is_active=True),
        "types": TYPES, "statuses": STATUSES,
    })


# ---------- issues ----------
@login_required
def issue_detail(request, key, number):
    i = get_object_or_404(Issue.objects.select_related("project", "parent", "assignee", "reporter"),
                          project__key=key, number=number)
    logs = list(i.worklogs.select_related("user"))
    return render(request, "issue.html", {
        "i": i, "children": i.children.select_related("project", "assignee"), "logs": logs,
        "own": sum(w.hours for w in logs), "total": i.hours_logged(), "progress": i.progress(),
        "form": WorkLogForm(initial={"date": timezone.localdate()}),
    })


@login_required
def issue_edit(request, key, number=None):
    if number:
        i = get_object_or_404(Issue, project__key=key, number=number)
        p = i.project
    else:
        i, p = None, get_object_or_404(Project, key=key)
    initial = {}
    if i is None and request.GET.get("parent", "").isdigit():
        par = p.issues.filter(pk=request.GET["parent"]).first()
        if par:
            initial = {"parent": par, "type": "story" if par.type == "epic" else "subtask"}
    form = IssueForm(request.POST or None, instance=i, project=p, initial=initial)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if not obj.reporter_id:
            obj.reporter = request.user
        obj.save()
        return redirect(obj)
    return render(request, "form.html", {"form": form, "title": i.key if i else f"New issue in {p.key}"})


@require_POST
@login_required
def issue_status(request, key, number):
    i = get_object_or_404(Issue, project__key=key, number=number)
    if request.POST.get("status") in dict(STATUSES):
        i.status = request.POST["status"]
        i.save(update_fields=["status", "updated_at"])
    return back(request, i)


@require_POST
@staff_only
def issue_delete(request, key, number):
    i = get_object_or_404(Issue, project__key=key, number=number)
    p = i.project
    i.delete()
    return redirect("project", p.key)


# ---------- work logs ----------
@require_POST
@login_required
def worklog_add(request, key, number):
    i = get_object_or_404(Issue, project__key=key, number=number)
    form = WorkLogForm(request.POST)
    if form.is_valid():
        w = form.save(commit=False)
        w.issue, w.user = i, request.user
        w.save()
    else:
        messages.error(request, "; ".join(f"{k}: {' '.join(v)}" for k, v in form.errors.items()))
    return back(request, i)


def _own_log_or_403(request, pk):
    w = get_object_or_404(WorkLog.objects.select_related("issue__project"), pk=pk)
    if not (request.user.is_staff or w.user_id == request.user.id):
        raise PermissionDenied
    return w


@login_required
def worklog_edit(request, pk):
    w = _own_log_or_403(request, pk)
    form = WorkLogForm(request.POST or None, instance=w)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(w.issue)
    return render(request, "form.html", {"form": form, "title": f"Edit work log on {w.issue.key}"})


@require_POST
@login_required
def worklog_delete(request, pk):
    w = _own_log_or_403(request, pk)
    issue = w.issue
    w.delete()
    return redirect(issue)


# ---------- my work & team dashboard ----------
@login_required
def my_work(request):
    mon, sun = week_range()
    issues = (Issue.objects.filter(assignee=request.user).exclude(status="done")
              .select_related("project").order_by("project__key", "number"))
    hours = WorkLog.objects.filter(user=request.user, date__range=(mon, sun)).aggregate(s=Sum("hours"))["s"] or 0
    return render(request, "my_work.html", {"issues": issues, "hours": hours, "today": timezone.localdate()})


@staff_only
def dashboard(request):
    start, end = date_range(request)
    today = timezone.localdate()
    logs = WorkLog.objects.filter(date__range=(start, end))
    hours = dict(logs.order_by().values_list("user_id").annotate(s=Sum("hours")))
    open_issues = Issue.objects.exclude(status="done")
    rows = []
    for u in User.objects.filter(is_active=True).order_by("username"):
        mine = open_issues.filter(assignee=u)
        rows.append({"user": u, "hours": hours.get(u.pk, 0), "open": mine.count(),
                     "in_progress": mine.filter(status="in_progress").count(),
                     "overdue": mine.filter(due_date__lt=today).count()})
    per_project = (logs.order_by().values("issue__project__key", "issue__project__name")
                   .annotate(s=Sum("hours")).order_by("issue__project__key"))
    return render(request, "dashboard.html", {
        "start": start, "end": end, "rows": rows, "per_project": per_project,
        "unassigned": open_issues.filter(assignee=None).select_related("project"),
    })


@staff_only
def person_logs(request, user_id):
    u = get_object_or_404(User, pk=user_id)
    start, end = date_range(request)
    logs = (WorkLog.objects.filter(user=u, date__range=(start, end)).select_related("issue__project")
            .order_by("issue__project__key", "issue__number", "date"))
    return render(request, "person.html", {"u": u, "logs": logs, "start": start, "end": end,
                                           "total": sum(w.hours for w in logs)})
