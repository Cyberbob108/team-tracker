from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from .models import Issue, Project, WorkLog
from .views import week_range

User = get_user_model()


class TrackerTests(TestCase):
    def setUp(self):
        self.boss = User.objects.create_user("boss", password="x", is_staff=True)
        self.ann = User.objects.create_user("ann", password="x")
        self.bob = User.objects.create_user("bob", password="x")
        self.p = Project.objects.create(key="WEB", name="Web")
        self.epic = self.mk("epic")
        self.story = self.mk("story", parent=self.epic)
        self.sub = self.mk("subtask", parent=self.story)

    def mk(self, type, **kw):
        return Issue.objects.create(project=self.p, type=type, title=type, **kw)

    def log(self, issue, hours, day, user=None):
        return WorkLog.objects.create(issue=issue, user=user or self.ann, date=day, hours=Decimal(hours))

    def test_numbering_is_sequential_per_project(self):
        other = Project.objects.create(key="API", name="Api")
        self.assertEqual([self.epic.key, self.story.key, self.sub.key], ["WEB-1", "WEB-2", "WEB-3"])
        self.assertEqual(Issue.objects.create(project=other, type="task", title="t").key, "API-1")

    def test_hierarchy_rules(self):
        for type_, parent in (("epic", self.epic), ("story", self.story), ("subtask", None),
                              ("subtask", self.epic), ("task", self.story)):
            with self.assertRaises(ValidationError):
                Issue(project=self.p, type=type_, parent=parent, title="x").clean()
        Issue(project=self.p, type="task", parent=self.epic, title="ok").clean()
        Issue(project=self.p, type="task", title="standalone").clean()

    def test_type_change_with_children_rejected(self):
        self.epic.type = "task"
        with self.assertRaises(ValidationError):
            self.epic.clean()

    def test_hours_roll_up_and_progress(self):
        today = timezone.localdate()
        self.log(self.sub, "2.5", today)
        self.log(self.story, "1", today)
        self.assertEqual(self.sub.hours_logged(), Decimal("2.5"))
        self.assertEqual(self.epic.hours_logged(), Decimal("3.5"))
        self.assertEqual(self.epic.progress(), 0)
        self.story.status = "done"
        self.story.save()
        self.assertEqual(self.epic.progress(), 100)

    def test_future_worklog_rejected(self):
        with self.assertRaises(ValidationError):
            WorkLog(issue=self.sub, user=self.ann, date=timezone.localdate() + timedelta(days=1), hours=1).clean()

    def test_dashboard_is_staff_only(self):
        self.client.force_login(self.ann)
        self.assertEqual(self.client.get("/dashboard/").status_code, 403)
        self.client.force_login(self.boss)
        self.assertEqual(self.client.get("/dashboard/").status_code, 200)

    def test_dashboard_hours_by_date_range(self):
        mon, _ = week_range()
        self.log(self.sub, "2", mon)
        self.log(self.sub, "3", mon - timedelta(days=7))
        self.client.force_login(self.boss)
        row = lambda r: next(x for x in r.context["rows"] if x["user"] == self.ann)
        self.assertEqual(row(self.client.get("/dashboard/"))["hours"], Decimal("2"))
        last = self.client.get("/dashboard/", {"start": (mon - timedelta(days=7)).isoformat(),
                                               "end": (mon - timedelta(days=1)).isoformat()})
        self.assertEqual(row(last)["hours"], Decimal("3"))

    def test_worklog_ownership(self):
        w = self.log(self.sub, "1", timezone.localdate())
        self.client.force_login(self.bob)
        self.assertEqual(self.client.post(f"/worklogs/{w.pk}/delete/").status_code, 403)
        self.client.force_login(self.ann)
        self.assertEqual(self.client.post(f"/worklogs/{w.pk}/delete/").status_code, 302)

    def test_issue_form_enforces_hierarchy_and_sets_reporter(self):
        self.client.force_login(self.ann)
        base = {"title": "New", "status": "todo", "priority": "medium"}
        bad = self.client.post("/projects/WEB/issues/new/", {**base, "type": "subtask"})
        self.assertEqual(bad.status_code, 200)
        self.assertFalse(Issue.objects.filter(title="New").exists())
        ok = self.client.post("/projects/WEB/issues/new/", {**base, "type": "story", "parent": self.epic.pk})
        self.assertEqual(ok.status_code, 302)
        self.assertEqual(Issue.objects.get(title="New").reporter, self.ann)

    def test_pages_load(self):
        self.client.force_login(self.ann)
        for url in ("/", "/projects/", "/projects/WEB/", f"/projects/WEB/?view=list&type=story&epic={self.epic.pk}",
                    f"/issues/WEB/{self.story.number}/", f"/issues/WEB/{self.story.number}/edit/", "/projects/WEB/issues/new/"):
            self.assertEqual(self.client.get(url).status_code, 200, url)
