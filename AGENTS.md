# Working on this repo (for AI coding agents)
- Stack: Django + server-rendered templates + SQLite/Postgres. Keep it boring.
- YAGNI: build only what was asked. Ideas go in BACKLOG.md, not in code.
- Choices (statuses, types, priorities) live in `tracker/models.py` only.
- Business rules belong in models; views stay thin.
- Every schema change needs a migration (`python manage.py makemigrations`).
- Run `python manage.py test` before committing; add a test for each new rule.
