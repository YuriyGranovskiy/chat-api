"""RPG scene JSON: sync Location/Persona rows from assistant_meta."""

from __future__ import annotations

import json
import re

from app.models import Chat, Location, Persona, db


def normalize_location_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip()


def normalize_person_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip()


def find_location_by_normalized_name(normalized_name: str) -> Location | None:
    target = normalized_name.casefold()
    for location in Location.query.all():
        if normalize_location_name(location.name).casefold() == target:
            return location
    return None


def find_persona_by_normalized_name(normalized_name: str) -> Persona | None:
    target = normalized_name.casefold()
    for persona in Persona.query.all():
        if normalize_person_name(persona.name).casefold() == target:
            return persona
    return None


def sync_location_from_meta(chat: Chat, meta: str | None) -> str | None:
    if not meta:
        return meta

    parsed_meta = json.loads(meta)
    raw_location = parsed_meta.get("location")
    if not isinstance(raw_location, str):
        parsed_meta.pop("new_location", None)
        return json.dumps(parsed_meta, ensure_ascii=False, sort_keys=True)

    normalized_location_name = normalize_location_name(raw_location)
    if not normalized_location_name:
        parsed_meta.pop("new_location", None)
        return json.dumps(parsed_meta, ensure_ascii=False, sort_keys=True)

    parsed_meta["location"] = normalized_location_name

    location_description = parsed_meta.get("location_description")
    location_description_text = (
        location_description.strip()
        if isinstance(location_description, str) and location_description.strip()
        else None
    )
    if location_description_text:
        parsed_meta["location_description"] = location_description_text

    location = find_location_by_normalized_name(normalized_location_name)
    location_is_new = False
    if location is None:
        location = Location(
            name=normalized_location_name,
            description=location_description_text,
        )
        db.session.add(location)
        location_is_new = True
    elif location_description_text and not location.description:
        location.description = location_description_text

    if location not in chat.available_locations:
        chat.available_locations.append(location)

    if location_is_new:
        parsed_meta["new_location"] = {
            "name": location.name,
            "description": location.description or "",
        }
    else:
        parsed_meta.pop("new_location", None)

    return json.dumps(parsed_meta, ensure_ascii=False, sort_keys=True)


def sync_personas_from_meta(chat: Chat, meta: str | None) -> str | None:
    if not meta:
        return meta

    parsed_meta = json.loads(meta)
    raw_persons = parsed_meta.get("persons")
    if not isinstance(raw_persons, list):
        parsed_meta.pop("new_persons", None)
        return json.dumps(parsed_meta, ensure_ascii=False, sort_keys=True)

    raw_descriptions = parsed_meta.get("person_descriptions")
    description_by_name: dict[str, str] = {}
    if isinstance(raw_descriptions, dict):
        for raw_name, raw_description in raw_descriptions.items():
            if not isinstance(raw_name, str) or not isinstance(raw_description, str):
                continue
            normalized_name = normalize_person_name(raw_name)
            normalized_description = raw_description.strip()
            if normalized_name and normalized_description:
                description_by_name[normalized_name.casefold()] = normalized_description

    normalized_persons: list[str] = []
    normalized_person_keys: set[str] = set()
    new_persons: list[dict[str, str]] = []
    normalized_descriptions: dict[str, str] = {}
    for raw_person in raw_persons:
        if not isinstance(raw_person, str):
            continue
        normalized_person_name = normalize_person_name(raw_person)
        if not normalized_person_name:
            continue
        person_key = normalized_person_name.casefold()
        if person_key in normalized_person_keys:
            continue
        normalized_person_keys.add(person_key)
        normalized_persons.append(normalized_person_name)

        person_description = description_by_name.get(person_key)
        if person_description:
            normalized_descriptions[normalized_person_name] = person_description

        persona = find_persona_by_normalized_name(normalized_person_name)
        persona_is_new = False
        if persona is None:
            persona = Persona(name=normalized_person_name, description=person_description)
            db.session.add(persona)
            persona_is_new = True
        elif person_description and not persona.description:
            persona.description = person_description

        if persona not in chat.personas:
            chat.personas.append(persona)

        if persona_is_new:
            new_persons.append(
                {
                    "name": persona.name,
                    "description": persona.description or "",
                }
            )

    parsed_meta["persons"] = normalized_persons
    if normalized_descriptions:
        parsed_meta["person_descriptions"] = normalized_descriptions
    else:
        parsed_meta.pop("person_descriptions", None)

    if new_persons:
        parsed_meta["new_persons"] = new_persons
    else:
        parsed_meta.pop("new_persons", None)

    return json.dumps(parsed_meta, ensure_ascii=False, sort_keys=True)
