# Pulse Check VCS

Anonymous per-lesson feedback for Vilnius Coding School courses. See [PLAN.md](PLAN.md) for the design and [DEPLOY.md](DEPLOY.md) for putting it on a server.

## Run locally

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py seed_ai_engineering   # AI Engineering program + 7 modules
uv run python manage.py demo_data              # optional: a demo group with fake answers
uv run python manage.py runserver
```

- Admin panel: http://127.0.0.1:8000/admin/
- Results dashboard: http://127.0.0.1:8000/dashboard/
- Student form: the link shown on each group's page in the admin panel (`/g/<code>/`)

Remove the demo data with `uv run python manage.py demo_data --remove`.

## Tests

```bash
uv run python manage.py test
```

## How it works

| Where | What |
|---|---|
| `feedback/models.py` | Program → Module, Group → Session → Response → Answer, versioned questions |
| `feedback/views.py` | Student form: finds the open session, one answer per device per session |
| `feedback/stats.py` | Averages, pace shares, the minimum-3 rule, module alerts |
| `feedback/dashboard_views.py` | Admin-only results pages and export |
| `feedback/exports.py` | CSV / Excel files |
| `config/settings.py` | Thresholds (`PULSE_MIN_RESPONSES`, `PULSE_ALERT_*`) and server settings |
