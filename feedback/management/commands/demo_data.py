"""Fill a DEMO group with made-up responses so the dashboard can be tried out.

    uv run python manage.py demo_data            # create / refresh
    uv run python manage.py demo_data --remove   # delete the demo group and its responses
"""

import datetime
import random
import uuid

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from feedback.models import Answer, Group, Program, QuestionSet, Response

DEMO_NAME = "DEMO grupė (netikri duomenys)"
COMMENTS = [
    "Labai patiko praktinės užduotys, norėtųsi daugiau tokių.",
    "Teorijos dalis buvo per ilga, pritrūko laiko praktikai.",
    "Lektorius puikiai paaiškino, ačiū!",
    "Šiandien buvo sunku suspėti, gal galima įrašą?",
    "Norėčiau daugiau realių pavyzdžių iš darbo.",
    "Namų darbų užduotis nebuvo aiški.",
    "Viskas super 👍",
]


class Command(BaseCommand):
    help = "Create a demo group with random responses (for trying out the dashboard)."

    def add_arguments(self, parser):
        parser.add_argument("--remove", action="store_true", help="Delete the demo group.")

    @transaction.atomic
    def handle(self, *args, remove=False, **options):
        Response.objects.filter(session__group__name=DEMO_NAME).delete()
        Group.objects.filter(name=DEMO_NAME).delete()
        if remove:
            self.stdout.write(self.style.SUCCESS("Demo group removed."))
            return

        call_command("seed_ai_engineering", stdout=self.stdout)
        group = Group.objects.create(
            program=Program.objects.get(name="AI Engineering"),
            name=DEMO_NAME,
            start_date=datetime.date(2026, 8, 3),
        )
        group.generate_sessions()

        rng = random.Random(42)
        question_set = QuestionSet.active()
        questions = {q.code: q for q in question_set.questions.all()}
        today = timezone.localdate()
        count = 0
        for session in group.sessions.filter(date__lt=today).select_related("module"):
            hard_module = session.module and session.module.number == 1
            for _ in range(rng.randint(2, 13)):
                response = Response.objects.create(
                    session=session, question_set=question_set, respondent_hash=uuid.uuid4().hex
                )
                pace = rng.choices([1, 2, 3], weights=[1, 5, 4 if hard_module else 1])[0]
                values = {
                    "pace": pace,
                    "lecturer": rng.choices([3, 4, 5], weights=[1, 3, 6])[0],
                    "theory": rng.choices([2, 3, 4, 5], weights=[1, 2, 4, 3])[0],
                    "practice": rng.choices([1, 2, 3, 4, 5], weights=[2, 3, 3, 2, 1] if hard_module else [0, 1, 2, 4, 3])[0],
                }
                Answer.objects.bulk_create(
                    Answer(response=response, question=questions[code], value=value)
                    for code, value in values.items()
                )
                if rng.random() < 0.3:
                    Answer.objects.create(
                        response=response, question=questions["comment"], text=rng.choice(COMMENTS)
                    )
                count += 1
        self.stdout.write(self.style.SUCCESS(f"{DEMO_NAME}: {count} demo responses."))
