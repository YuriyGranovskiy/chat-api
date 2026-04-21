import os
import tempfile
import unittest
from io import BytesIO

from flask import Flask
from werkzeug.datastructures import FileStorage

import app.models  # noqa: F401 — register models with SQLAlchemy
from app import services
from app.extensions import db
from app.models import World

# Minimal valid GIF (1x1 transparent).
ONE_PX_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00"
    b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


class EntityImageServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        self.app.config["MEDIA_ROOT"] = self._tmpdir.name
        self.app.config["MAX_IMAGE_BYTES"] = 1024 * 1024
        self.app.config["ALLOWED_IMAGE_MIMES"] = frozenset(
            {"image/png", "image/jpeg", "image/webp", "image/gif"}
        )
        self.app.config["MIME_TO_EXT"] = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }
        db.init_app(self.app)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        self._tmpdir.cleanup()

    def test_set_entity_image_writes_file_and_token(self) -> None:
        world = services.create_entity(World, name="W", description="d")
        fs = FileStorage(
            stream=BytesIO(ONE_PX_GIF),
            filename="x.gif",
            content_type="image/gif",
        )
        services.set_entity_image(World, world.id, fs)
        row = World.query.get(world.id)
        self.assertIsNotNone(row)
        self.assertIsNotNone(row.image_access_token)
        self.assertIsNotNone(row.image_path)
        disk_path = os.path.join(self.app.config["MEDIA_ROOT"], row.image_path)
        self.assertTrue(os.path.isfile(disk_path))

    def test_delete_entity_removes_image_file(self) -> None:
        world = services.create_entity(World, name="W", description="d")
        fs = FileStorage(
            stream=BytesIO(ONE_PX_GIF),
            filename="x.gif",
            content_type="image/gif",
        )
        services.set_entity_image(World, world.id, fs)
        rel = World.query.get(world.id).image_path
        disk_path = os.path.join(self.app.config["MEDIA_ROOT"], rel)
        self.assertTrue(os.path.isfile(disk_path))
        services.delete_entity(World, world.id)
        self.assertFalse(os.path.isfile(disk_path))

    def test_resolve_media_file(self) -> None:
        world = services.create_entity(World, name="W", description="d")
        fs = FileStorage(
            stream=BytesIO(ONE_PX_GIF),
            filename="x.gif",
            content_type="image/gif",
        )
        services.set_entity_image(World, world.id, fs)
        token = World.query.get(world.id).image_access_token
        resolved = services.resolve_media_file(token)
        self.assertIsNotNone(resolved)
        abs_path, mime = resolved
        self.assertEqual(mime, "image/gif")
        self.assertTrue(os.path.isfile(abs_path))

    def test_clear_entity_image_removes_file(self) -> None:
        world = services.create_entity(World, name="W", description="d")
        fs = FileStorage(
            stream=BytesIO(ONE_PX_GIF),
            filename="x.gif",
            content_type="image/gif",
        )
        services.set_entity_image(World, world.id, fs)
        rel = World.query.get(world.id).image_path
        disk_path = os.path.join(self.app.config["MEDIA_ROOT"], rel)
        services.clear_entity_image(World, world.id)
        self.assertFalse(os.path.isfile(disk_path))
        row = World.query.get(world.id)
        self.assertIsNone(row.image_path)
        self.assertIsNone(row.image_access_token)
