from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from tracker.models import Issue, Project, WorkLog


class Command(BaseCommand):
    help = "Create demo users, projects, issues and work logs (demo passwords only!)"

    def handle(self, *args, **options):
        if Project.objects.exists():
            self.stdout.write("Projects already exist; skipping demo data.")
            return
        User = get_user_model()
        boss = User.objects.create_superuser("admin", password="admin123")
        members = [User.objects.create_user(n, password="demo1234") for n in ("alice", "bob", "carol", "dave")]
        today = timezone.localdate()
        for key, name in (("WEB", "Website"), ("API", "Backend API")):
            p = Project.objects.create(key=key, name=name)
            epic = Issue.objects.create(project=p, type="epic", title=f"{name} launch", reporter=boss, assignee=members[0])
            for n, m in enumerate(members[:3]):
                story = Issue.objects.create(project=p, type="story", parent=epic, title=f"Story {n + 1}", reporter=boss,
                                             assignee=m, status=("todo", "in_progress", "done")[n],
                                             due_date=today + timedelta(days=n * 3 - 2))
                sub = Issue.objects.create(project=p, type="subtask", parent=story, title=f"Sub-task for story {n + 1}",
                                           reporter=boss, assignee=m)
                WorkLog.objects.create(issue=sub, user=m, date=today - timedelta(days=n), hours=Decimal("2.5"), note="Demo")
        self.stdout.write("Done. Log in as admin/admin123 (manager) or alice/demo1234 (member).")
