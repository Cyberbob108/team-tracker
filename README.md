# Team Tracker

A deliberately small Jira-style tracker for a ~15-person team: projects, epics, stories, tasks, sub-tasks, work logs, and a manager dashboard.

## Run locally
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python manage.py makemigrations tracker   # first time only; then commit tracker/migrations/
    python manage.py migrate
    python manage.py seed_demo          # optional demo data (admin/admin123, alice/demo1234 ...)
    python manage.py runserver          # http://127.0.0.1:8000

Without demo data: `python manage.py createsuperuser`.

## Roles
- **Manager** = user with "staff status" (create in `/admin/`). Can create/edit projects, delete issues, see the Dashboard.
- **Member** = any other active user. Can create/edit issues, change status, log time (edit/delete own logs only).
- Add team members in `/admin/` > Users.

## Rules
- Epic (no parent) > Story/Task (optional epic parent) > Sub-task (required story/task parent).
- Issue keys are per project (WEB-1, WEB-2...). Hours and epic progress are computed on read.

## Tests
    python manage.py test

## Production notes
Set `DEBUG=0`, `SECRET_KEY`, `ALLOWED_HOSTS`, and `DATABASE_URL` (Postgres: also `pip install "psycopg[binary]"`). Serve with gunicorn (`config.wsgi`) behind HTTPS; static files for the admin need `collectstatic` or WhiteNoise.

## Push to GitHub
    git init -b main && git add . && git commit -m "Initial commit"
    git remote add origin git@github.com:<you>/team-tracker.git && git push -u origin main

See `BACKLOG.md` for what is intentionally missing and `AGENTS.md` for AI-agent conventions.
