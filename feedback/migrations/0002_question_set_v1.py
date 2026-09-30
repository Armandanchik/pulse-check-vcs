from django.db import migrations

QUESTIONS = [
    ("pace", "pace", "Kaip vertinate paskaitos tempą?", True),
    ("lecturer", "scale", "Kaip vertinate lektoriaus darbą?", True),
    ("theory", "scale", "Ar teorija buvo aiški?", True),
    ("practice", "scale", "Ar praktinės užduotys buvo naudingos ir suprantamos?", True),
    ("comment", "text", "Papildomi komentarai", False),
]


def create_v1(apps, schema_editor):
    QuestionSet = apps.get_model("feedback", "QuestionSet")
    Question = apps.get_model("feedback", "Question")
    question_set = QuestionSet.objects.create(version=1, is_active=True)
    for order, (code, kind, text, required) in enumerate(QUESTIONS, start=1):
        Question.objects.create(
            question_set=question_set,
            order=order,
            code=code,
            kind=kind,
            text=text,
            required=required,
        )


def delete_v1(apps, schema_editor):
    apps.get_model("feedback", "QuestionSet").objects.filter(version=1).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("feedback", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_v1, delete_v1),
    ]
