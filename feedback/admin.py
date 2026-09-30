from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import Count

from .models import (
    WEEKDAY_NAMES,
    Answer,
    Group,
    Module,
    Program,
    Question,
    QuestionSet,
    Response,
    Session,
)

admin.site.site_header = "Pulse Check VCS"
admin.site.site_title = "Pulse Check VCS"


class ModuleInline(admin.TabularInline):
    model = Module
    extra = 0


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ["name", "session_count"]
    inlines = [ModuleInline]


class SessionInline(admin.TabularInline):
    model = Session
    extra = 0
    fields = ["number", "date", "module", "topic"]
    readonly_fields = ["number"]
    show_change_link = True


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ["name", "program", "start_date", "end_date", "schedule", "session_total"]
    list_filter = ["program"]
    readonly_fields = ["end_date", "link_token"]
    inlines = [SessionInline]
    actions = ["generate_sessions"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(session_total=Count("sessions"))

    @admin.display(description="tvarkaraštis")
    def schedule(self, group):
        days = ", ".join(WEEKDAY_NAMES[d] for d in group.weekday_list())
        return f"{days} {group.lesson_start:%H:%M}–{group.lesson_end:%H:%M}"

    @admin.display(description="sesijos", ordering="session_total")
    def session_total(self, group):
        return group.session_total

    @admin.action(description="Sugeneruoti sesijas pagal tvarkaraštį")
    def generate_sessions(self, request, queryset):
        for group in queryset:
            try:
                count = group.generate_sessions()
            except ValidationError as error:
                self.message_user(request, f"{group}: {error.message}", messages.ERROR)
            else:
                self.message_user(
                    request, f"{group}: sukurta {count} sesijų, pabaiga {group.end_date}."
                )


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ["__str__", "module", "topic", "response_total"]
    list_filter = ["group", "module"]
    date_hierarchy = "date"

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(response_total=Count("responses"))

    @admin.display(description="atsakymai", ordering="response_total")
    def response_total(self, session):
        return session.response_total


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0


@admin.register(QuestionSet)
class QuestionSetAdmin(admin.ModelAdmin):
    list_display = ["__str__", "created_at"]
    inlines = [QuestionInline]


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    can_delete = False
    readonly_fields = ["question", "value", "text"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    """Read-only: responses come only from students."""

    list_display = ["session", "created_at"]
    list_filter = ["session__group", "session__module"]
    readonly_fields = ["session", "question_set", "created_at"]
    exclude = ["respondent_hash"]
    inlines = [AnswerInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
