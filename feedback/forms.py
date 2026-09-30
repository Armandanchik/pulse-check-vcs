from django import forms

from .models import Answer, Question

SCALE_CHOICES = [(n, str(n)) for n in range(1, 6)]


class FeedbackForm(forms.Form):
    """Built from a QuestionSet: one field per question, named after its code."""

    def __init__(self, question_set, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.questions = list(question_set.questions.all())
        for question in self.questions:
            self.fields[question.code] = self._field_for(question)

    @staticmethod
    def _field_for(question):
        if question.kind == Question.TEXT:
            return forms.CharField(
                label=question.text,
                required=question.required,
                max_length=2000,
                widget=forms.Textarea(attrs={"rows": 4}),
                help_text="Neįrašykite savo vardo ar kitų asmens duomenų – atsakymai anonimiški.",
            )
        choices = Question.PACE_CHOICES if question.kind == Question.PACE else SCALE_CHOICES
        return forms.TypedChoiceField(
            label=question.text,
            required=question.required,
            choices=choices,
            coerce=int,
            widget=forms.RadioSelect,
            error_messages={"required": "Pasirinkite atsakymą."},
        )

    def answers_for(self, response):
        """Unsaved Answer objects for a saved Response."""
        answers = []
        for question in self.questions:
            value = self.cleaned_data.get(question.code)
            if value in (None, ""):
                continue
            if question.kind == Question.TEXT:
                answers.append(Answer(response=response, question=question, text=value.strip()))
            else:
                answers.append(Answer(response=response, question=question, value=value))
        return answers
