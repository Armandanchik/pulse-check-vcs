from django import template
from django.conf import settings

register = template.Library()


@register.filter
def score(value):
    """1–5 average as '4.25', or an en dash when there is nothing to show."""
    return "–" if value is None else f"{value:.2f}"


@register.filter
def score_class(value):
    if value is None:
        return "empty"
    if value < settings.PULSE_ALERT_MIN_AVERAGE:
        return "bad"
    if value < 4:
        return "ok"
    return "good"


@register.filter
def percent(share):
    return f"{share:.0%}"
