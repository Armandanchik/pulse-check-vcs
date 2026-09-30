import hashlib
import hmac
import uuid

from django.conf import settings
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render

from .forms import FeedbackForm
from .models import Group, QuestionSet, Response

DEVICE_COOKIE = "pulse_device"
DEVICE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365 * 2


def respondent_hash(device_id, session):
    """Same device + same session -> same hash. Different sessions can't be linked."""
    message = f"{device_id}:{session.pk}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def feedback_form(request, token):
    group = get_object_or_404(Group.objects.select_related("program"), link_token=token)
    session = group.current_session()
    if session is None:
        return render(
            request, "feedback/closed.html", {"group": group, "next_session": group.next_session()}
        )

    device_id = request.COOKIES.get(DEVICE_COOKIE) or uuid.uuid4().hex
    answered_hash = respondent_hash(device_id, session)
    already_answered = Response.objects.filter(
        session=session, respondent_hash=answered_hash
    ).exists()

    if already_answered:
        response = render(request, "feedback/thanks.html", {"group": group, "session": session})
    else:
        question_set = QuestionSet.active()
        form = FeedbackForm(question_set, request.POST or None)
        if request.method == "POST" and form.is_valid():
            try:
                with transaction.atomic():
                    saved = Response.objects.create(
                        session=session,
                        question_set=question_set,
                        respondent_hash=answered_hash,
                    )
                    saved.answers.bulk_create(form.answers_for(saved))
            except IntegrityError:
                pass  # double click / second tab: the first submission already counted
            response = redirect("feedback:form", token=token)
        else:
            response = render(
                request,
                "feedback/form.html",
                {"group": group, "session": session, "form": form},
            )

    response.set_cookie(
        DEVICE_COOKIE,
        device_id,
        max_age=DEVICE_COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=not settings.DEBUG,
    )
    return response
