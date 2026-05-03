import json
import unittest
from unittest import mock

from flask import Flask

from app.extensions import db
from app.message_job import process_messages
from app.models import Chat, Location, Message, MessageType, Persona, Status


class _SocketStub:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def emit(self, event: str, payload: dict, **kwargs: object) -> None:
        self.events.append({"event": event, "payload": payload, "kwargs": kwargs})


class ProcessMessagesLocationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = Flask(__name__)
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        db.init_app(self.app)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _create_chat_with_pending_user_message(
        self, *, strategy_id: str = "rpg"
    ) -> Chat:
        chat = Chat(id="chat_1", name="test chat", strategy_id=strategy_id)
        db.session.add(chat)
        db.session.add(
            Message(
                id="user_1",
                chat_id=chat.id,
                sender_type=MessageType.USER,
                message="where are we?",
                status=Status.NEW,
            )
        )
        db.session.commit()
        return chat

    def test_new_location_is_created_linked_and_exposed_in_meta(self) -> None:
        chat = self._create_chat_with_pending_user_message()
        socket = _SocketStub()
        assistant_content = (
            "Paragraph one.\n\nParagraph two.\n\n"
            '{"location":"  Dark   Forest ","location_description":"Misty pines",'
            '"persons":[],"clothing":{},"ammunition":{}}'
        )

        with (
            mock.patch("app.message_job.ollama.chat", return_value={"message": {"content": assistant_content}}),
            mock.patch("app.message_job.count_tokens", return_value=0),
        ):
            process_messages(socket)

        location = Location.query.one()
        self.assertEqual(location.name, "Dark Forest")
        self.assertEqual(location.description, "Misty pines")
        self.assertIn(location, chat.available_locations)

        assistant_message = Message.query.filter_by(sender_type=MessageType.ASSISTANT).one()
        parsed_meta = json.loads(assistant_message.assistant_meta or "{}")
        self.assertEqual(parsed_meta["location"], "Dark Forest")
        self.assertEqual(parsed_meta["location_description"], "Misty pines")
        self.assertEqual(
            parsed_meta["new_location"],
            {"name": "Dark Forest", "description": "Misty pines"},
        )

    def test_existing_location_is_reused_case_insensitively(self) -> None:
        chat = self._create_chat_with_pending_user_message()
        existing_location = Location(name="Dark Forest", description="Known place")
        db.session.add(existing_location)
        db.session.commit()
        socket = _SocketStub()
        assistant_content = (
            "Paragraph one.\n\nParagraph two.\n\n"
            '{"location":" dark   forest ","location_description":"Should be ignored",'
            '"persons":[],"clothing":{},"ammunition":{},"new_location":{"name":"x","description":"x"}}'
        )

        with (
            mock.patch("app.message_job.ollama.chat", return_value={"message": {"content": assistant_content}}),
            mock.patch("app.message_job.count_tokens", return_value=0),
        ):
            process_messages(socket)

        self.assertEqual(Location.query.count(), 1)
        self.assertIn(existing_location, chat.available_locations)

        assistant_message = Message.query.filter_by(sender_type=MessageType.ASSISTANT).one()
        parsed_meta = json.loads(assistant_message.assistant_meta or "{}")
        self.assertEqual(parsed_meta["location"], "dark forest")
        self.assertNotIn("new_location", parsed_meta)

    def test_count_tokens_falls_back_to_zero_when_tokenizer_unavailable(self) -> None:
        with mock.patch("app.message_job._tokenizer", side_effect=RuntimeError("offline")):
            from app.message_job import count_tokens

            self.assertEqual(count_tokens([{"role": "user", "content": "hello"}]), 0)

    def test_new_persons_are_created_linked_and_exposed_in_meta(self) -> None:
        chat = self._create_chat_with_pending_user_message()
        socket = _SocketStub()
        assistant_content = (
            "Paragraph one.\n\nParagraph two.\n\n"
            '{"location":"Dark Forest","location_description":"Misty pines",'
            '"persons":["  Akira  ","Ember"],'
            '"person_descriptions":{"Akira":"Scout with a cold stare"," Ember ":"Fast sharpshooter"},'
            '"clothing":{"Akira":"cloak","Ember":"jacket"},'
            '"ammunition":{"Akira":"knife","Ember":"pistol"}}'
        )

        with (
            mock.patch("app.message_job.ollama.chat", return_value={"message": {"content": assistant_content}}),
            mock.patch("app.message_job.count_tokens", return_value=0),
        ):
            process_messages(socket)

        personas = Persona.query.order_by(Persona.name.asc()).all()
        self.assertEqual([persona.name for persona in personas], ["Akira", "Ember"])
        self.assertTrue(all(persona in chat.personas for persona in personas))

        assistant_message = Message.query.filter_by(sender_type=MessageType.ASSISTANT).one()
        parsed_meta = json.loads(assistant_message.assistant_meta or "{}")
        self.assertEqual(parsed_meta["persons"], ["Akira", "Ember"])
        self.assertEqual(
            parsed_meta["new_persons"],
            [
                {"name": "Akira", "description": "Scout with a cold stare"},
                {"name": "Ember", "description": "Fast sharpshooter"},
            ],
        )

    def test_existing_person_is_reused_case_insensitively(self) -> None:
        chat = self._create_chat_with_pending_user_message()
        existing_persona = Persona(name="Akira", description="Known person")
        db.session.add(existing_persona)
        db.session.commit()
        socket = _SocketStub()
        assistant_content = (
            "Paragraph one.\n\nParagraph two.\n\n"
            '{"location":"Dark Forest","persons":[" akira "],'
            '"person_descriptions":{"akira":"Should be ignored for creation"},'
            '"clothing":{"akira":"cloak"},'
            '"ammunition":{"akira":"knife"},'
            '"new_persons":[{"name":"x","description":"x"}]}'
        )

        with (
            mock.patch("app.message_job.ollama.chat", return_value={"message": {"content": assistant_content}}),
            mock.patch("app.message_job.count_tokens", return_value=0),
        ):
            process_messages(socket)

        self.assertEqual(Persona.query.count(), 1)
        self.assertIn(existing_persona, chat.personas)

        assistant_message = Message.query.filter_by(sender_type=MessageType.ASSISTANT).one()
        parsed_meta = json.loads(assistant_message.assistant_meta or "{}")
        self.assertEqual(parsed_meta["persons"], ["akira"])
        self.assertNotIn("new_persons", parsed_meta)

    def test_language_teacher_does_not_sync_scene_entities(self) -> None:
        chat = self._create_chat_with_pending_user_message(strategy_id="language_teacher")
        socket = _SocketStub()
        assistant_content = (
            "Bonjour! Essayez encore.\n\n"
            '{"location":"Paris","persons":["Marie"],'
            '"clothing":{},"ammunition":{}}'
        )

        with (
            mock.patch("app.message_job.ollama.chat", return_value={"message": {"content": assistant_content}}),
            mock.patch("app.message_job.count_tokens", return_value=0),
        ):
            process_messages(socket)

        self.assertEqual(Location.query.count(), 0)
        self.assertEqual(Persona.query.count(), 0)
        assistant_message = Message.query.filter_by(sender_type=MessageType.ASSISTANT).one()
        self.assertIsNone(assistant_message.assistant_meta)


if __name__ == "__main__":
    unittest.main()
