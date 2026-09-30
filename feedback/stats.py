"""Aggregate responses into summaries for the dashboard.

Questions are matched by their stable `code`, so results stay comparable across
question-set versions and across courses.
"""

from collections import defaultdict
from dataclasses import dataclass, field

from django.conf import settings
from django.db.models import Avg, Count, Max
from django.utils import timezone

from .models import Answer, Question, Response

SCALE_CODES = ["lecturer", "theory", "practice"]
SCALE_LABELS = {"lecturer": "Lektorius", "theory": "Teorija", "practice": "Praktika"}
PACE_LABELS = dict(Question.PACE_CHOICES)


@dataclass
class Summary:
    responses: int = 0
    averages: dict = field(default_factory=dict)  # code -> float
    pace: dict = field(default_factory=dict)  # 1/2/3 -> count

    @property
    def visible(self):
        return self.responses >= settings.PULSE_MIN_RESPONSES

    @property
    def pace_total(self):
        return sum(self.pace.values())

    def pace_share(self, value):
        return self.pace.get(value, 0) / self.pace_total if self.pace_total else 0

    def average(self, code):
        return self.averages.get(code)

    @property
    def overall(self):
        """Mean of the 1–5 question averages: one number to compare modules or groups."""
        values = [self.averages[code] for code in SCALE_CODES if self.averages.get(code) is not None]
        return sum(values) / len(values) if values else None

    def chart_value(self, code=None):
        """Rounded average for charts, or None while below the anonymity threshold."""
        value = self.overall if code is None else self.average(code)
        return round(value, 2) if self.visible and value is not None else None

    def scale_rows(self):
        return [(SCALE_LABELS[code], self.averages.get(code)) for code in SCALE_CODES]

    def pace_rows(self):
        return [(label, self.pace_share(value)) for value, label in PACE_LABELS.items()]


def summaries(key, **filters):
    """Summaries of the responses matching `filters`, grouped by `key`.

    `key` is a Response field path such as "session", "session__module" or
    "session__group". Returns {key value: Summary}.
    """
    responses = Response.objects.filter(**filters)
    result = defaultdict(Summary)

    for row in responses.values(key).annotate(n=Count("id")):
        result[row[key]].responses = row["n"]

    answers = Answer.objects.filter(response__in=responses)
    answer_key = f"response__{key}"
    for row in (
        answers.filter(question__kind=Question.SCALE)
        .values(answer_key, "question__code")
        .annotate(avg=Avg("value"))
    ):
        result[row[answer_key]].averages[row["question__code"]] = row["avg"]
    for row in (
        answers.filter(question__kind=Question.PACE).values(answer_key, "value").annotate(n=Count("id"))
    ):
        result[row[answer_key]].pace[row["value"]] = row["n"]

    return dict(result)


def summary(**filters):
    """One Summary over all responses matching `filters`."""
    responses = Response.objects.filter(**filters)
    answers = Answer.objects.filter(response__in=responses)
    result = Summary(responses=responses.count())
    for row in answers.filter(question__kind=Question.SCALE).values("question__code").annotate(avg=Avg("value")):
        result.averages[row["question__code"]] = row["avg"]
    for row in answers.filter(question__kind=Question.PACE).values("value").annotate(n=Count("id")):
        result.pace[row["value"]] = row["n"]
    return result


@dataclass
class Alert:
    module: object
    messages: list


def module_alerts(group, now=None):
    """Alerts for modules of `group` whose last session's form has closed."""
    now = now or timezone.now()
    module_summaries = summaries("session__module", session__group=group)
    last_dates = dict(
        group.sessions.exclude(module=None).values_list("module").annotate(last=Max("date"))
    )
    alerts = []
    for module in group.program.modules.all():
        last_session = group.sessions.filter(module=module, date=last_dates.get(module.pk)).first()
        if last_session is None or last_session.closes_at() > now:
            continue
        module_summary = module_summaries.get(module.pk)
        if module_summary is None or not module_summary.visible:
            continue
        messages = []
        for label, value in module_summary.scale_rows():
            if value is not None and value < settings.PULSE_ALERT_MIN_AVERAGE:
                messages.append(f"{label}: vidurkis {value:.2f} (< {settings.PULSE_ALERT_MIN_AVERAGE})")
        for value, label in PACE_LABELS.items():
            share = module_summary.pace_share(value)
            if value != 2 and share >= settings.PULSE_ALERT_PACE_SHARE:
                messages.append(f"Tempas „{label.lower()}“: {share:.0%} atsakiusiųjų")
        if messages:
            alerts.append(Alert(module=module, messages=messages))
    return alerts
