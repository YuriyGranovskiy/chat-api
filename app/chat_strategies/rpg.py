from __future__ import annotations

from app.models import Chat
from app.scene_sync import sync_location_from_meta, sync_personas_from_meta

_RPG_RULES = (
    "1. Respond with TWO SHORT paragraphs ONLY.\n"
    "2. Each paragraph must be exactly 2-3 sentences long.\n"
    "3. Be extremely concise. Avoid purple prose and long metaphors.\n"
    "4. Format actions in asterisks and speech in quotes.\n"
    "5. After the second paragraph output scene VALID JSON strictly with keys: "
    "\"location\" (string), \"persons\" (names present in the scene), "
    "\"location_description\" (short location description, only interior, no descriotion of the persons), "
    "\"person_descriptions\" (object with short descriptions of a person by name, briefly describe the character and a backstory, fill only for new persons), "
    "\"clothing\" and \"ammunition\" (objects mapping each name in persons to a short string). "
    "Use empty string or omit a name if unknown; use empty objects {} if no weapons apply. "
    "Example: {\"location\": \"...\", \"location_description\": \"...\", \"persons\": [\"A\"], "
    "\"person_descriptions\": {\"A\": \"...\"}, \"clothing\": {\"A\": \"...\"}, \"ammunition\": {\"A\": \"...\"}}.\n"
    "Fill location_description only if the location is new.  Don't add transit locations like \"doorway\".\n"
    "6. When the user speaks to a specific personas, respond as them.\n"
    "7. Prefix persona's speech with their name, e.g., AKIRA: \"...\"\n\n"
)


class RpgStrategy:
    id = "rpg"

    def build_system_prompt(self, chat: Chat) -> str:
        personas_block = (
            "\n".join(
                f"{persona.name}: {persona.description or 'No description'}"
                for persona in chat.personas
            )
            or "No personas in this chat."
        )
        locations_block = (
            "\n".join(
                f"{location.name}: {location.description or 'No description'}"
                for location in chat.available_locations
            )
            or "No locations in this chat."
        )
        scenario = chat.scenario or "In a quiet room."

        return (
            "### RPG ENGINE MODE\n"
            "You are the Game Master and the narrator. "
            "You control the environment and all NPCs.\n\n"
            f"### CURRENT SCENARIO:\n{scenario}\n\n"
            f"### CHAT PERSONAS (name: description):\n{personas_block}\n\n"
            f"### CHAT LOCATIONS (name: description):\n{locations_block}\n\n"
            f"### MANDATORY RESPONSE FORMATTING RULES:\n{_RPG_RULES}"
        )

    def refine_assistant_output(
        self, chat: Chat, display_text: str, meta: str | None
    ) -> tuple[str, str | None]:
        meta = sync_location_from_meta(chat, meta)
        meta = sync_personas_from_meta(chat, meta)
        return display_text, meta
