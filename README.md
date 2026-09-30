# Pulse Check VCS

Anonymous per-lesson feedback for Vilnius Coding School courses. See [PLAN.md](PLAN.md) for the design.

## Run locally

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Admin panel: http://127.0.0.1:8000/admin/
