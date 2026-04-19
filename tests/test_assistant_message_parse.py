import importlib.util
import json
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PARSE_PATH = _ROOT / "app" / "assistant_message_parse.py"


def _load_parse_module():
    spec = importlib.util.spec_from_file_location("assistant_message_parse", _PARSE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_parse = _load_parse_module()
split_assistant_content = _parse.split_assistant_content
assistant_content_for_model = _parse.assistant_content_for_model
assistant_display_for_client = _parse.assistant_display_for_client
assistant_raw_for_model = _parse.assistant_raw_for_model


class SplitAssistantContentTests(unittest.TestCase):
    def test_fenced_json_block(self) -> None:
        raw = (
            'Para one.\n\nPara two.\n\n```json\n'
            '{"location": "Mansion: Grand hall", "persons": ["Sharn", "Ember"]}\n```'
        )
        display, meta = split_assistant_content(raw)
        self.assertEqual(display, "Para one.\n\nPara two.")
        self.assertIsNotNone(meta)
        self.assertEqual(
            json.loads(meta),
            {"location": "Mansion: Grand hall", "persons": ["Sharn", "Ember"]},
        )

    def test_trailing_json(self) -> None:
        raw = (
            'First paragraph.\n\nSecond paragraph.\n\n'
            '{"location": "A", "persons": ["B"]}'
        )
        display, meta = split_assistant_content(raw)
        self.assertEqual(display, "First paragraph.\n\nSecond paragraph.")
        self.assertEqual(json.loads(meta or ""), {"location": "A", "persons": ["B"]})

    def test_no_json_returns_original(self) -> None:
        raw = "Just narrative.\n\nNo metadata here."
        display, meta = split_assistant_content(raw)
        self.assertEqual(display, raw)
        self.assertIsNone(meta)

    def test_invalid_trailing_brace_returns_original(self) -> None:
        raw = "Hello { not json"
        display, meta = split_assistant_content(raw)
        self.assertEqual(display, raw)
        self.assertIsNone(meta)

    def test_fenced_takes_precedence_over_trailing(self) -> None:
        raw = 'Text\n```json\n{"location": "x", "persons": []}\n```\n'
        display, meta = split_assistant_content(raw)
        self.assertEqual(display.strip(), "Text")
        self.assertEqual(json.loads(meta or ""), {"location": "x", "persons": []})


class AssistantHelpersTests(unittest.TestCase):
    def test_assistant_content_for_model_roundtrip(self) -> None:
        display = "A\n\nB"
        meta = '{"location": "x", "persons": []}'
        full = assistant_content_for_model(display, meta)
        d2, m2 = split_assistant_content(full)
        self.assertEqual(d2, display)
        self.assertEqual(
            json.loads(m2 or "{}"),
            json.loads(meta),
        )

    def test_assistant_raw_for_model_legacy(self) -> None:
        blob = 'Hi\n\n{"location": "z", "persons": []}'
        self.assertEqual(assistant_raw_for_model(blob, None), blob)

    def test_assistant_raw_for_model_split_row(self) -> None:
        self.assertEqual(
            assistant_raw_for_model("Hi", '{"location": "z", "persons": []}'),
            'Hi\n\n{"location": "z", "persons": []}',
        )

    def test_assistant_display_for_client_with_meta(self) -> None:
        self.assertEqual(
            assistant_display_for_client("visible only", '{"x": 1}'),
            "visible only",
        )

    def test_assistant_display_for_client_legacy_lazy_strip(self) -> None:
        self.assertEqual(
            assistant_display_for_client(
                'Story\n\n{"location": "z", "persons": []}',
                None,
            ),
            "Story",
        )


if __name__ == "__main__":
    unittest.main()
