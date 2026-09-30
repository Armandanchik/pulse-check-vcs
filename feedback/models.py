import datetime
import secrets

import holidays
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone


class Program(models.Model):
    """A course template, e.g. "AI Engineering". Every group of the course reuses it."""

    name = models.CharField("pavadinimas", max_length=200, unique=True)
    session_count = models.PositiveIntegerField("sesijų skaičius", default=65)

    class Meta:
        verbose_name = "programa"
        verbose_name_plural = "programos"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def module_for(self, session_number):
        return self.modules.filter(
            first_session__lte=session_number, last_session__gte=session_number
        ).first()


class Module(models.Model):
    program = models.ForeignKey(
        Program, on_delete=models.CASCADE, related_name="modules", verbose_name="programa"
    )
    number = models.PositiveIntegerField("nr.")
    title = models.CharField("tema", max_length=200)
    first_session = models.PositiveIntegerField("pirma sesija")
    last_session = models.PositiveIntegerField("paskutinė sesija")

    class Meta:
        verbose_name = "modulis"
        verbose_name_plural = "moduliai"
        ordering = ["program", "number"]
        constraints = [
            models.UniqueConstraint(fields=["program", "number"], name="unique_module_number"),
        ]

    def __str__(self):
        return f"{self.number}. {self.title}"

    def clean(self):
        if self.first_session and self.last_session and self.first_session > self.last_session:
            raise ValidationError("Pirma sesija negali būti po paskutinės.")


def new_link_token():
    return secrets.token_urlsafe(8)


# Monday=0 ... Sunday=6, matching datetime.date.weekday()
WEEKDAY_NAMES = ["Pr", "An", "Tr", "Kt", "Pn", "Št", "Sk"]


class Group(models.Model):
    """One run of a program, e.g. "AI Engineering 2026-10". One group = one course."""

    program = models.ForeignKey(
        Program, on_delete=models.PROTECT, related_name="groups", verbose_name="programa"
    )
    name = models.CharField("pavadinimas", max_length=200, unique=True)
    start_date = models.DateField("pradžios data")
    end_date = models.DateField("pabaigos data", null=True, blank=True, editable=False)
    weekdays = models.CharField(
        "savaitės dienos",
        max_length=20,
        default="0,2,3",
        help_text="Dienų numeriai per kablelį: 0=Pr, 1=An, 2=Tr, 3=Kt, 4=Pn, 5=Št, 6=Sk.",
    )
    lesson_start = models.TimeField("paskaitos pradžia", default=datetime.time(18, 0))
    lesson_end = models.TimeField("paskaitos pabaiga", default=datetime.time(21, 30))
    skip_public_holidays = models.BooleanField("praleisti valstybines šventes", default=True)
    response_window_hours = models.PositiveIntegerField(
        "atsakymų langas (val.)",
        default=48,
        help_text="Kiek valandų po paskaitos pabaigos forma lieka atvira.",
    )
    link_token = models.CharField(max_length=32, unique=True, default=new_link_token, editable=False)

    class Meta:
        verbose_name = "grupė"
        verbose_name_plural = "grupės"
        ordering = ["-start_date"]

    def __str__(self):
        return self.name

    def weekday_list(self):
        return sorted({int(d) for d in self.weekdays.split(",") if d.strip()})

    def clean(self):
        try:
            days = self.weekday_list()
        except ValueError:
            raise ValidationError({"weekdays": "Naudokite skaičius 0–6, atskirtus kableliais."})
        if not days or any(d > 6 for d in days):
            raise ValidationError({"weekdays": "Naudokite skaičius 0–6, atskirtus kableliais."})

    def lesson_dates(self):
        """Dates of all sessions, starting at start_date on the chosen weekdays."""
        days = self.weekday_list()
        skip = holidays.country_holidays("LT") if self.skip_public_holidays else {}
        dates = []
        day = self.start_date
        while len(dates) < self.program.session_count:
            if day.weekday() in days and day not in skip:
                dates.append(day)
            day += datetime.timedelta(days=1)
        return dates

    @transaction.atomic
    def generate_sessions(self):
        """Create the group's sessions. Refuses if any session already has responses."""
        if Response.objects.filter(session__group=self).exists():
            raise ValidationError("Grupė jau turi atsakymų, sesijų perkurti negalima.")
        self.sessions.all().delete()
        dates = self.lesson_dates()
        Session.objects.bulk_create(
            Session(
                group=self,
                number=number,
                date=date,
                module=self.program.module_for(number),
            )
            for number, date in enumerate(dates, start=1)
        )
        self.end_date = dates[-1]
        self.save(update_fields=["end_date"])
        return len(dates)

    def student_url(self):
        return f"{settings.PUBLIC_BASE_URL}{reverse('feedback:form', args=[self.link_token])}"

    def current_session(self, now=None):
        """The latest session whose form is open right now, or None."""
        now = now or timezone.now()
        today = timezone.localdate(now)
        earliest = today - datetime.timedelta(days=self.response_window_hours // 24 + 1)
        candidates = self.sessions.filter(date__range=(earliest, today)).order_by("-date")
        for session in candidates:
            if session.opens_at() <= now <= session.closes_at():
                return session
        return None

    def next_session(self, now=None):
        now = now or timezone.now()
        for session in self.sessions.filter(date__gte=timezone.localdate(now)).order_by("date"):
            if session.opens_at() > now:
                return session
        return None


class Session(models.Model):
    """One lesson of a group."""

    group = models.ForeignKey(
        Group, on_delete=models.CASCADE, related_name="sessions", verbose_name="grupė"
    )
    number = models.PositiveIntegerField("nr.")
    date = models.DateField("data")
    module = models.ForeignKey(
        Module,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions",
        verbose_name="modulis",
    )
    topic = models.CharField("tema", max_length=200, blank=True)

    class Meta:
        verbose_name = "sesija"
        verbose_name_plural = "sesijos"
        ordering = ["group", "number"]
        constraints = [
            models.UniqueConstraint(fields=["group", "number"], name="unique_session_number"),
        ]

    def __str__(self):
        return f"{self.group} · S{self.number} ({self.date})"

    def opens_at(self):
        return timezone.make_aware(datetime.datetime.combine(self.date, self.group.lesson_start))

    def closes_at(self):
        lesson_end = timezone.make_aware(datetime.datetime.combine(self.date, self.group.lesson_end))
        return lesson_end + datetime.timedelta(hours=self.group.response_window_hours)


class QuestionSet(models.Model):
    """A versioned list of questions. Responses point at the exact version they answered."""

    version = models.PositiveIntegerField("versija", unique=True)
    is_active = models.BooleanField("aktyvi", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "klausimynas"
        verbose_name_plural = "klausimynai"
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"],
                condition=models.Q(is_active=True),
                name="one_active_question_set",
            ),
        ]

    def __str__(self):
        return f"v{self.version}" + (" (aktyvi)" if self.is_active else "")

    @classmethod
    def active(cls):
        return cls.objects.get(is_active=True)


class Question(models.Model):
    PACE = "pace"
    SCALE = "scale"
    TEXT = "text"
    KIND_CHOICES = [
        (PACE, "Tempas (per lėtas / tinkamas / per greitas)"),
        (SCALE, "Skalė 1–5"),
        (TEXT, "Laisvas tekstas"),
    ]
    PACE_CHOICES = [(1, "Per lėtas"), (2, "Tinkamas"), (3, "Per greitas")]

    question_set = models.ForeignKey(QuestionSet, on_delete=models.CASCADE, related_name="questions")
    order = models.PositiveIntegerField("eilė")
    code = models.SlugField(
        "kodas", help_text="Stabilus kodas palyginimui tarp versijų, pvz. „lecturer“."
    )
    text = models.CharField("klausimas", max_length=300)
    kind = models.CharField("tipas", max_length=10, choices=KIND_CHOICES)
    required = models.BooleanField("privalomas", default=True)

    class Meta:
        verbose_name = "klausimas"
        verbose_name_plural = "klausimai"
        ordering = ["question_set", "order"]
        constraints = [
            models.UniqueConstraint(fields=["question_set", "code"], name="unique_question_code"),
        ]

    def __str__(self):
        return self.text


class Response(models.Model):
    """One anonymous student's feedback on one session.

    respondent_hash is derived from a random browser ID *and* the session, so it
    blocks double answers but cannot link one student's answers across sessions.
    """

    session = models.ForeignKey(
        Session, on_delete=models.PROTECT, related_name="responses", verbose_name="sesija"
    )
    question_set = models.ForeignKey(
        QuestionSet, on_delete=models.PROTECT, related_name="responses", verbose_name="klausimynas"
    )
    respondent_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField("pateikta", auto_now_add=True)

    class Meta:
        verbose_name = "atsakymas"
        verbose_name_plural = "atsakymai"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "respondent_hash"], name="one_response_per_device"
            ),
        ]

    def __str__(self):
        return f"{self.session} · {self.created_at:%Y-%m-%d %H:%M}"


class Answer(models.Model):
    response = models.ForeignKey(Response, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(
        Question, on_delete=models.PROTECT, related_name="answers", verbose_name="klausimas"
    )
    value = models.PositiveSmallIntegerField("reikšmė", null=True, blank=True)
    text = models.TextField("tekstas", blank=True)

    class Meta:
        verbose_name = "atsakymas į klausimą"
        verbose_name_plural = "atsakymai į klausimus"
        constraints = [
            models.UniqueConstraint(fields=["response", "question"], name="one_answer_per_question"),
        ]
