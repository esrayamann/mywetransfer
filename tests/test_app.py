import os
import shutil
import tempfile
import unittest
from io import BytesIO
from pathlib import Path


TEST_ROOT = Path(tempfile.mkdtemp(prefix="mywetransfer-tests-"))
os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_ROOT / 'test.db'}",
    "SECRET_KEY": "test-secret-key",
    "UPLOAD_FOLDER": str(TEST_ROOT / "uploads"),
    "FLASK_ENV": "development",
    "MAX_UPLOAD_MB": "5",
    "MAIL_USERNAME": "",
    "MAIL_PASSWORD": "",
})

from app import File, app, db  # noqa: E402


class MyWeTransferTestCase(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, SERVER_NAME="localhost")
        self.client = app.test_client()
        with app.app_context():
            db.drop_all()
            db.create_all()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def csrf_token(self):
        self.client.get("/")
        with self.client.session_transaction() as session:
            return session["_csrf_token"]

    def register_and_login(self):
        response = self.client.post("/register", data={
            "csrf_token": self.csrf_token(),
            "username": "demo_user",
            "email": "demo@example.com",
            "password": "safe-password-123",
        })
        self.assertEqual(response.status_code, 302)
        return self.client.post("/login", data={
            "csrf_token": self.csrf_token(),
            "username": "demo@example.com",
            "password": "safe-password-123",
        })

    def test_post_requests_require_csrf_token(self):
        response = self.client.post("/register", data={
            "username": "demo_user",
            "email": "demo@example.com",
            "password": "safe-password-123",
        })
        self.assertEqual(response.status_code, 400)

    def test_user_cannot_access_admin_panel(self):
        response = self.register_and_login()
        self.assertTrue(response.location.endswith("/user_home"))
        self.assertEqual(self.client.get("/admin").status_code, 403)

    def test_transfer_uses_random_archive_name_and_downloads_as_attachment(self):
        self.register_and_login()
        response = self.client.post("/send_file", data={
            "csrf_token": self.csrf_token(),
            "sender_email": "ignored@example.com",
            "receiver_email": "receiver@example.com",
            "file": (BytesIO(b"hello transfer"), "report.txt"),
        }, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200)

        with app.app_context():
            transfer = File.query.one()
            self.assertTrue(transfer.filename.startswith("transfer-"))
            self.assertNotIn("report", transfer.filename)
            self.assertTrue(Path(app.config["UPLOAD_FOLDER"], transfer.filename).is_file())
            filename = transfer.filename

        response = self.client.get(f"/download/{filename}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response.headers["Content-Disposition"])
        response.close()


def tearDownModule():
    with app.app_context():
        db.session.remove()
        db.engine.dispose()
    shutil.rmtree(TEST_ROOT, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
