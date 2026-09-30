# Pulse Check VCS — plan

Anonymous feedback after every lesson. Pilot on the AI Engineering course starting **2026-10-19**, designed so any VCS course can use it without code changes.

## Principles

- **No personal data.** No names, emails, or logins for students. Only a random browser ID to prevent double answers.
- **Same core questions everywhere**, so courses and modules can be compared.
- **Questionnaire in Lithuanian.**
- **Results only for admin** (lecturer view comes later).
- **Anonymity threshold:** a session's results are shown only once it has at least **3** answers.

## Data model

```
Program            e.g. "AI Engineering". The course template, reused by every group.
 └─ Module         e.g. "Module 2: LLM APIs" (ordered)

Group              one run of a Program: "AI Engineering 2026-10", start/end date,
 │                 schedule (weekdays, 18:00–21:30), public link token
 └─ Session        one lesson: date, number (1–65), module, topic
     └─ Response   one student's answers to one session
         └─ Answer one value per question

QuestionSet        versioned question list. A response always points at the exact
 └─ Question       version it answered, so rewording never mixes results.
```

Sessions are **generated automatically** from a group's start date, weekdays and session count, so admin doesn't type 65 lessons by hand. Admin only assigns module ranges and optional topics.

## Student flow

1. Lecturer shares **one link per group** once (e.g. `/g/abc123`).
2. The link opens today's session (or the latest one still open). The form stays open for **48 h** after the lesson.
3. Student answers 4 closed questions + an optional comment, then submits. One answer per device per session.

### Draft questions (Lithuanian, to confirm)

| # | Question | Answer |
|---|----------|--------|
| 1 | Kaip vertinate paskaitos tempą? | Per lėtas / Tinkamas / Per greitas |
| 2 | Kaip vertinate lektoriaus darbą? | 1–5 |
| 3 | Ar teorija buvo aiški? | 1–5 |
| 4 | Ar praktinės užduotys buvo naudingos ir suprantamos? | 1–5 |
| 5 | Papildomi komentarai (neprivaloma) | free text |

## Admin

- **Django admin panel:** manage programs, modules, groups, sessions and questions.
- **Dashboard:** per-session results, trends across a group's sessions, module-vs-module comparison, and the same module compared across groups.
- **Export:** CSV / Excel with filters (program, group, module, date range).
- **Alerts:** when a module's last session ends, flag any average below a threshold (e.g. < 3.5) or pace skewed "too fast" or "too slow". Shown on the dashboard, with email later.

## Tech stack

- **Python 3.12 + Django 5** (models, forms and admin out of the box)
- **SQLite** locally, **PostgreSQL** on the server
- **Chart.js** for dashboard charts, **openpyxl** for Excel export
- **Docker** so the same setup runs on a cheap VPS now and on a VCS server later
- Hosting for the pilot: a small VPS (e.g. Hetzner, ~€5/month) or Render

## Milestones

| By | Goal |
|----|------|
| ✅ Sep 30 | Models, admin panel, automatic session generation |
| Oct 10 | Student form (Lithuanian, mobile-friendly), one answer per device |
| Oct 14 | CSV/Excel export, basic per-session results |
| Oct 17 | Deployed on a server, tested end to end with a fake group |
| **Oct 19** | **Pilot starts with AI Engineering** |
| Nov | Dashboard charts, module comparison, alerts |

## Decisions

- AI Engineering runs **Mon, Wed, Thu 18:00–21:30**. Lithuanian public holidays are skipped automatically, which puts the pilot's last lesson on **2027-03-24**.
- Questions 2–4 use a **1–5** scale.
- Modules: see `feedback/management/commands/seed_ai_engineering.py` (M1 S1–17 … M7 S58–65).
