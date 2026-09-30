"""CSV / Excel export: one row per response, one column per question code."""

import csv
import io

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from .models import Question, Response

QUESTION_COLUMNS = [
    ("pace", "Tempas"),
    ("lecturer", "Lektorius (1–5)"),
    ("theory", "Teorija (1–5)"),
    ("practice", "Praktika (1–5)"),
    ("comment", "Komentaras"),
]
HEADER = [
    "Programa",
    "Grupė",
    "Modulis",
    "Sesija",
    "Data",
    "Klausimyno versija",
    *[label for _, label in QUESTION_COLUMNS],
    "Pateikta",
]
PACE_LABELS = dict(Question.PACE_CHOICES)


def export_rows(**filters):
    responses = (
        Response.objects.filter(**filters)
        .select_related("session__group__program", "session__module", "question_set")
        .prefetch_related("answers__question")
        .order_by("session__group__name", "session__number", "created_at")
    )
    for response in responses:
        session = response.session
        by_code = {}
        for answer in response.answers.all():
            question = answer.question
            if question.kind == Question.TEXT:
                by_code[question.code] = answer.text
            elif question.kind == Question.PACE:
                by_code[question.code] = PACE_LABELS.get(answer.value, answer.value)
            else:
                by_code[question.code] = answer.value
        yield [
            session.group.program.name,
            session.group.name,
            str(session.module) if session.module else "",
            session.number,
            session.date,
            response.question_set.version,
            *[by_code.get(code, "") for code, _ in QUESTION_COLUMNS],
            timezone.localtime(response.created_at).replace(tzinfo=None),
        ]


def to_csv(rows):
    buffer = io.StringIO()
    buffer.write("﻿")  # BOM so Excel opens Lithuanian letters correctly
    writer = csv.writer(buffer)
    writer.writerow(HEADER)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def to_xlsx(rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Atsakymai"
    sheet.append(HEADER)
    for row in rows:
        sheet.append(row)
    sheet.freeze_panes = "A2"
    for index, width in enumerate([18, 24, 36, 8, 12, 10, 14, 10, 10, 10, 60, 18], start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    for cell in sheet["E"][1:]:
        cell.number_format = "yyyy-mm-dd"
    for cell in sheet["L"][1:]:
        cell.number_format = "yyyy-mm-dd hh:mm"
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
