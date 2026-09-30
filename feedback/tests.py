import datetime

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from .models import Group, Program, QuestionSet, Response, Session


class SessionGenerationTests(TestCase):
    def setUp(self):
        call_command("seed_ai_engineering", stdout=open("/dev/null", "w"))
        self.program = Program.objects.get(name="AI Engineering")
        self.group = Group.objects.create(
            program=self.program,
            name="AI Engineering 2026-10",
            start_date=datetime.date(2026, 10, 19),
            weekdays="0,2,3",
        )

    def test_creates_65_sessions_on_mon_wed_thu(self):
        self.assertEqual(self.group.generate_sessions(), 65)
        sessions = self.group.sessions.all()
        self.assertEqual(sessions.count(), 65)
        self.assertEqual(sessions.first().date, datetime.date(2026, 10, 19))
        self.assertTrue(all(s.date.weekday() in (0, 2, 3) for s in sessions))
        self.assertEqual(self.group.end_date, sessions.last().date)

    def test_skips_lithuanian_public_holidays(self):
        self.group.generate_sessions()
        dates = set(self.group.sessions.values_list("date", flat=True))
        # Nov 2 (Mon, Vėlinės) and Dec 24 (Thu, Kūčios) are public holidays.
        self.assertNotIn(datetime.date(2026, 11, 2), dates)
        self.assertNotIn(datetime.date(2026, 12, 24), dates)

    def test_assigns_modules_by_session_number(self):
        self.group.generate_sessions()
        self.assertEqual(self.group.sessions.get(number=17).module.number, 1)
        self.assertEqual(self.group.sessions.get(number=18).module.number, 2)
        self.assertEqual(self.group.sessions.get(number=65).module.number, 7)

    def test_refuses_to_regenerate_after_responses(self):
        self.group.generate_sessions()
        Response.objects.create(
            session=self.group.sessions.first(),
            question_set=QuestionSet.active(),
            respondent_hash="x",
        )
        with self.assertRaises(ValidationError):
            self.group.generate_sessions()
        self.assertEqual(Session.objects.filter(group=self.group).count(), 65)


class QuestionSetTests(TestCase):
    def test_v1_is_active_with_five_questions(self):
        question_set = QuestionSet.active()
        self.assertEqual(question_set.version, 1)
        self.assertEqual(
            list(question_set.questions.values_list("code", flat=True)),
            ["pace", "lecturer", "theory", "practice", "comment"],
        )
