"""Admin-only results pages. Every view requires a staff login."""

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from . import exports, stats
from .models import Answer, Group, Program, Question, Session

EXPORT_FILTERS = {
    "program": "session__group__program_id",
    "group": "session__group_id",
    "module": "session__module_id",
}


def visible_comments(sessions_summaries, **filters):
    """Comments, newest first, only from sessions that meet the anonymity threshold."""
    visible = [pk for pk, summary in sessions_summaries.items() if summary.visible]
    return (
        Answer.objects.filter(
            question__kind=Question.TEXT, response__session__in=visible, **filters
        )
        .exclude(text="")
        .select_related("response__session__module")
        .order_by("-response__created_at")
    )


@staff_member_required
def home(request):
    programs = Program.objects.prefetch_related("groups")
    group_summaries = stats.summaries("session__group")
    rows = []
    for program in programs:
        for group in program.groups.annotate(session_total=Count("sessions")):
            rows.append(
                {
                    "group": group,
                    "summary": group_summaries.get(group.pk, stats.Summary()),
                    "alerts": len(stats.module_alerts(group)),
                }
            )
    return render(request, "feedback/dashboard/home.html", {"programs": programs, "rows": rows})


@staff_member_required
def group_detail(request, pk):
    group = get_object_or_404(Group.objects.select_related("program"), pk=pk)
    sessions = list(group.sessions.select_related("module"))
    session_summaries = stats.summaries("session", session__group=group)
    module_summaries = stats.summaries("session__module", session__group=group)
    today = timezone.localdate()

    session_rows = [
        {"session": s, "summary": session_summaries.get(s.pk, stats.Summary()), "past": s.date <= today}
        for s in sessions
    ]
    module_rows = [
        {"module": m, "summary": module_summaries.get(m.pk, stats.Summary())}
        for m in group.program.modules.all()
    ]

    trend = {
        "labels": [f"S{row['session'].number}" for row in session_rows if row["past"]],
        "series": {
            stats.SCALE_LABELS[code]: [row["summary"].chart_value(code) for row in session_rows if row["past"]]
            for code in stats.SCALE_CODES
        },
    }
    modules_chart = {
        "labels": [f"M{row['module'].number}" for row in module_rows],
        "series": {
            stats.SCALE_LABELS[code]: [row["summary"].chart_value(code) for row in module_rows]
            for code in stats.SCALE_CODES
        },
        "pace": {
            label: [
                round(row["summary"].pace_share(value) * 100) if row["summary"].visible else None
                for row in module_rows
            ]
            for value, label in stats.PACE_LABELS.items()
        },
    }

    return render(
        request,
        "feedback/dashboard/group.html",
        {
            "group": group,
            "overall": stats.summary(session__group=group),
            "alerts": stats.module_alerts(group),
            "session_rows": session_rows,
            "module_rows": module_rows,
            "trend": trend,
            "modules_chart": modules_chart,
            "comments": visible_comments(session_summaries, response__session__group=group)[:15],
            "min_responses": settings.PULSE_MIN_RESPONSES,
        },
    )


@staff_member_required
def session_detail(request, pk):
    session = get_object_or_404(Session.objects.select_related("group__program", "module"), pk=pk)
    session_summaries = stats.summaries("session", session=session)
    return render(
        request,
        "feedback/dashboard/session.html",
        {
            "session": session,
            "group": session.group,
            "summary": session_summaries.get(session.pk, stats.Summary()),
            "comments": visible_comments(session_summaries),
            "min_responses": settings.PULSE_MIN_RESPONSES,
        },
    )


@staff_member_required
def program_detail(request, pk):
    """The same modules compared across all groups of a program."""
    program = get_object_or_404(Program, pk=pk)
    groups = list(program.groups.all())
    modules = list(program.modules.all())
    by_group = {
        group.pk: stats.summaries("session__module", session__group=group) for group in groups
    }
    combined = stats.summaries("session__module", session__group__program=program)

    rows = []
    for module in modules:
        rows.append(
            {
                "module": module,
                "combined": combined.get(module.pk, stats.Summary()),
                "groups": [by_group[g.pk].get(module.pk, stats.Summary()) for g in groups],
            }
        )
    chart = {
        "labels": [f"M{m.number}" for m in modules],
        "series": {
            group.name: [
                by_group[group.pk].get(m.pk, stats.Summary()).chart_value() for m in modules
            ]
            for group in groups
        },
    }
    return render(
        request,
        "feedback/dashboard/program.html",
        {"program": program, "groups": groups, "rows": rows, "chart": chart},
    )


@staff_member_required
def export(request, file_format):
    filters = {
        field: request.GET[param]
        for param, field in EXPORT_FILTERS.items()
        if request.GET.get(param, "").isdigit()
    }
    rows = exports.export_rows(**filters)
    stamp = timezone.localtime().strftime("%Y-%m-%d")
    if file_format == "csv":
        content, content_type = exports.to_csv(rows), "text/csv; charset=utf-8"
    elif file_format == "xlsx":
        content = exports.to_xlsx(rows)
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        raise Http404
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="pulse-check-{stamp}.{file_format}"'
    return response
