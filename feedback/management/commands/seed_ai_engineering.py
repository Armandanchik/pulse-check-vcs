from django.core.management.base import BaseCommand

from feedback.models import Module, Program

MODULES = [
    (1, "Python pagrindai ir kodo kokybė", 1, 17),
    (2, "Duomenys, duomenų bazės ir API", 18, 29),
    (3, "LLM, prompt inžinerija, įrankių kvietimas, MCP", 30, 37),
    (4, "LangChain, vektorinė paieška ir RAG", 38, 45),
    (5, "AI agentai su LangGraph", 46, 53),
    (6, "Vertinimas, apsaugos ir stebėsena", 54, 57),
    (7, "Produkcinis diegimas ir baigiamasis projektas", 58, 65),
]


class Command(BaseCommand):
    help = "Create or update the AI Engineering program and its 7 modules."

    def handle(self, *args, **options):
        program, _ = Program.objects.update_or_create(
            name="AI Engineering", defaults={"session_count": 65}
        )
        for number, title, first, last in MODULES:
            Module.objects.update_or_create(
                program=program,
                number=number,
                defaults={"title": title, "first_session": first, "last_session": last},
            )
        self.stdout.write(self.style.SUCCESS(f"{program}: {len(MODULES)} modules ready."))
