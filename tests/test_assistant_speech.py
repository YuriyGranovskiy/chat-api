"""Unit tests for assistant TTS storage and httpx client (no full OpenAPI stack)."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask

import app.models  # noqa: F401 — register models
from app import services
from app import tts_client
from app.extensions import bcrypt, db
from app.models import Message, MessageType, User, UserProfile

FAKE_WAV = b"RIFF\x00\x00\x00fake_wav_placeholder"


class _TTSResp:
    status_code = 200
    content = FAKE_WAV
    text = ""

    def __init__(self) -> None:
        self.headers = {"Content-Type": "audio/wav"}

    @property
    def reason_phrase(self) -> str:
        return "OK"


def _make_flask_app(media_root: str) -> Flask:
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MEDIA_ROOT"] = media_root
    app.config["TTS_SYNTHESIS_URL"] = "http://127.0.0.1:8091/v1/speech"
    app.config["TTS_HTTP_TIMEOUT_SEC"] = 30.0
    db.init_app(app)
    bcrypt.init_app(app)
    return app


class AssistantSpeechServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._media_dir = tempfile.TemporaryDirectory(prefix="chat_tts_")
        self.app = _make_flask_app(self._media_dir.name)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        u = User(id="user_1", username="alice")
        u.set_password("pw")
        db.session.add(u)
        db.session.add(UserProfile(id="prof_1", name="p"))
        db.session.commit()
        self.chat_id = services.create_user_chat(
            user_id="user_1",
            name="c",
            profile_id="prof_1",
            language="en",
        )
        self.msg_assistant_id = services.create_message(
            self.chat_id, "Hi there", MessageType.ASSISTANT
        )
        self.msg_user_id = services.create_message(
            self.chat_id, "user says", MessageType.USER
        )

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        self._media_dir.cleanup()

    def test_persist_and_resolve_speech(self) -> None:
        msg = Message.query.get(self.msg_assistant_id)
        self.assertIsNotNone(msg)
        services.persist_assistant_speech(msg, FAKE_WAV, "audio/wav")
        msg2 = Message.query.get(self.msg_assistant_id)
        self.assertTrue(services.assistant_message_has_speech(msg2))
        pair = services.resolve_assistant_speech_file(msg2)
        self.assertIsNotNone(pair)
        abs_path, mime = pair
        self.assertEqual(mime, "audio/wav")
        self.assertTrue(os.path.isfile(abs_path))
        with open(abs_path, "rb") as fh:
            self.assertEqual(fh.read(), FAKE_WAV)

    def test_get_messages_has_speech_flags(self) -> None:
        msg = Message.query.get(self.msg_assistant_id)
        services.persist_assistant_speech(msg, FAKE_WAV, "audio/wav")
        rows = services.get_messages(self.chat_id, limit=10)
        by_id = {r["id"]: r for r in rows}
        self.assertTrue(by_id[self.msg_assistant_id]["has_speech"])
        self.assertFalse(by_id[self.msg_user_id]["has_speech"])

    def test_delete_message_removes_speech_file(self) -> None:
        msg = Message.query.get(self.msg_assistant_id)
        services.persist_assistant_speech(msg, FAKE_WAV, "audio/wav")
        rel = Message.query.get(self.msg_assistant_id).assistant_speech_path
        disk = os.path.join(self._media_dir.name, rel)
        self.assertTrue(os.path.isfile(disk))
        services.delete_message(self.msg_assistant_id)
        self.assertFalse(os.path.isfile(disk))

    def test_edit_assistant_clears_speech_metadata(self) -> None:
        msg = Message.query.get(self.msg_assistant_id)
        services.persist_assistant_speech(msg, FAKE_WAV, "audio/wav")
        services.edit_message(self.msg_assistant_id, "New reply text")
        row = Message.query.get(self.msg_assistant_id)
        self.assertIsNone(row.assistant_speech_path)
        self.assertIsNone(row.assistant_speech_mime)

    def test_regenerate_deletes_speech_file(self) -> None:
        user_mid = services.create_message(self.chat_id, "q", MessageType.USER)
        asst_mid = services.create_message(self.chat_id, "a", MessageType.ASSISTANT)
        msg = Message.query.get(asst_mid)
        services.persist_assistant_speech(msg, FAKE_WAV, "audio/wav")
        rel = Message.query.get(asst_mid).assistant_speech_path
        disk = os.path.join(self._media_dir.name, rel)
        self.assertTrue(os.path.isfile(disk))
        services.regenerate_message(asst_mid)
        self.assertFalse(os.path.isfile(disk))


class TTSClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self._media_dir = tempfile.TemporaryDirectory()
        self.app = _make_flask_app(self._media_dir.name)

    def tearDown(self) -> None:
        self._media_dir.cleanup()

    def test_empty_url_returns_502(self) -> None:
        self.app.config["TTS_SYNTHESIS_URL"] = ""
        with self.app.app_context():
            with self.assertRaises(tts_client.TTSSynthesisError) as ctx:
                tts_client.synthesize_speech("hello", "en")
            self.assertEqual(ctx.exception.status_code, 502)

    @patch("app.tts_client.httpx.post", return_value=_TTSResp())
    def test_synthesize_success(self, _mock_post) -> None:
        with self.app.app_context():
            body, mime = tts_client.synthesize_speech("hello", "en-US")
            self.assertEqual(body, FAKE_WAV)
            self.assertEqual(mime, "audio/wav")


if __name__ == "__main__":
    unittest.main()
