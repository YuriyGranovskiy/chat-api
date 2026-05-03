from __future__ import annotations

from app.models import Chat


class LanguageTeacherStrategy:
    id = "language_teacher"

    def build_system_prompt(self, chat: Chat) -> str:
        personas_block = (
            "\n".join(
                f"{persona.name}: {persona.description or 'No description'}"
                for persona in chat.personas
            )
            or "No named tutor persona; you are a single helpful teacher."
        )
        goals = chat.scenario or (
            "Help the user practice a foreign language. "
            "Infer or ask their target language and level from the conversation."
        )

        return (
            "### LANGUAGE TUTOR MODE\n"
            "You are a patient language teacher and conversation partner.\n"
            "- Gently correct mistakes; explain briefly in the user's preferred explanation language when needed.\n"
            "- Encourage short exchanges at the learner's level; gradually increase difficulty.\n"
            "- Do not narrate a fictional RPG scene or output game-style scene JSON.\n"
            "- Respond in plain prose (no trailing JSON block).\n\n"
            f"### LEARNING CONTEXT / GOALS:\n{goals}\n\n"
            f"### REFERENCE PERSONAS (optional cast for role-play drills):\n{personas_block}\n"
        )

    def refine_assistant_output(
        self, chat: Chat, display_text: str, meta: str | None
    ) -> tuple[str, str | None]:
        del chat
        return display_text, None
