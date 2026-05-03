from __future__ import annotations

from typing import Protocol

from app.chat_strategies.language_teacher import LanguageTeacherStrategy
from app.chat_strategies.rpg import RpgStrategy
from app.models import Chat

_rpg = RpgStrategy()
_language_teacher = LanguageTeacherStrategy()

_BY_ID: dict[str, ChatStrategy] = {
    _rpg.id: _rpg,
    _language_teacher.id: _language_teacher,
}

KNOWN_STRATEGY_IDS: frozenset[str] = frozenset(_BY_ID.keys())

# Short labels for API clients (list/detail); unknown ids fall back to the id string.
STRATEGY_DISPLAY_NAMES: dict[str, str] = {
    _rpg.id: "RPG / Game Master",
    _language_teacher.id: "Language tutor",
}


def strategy_display_name(strategy_id: str) -> str:
    key = (strategy_id or "").strip() or "rpg"
    if key in STRATEGY_DISPLAY_NAMES:
        return STRATEGY_DISPLAY_NAMES[key]
    return key.replace("_", " ").title()


class ChatStrategy(Protocol):
    id: str

    def build_system_prompt(self, chat: Chat) -> str: ...

    def refine_assistant_output(
        self, chat: Chat, display_text: str, meta: str | None
    ) -> tuple[str, str | None]: ...


def validate_strategy_id_for_create(strategy_id: str) -> str:
    normalized = (strategy_id or "rpg").strip() or "rpg"
    if normalized not in KNOWN_STRATEGY_IDS:
        raise ValueError(f"Unknown strategy_id: {strategy_id!r}")
    return normalized


def get_strategy(strategy_id: str | None) -> ChatStrategy:
    key = (strategy_id or "").strip() or "rpg"
    return _BY_ID.get(key, _rpg)
