import datetime
import io
import uuid
from unittest import mock

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from . import stats
from .models import Answer, Group, Program, QuestionSet, Response, Session
from .views import respondent_hash


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


def make_group(start=datetime.date(2026, 10, 19)):
    call_command("seed_ai_engineering", stdout=open("/dev/null", "w"))
    group = Group.objects.create(
        program=Program.objects.get(name="AI Engineering"), name="Test", start_date=start
    )
    group.generate_sessions()
    return group


def at(date, hour, minute=0):
    return timezone.make_aware(datetime.datetime.combine(date, datetime.time(hour, minute)))


def add_response(session, pace=2, lecturer=5, theory=4, practice=3, comment="", device=None):
    question_set = QuestionSet.active()
    questions = {q.code: q for q in question_set.questions.all()}
    response = Response.objects.create(
        session=session,
        question_set=question_set,
        respondent_hash=device or uuid.uuid4().hex,
    )
    for code, value in [("pace", pace), ("lecturer", lecturer), ("theory", theory), ("practice", practice)]:
        Answer.objects.create(response=response, question=questions[code], value=value)
    if comment:
        Answer.objects.create(response=response, question=questions["comment"], text=comment)
    return response


VALID_POST = {"pace": "2", "lecturer": "5", "theory": "4", "practice": "4", "comment": "Puiku"}


class CurrentSessionTests(TestCase):
    def setUp(self):
        self.group = make_group()
        self.first = self.group.sessions.get(number=1)  # Mon 2026-10-19

    def test_closed_before_first_lesson(self):
        self.assertIsNone(self.group.current_session(at(self.first.date, 17, 59)))
        self.assertEqual(self.group.next_session(at(self.first.date, 17, 59)), self.first)

    def test_open_during_and_48h_after_lesson(self):
        self.assertEqual(self.group.current_session(at(self.first.date, 18)), self.first)
        tuesday = self.first.date + datetime.timedelta(days=1)
        self.assertEqual(self.group.current_session(at(tuesday, 23)), self.first)

    def test_next_lesson_takes_over_when_it_starts(self):
        wednesday = self.group.sessions.get(number=2)
        self.assertEqual(self.group.current_session(at(wednesday.date, 18, 30)), wednesday)


class StudentFormTests(TestCase):
    def setUp(self):
        self.group = make_group()
        self.session = self.group.sessions.get(number=1)
        self.url = reverse("feedback:form", args=[self.group.link_token])
        self.now = at(self.session.date, 21)

    def get(self, **kwargs):
        with mock.patch("django.utils.timezone.now", return_value=self.now):
            return self.client.get(self.url, **kwargs)

    def post(self, data):
        with mock.patch("django.utils.timezone.now", return_value=self.now):
            return self.client.post(self.url, data)

    def test_unknown_link_is_404(self):
        self.assertEqual(self.client.get("/g/nope/").status_code, 404)

    def test_closed_page_outside_window(self):
        self.now = at(self.session.date, 12)
        self.assertContains(self.get(), "forma uždaryta")

    def test_shows_form_in_lithuanian(self):
        response = self.get()
        self.assertContains(response, "Kaip vertinate paskaitos tempą?")
        self.assertContains(response, "Per greitas")

    def test_submit_saves_answers_then_thanks(self):
        response = self.post(VALID_POST)
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        saved = Response.objects.get()
        self.assertEqual(saved.session, self.session)
        self.assertEqual(
            {a.question.code: a.value or a.text for a in saved.answers.all()},
            {"pace": 2, "lecturer": 5, "theory": 4, "practice": 4, "comment": "Puiku"},
        )
        self.assertContains(self.get(), "Ačiū už atsiliepimą")

    def test_same_device_cannot_answer_twice(self):
        self.post(VALID_POST)
        self.post(VALID_POST)
        self.assertEqual(Response.objects.count(), 1)

    def test_another_device_can_answer(self):
        self.post(VALID_POST)
        self.client.cookies.clear()
        self.post(VALID_POST)
        self.assertEqual(Response.objects.count(), 2)

    def test_missing_required_answer_shows_error(self):
        response = self.post({**VALID_POST, "lecturer": ""})
        self.assertContains(response, "Pasirinkite atsakymą.")
        self.assertEqual(Response.objects.count(), 0)

    def test_comment_is_optional(self):
        self.post({**VALID_POST, "comment": ""})
        self.assertEqual(Response.objects.get().answers.count(), 4)

    def test_device_hash_differs_between_sessions(self):
        self.assertNotEqual(
            respondent_hash("device", self.session),
            respondent_hash("device", self.group.sessions.get(number=2)),
        )


class StatsTests(TestCase):
    def setUp(self):
        self.group = make_group(start=datetime.date(2026, 8, 3))
        self.session = self.group.sessions.get(number=1)

    def test_summary_hidden_below_three_responses(self):
        add_response(self.session)
        add_response(self.session)
        summary = stats.summaries("session", session__group=self.group)[self.session.pk]
        self.assertFalse(summary.visible)
        add_response(self.session)
        summary = stats.summaries("session", session__group=self.group)[self.session.pk]
        self.assertTrue(summary.visible)
        self.assertEqual(summary.average("lecturer"), 5)

    def test_pace_shares(self):
        for pace in (1, 3, 3, 2):
            add_response(self.session, pace=pace)
        summary = stats.summary(session=self.session)
        self.assertEqual(summary.pace_share(3), 0.5)

    def test_alert_for_finished_module_with_low_scores(self):
        module_1 = self.group.sessions.filter(module__number=1)
        for session in module_1[:3]:
            add_response(session, theory=2, pace=3)
        alerts = stats.module_alerts(self.group, now=at(datetime.date(2027, 1, 1), 12))
        self.assertEqual([a.module.number for a in alerts], [1])
        text = " ".join(alerts[0].messages)
        self.assertIn("Teorija", text)
        self.assertIn("per greitas", text)

    def test_no_alert_while_module_still_running(self):
        for session in self.group.sessions.filter(module__number=1)[:3]:
            add_response(session, theory=1)
        self.assertEqual(stats.module_alerts(self.group, now=at(self.session.date, 22)), [])


class DashboardTests(TestCase):
    def setUp(self):
        self.group = make_group(start=datetime.date(2026, 8, 3))
        self.session = self.group.sessions.get(number=1)
        for n in range(3):
            add_response(self.session, comment=f"komentaras {n}")
        self.admin = User.objects.create_superuser("boss", "boss@example.com", "x")

    def test_requires_staff_login(self):
        for url in [
            reverse("feedback:dashboard"),
            reverse("feedback:group", args=[self.group.pk]),
            reverse("feedback:export", args=["csv"]),
        ]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertIn("/admin/login/", response["Location"])

    def test_pages_render_for_admin(self):
        self.client.force_login(self.admin)
        for url in [
            reverse("feedback:dashboard"),
            reverse("feedback:group", args=[self.group.pk]),
            reverse("feedback:session", args=[self.session.pk]),
            reverse("feedback:program", args=[self.group.program_id]),
            reverse("admin:feedback_group_change", args=[self.group.pk]),
        ]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_group_page_shows_comments_of_visible_sessions(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("feedback:group", args=[self.group.pk]))
        self.assertContains(response, "komentaras 2")

    def test_comments_hidden_below_threshold(self):
        other = self.group.sessions.get(number=2)
        add_response(other, comment="slaptas")
        self.client.force_login(self.admin)
        response = self.client.get(reverse("feedback:session", args=[other.pk]))
        self.assertNotContains(response, "slaptas")

    def test_csv_export(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("feedback:export", args=["csv"]) + f"?group={self.group.pk}")
        lines = response.content.decode("utf-8-sig").strip().splitlines()
        self.assertEqual(len(lines), 4)
        self.assertIn("Tinkamas", lines[1])

    def test_xlsx_export(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("feedback:export", args=["xlsx"]))
        sheet = load_workbook(io.BytesIO(response.content)).active
        self.assertEqual(sheet.max_row, 4)
        self.assertEqual(sheet["A2"].value, "AI Engineering")
