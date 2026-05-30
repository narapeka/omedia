from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from app.infra.log.app import AppLog


class AppLogTests(unittest.TestCase):
    def test_writes_plain_text_blocks_and_redacts_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = AppLog()
            log.configure(root)

            log.info(
                "provider.request",
                "Request completed",
                url="https://example.test/search?api_key=secret&query=avatar",
                detail="Authorization: Bearer abc123",
                token="direct-token",
                nested={"password": "nested-password", "safe": "api_key=inline-secret"},
            )

            content = next(root.glob("omedia-*.log")).read_text(encoding="utf-8")
            self.assertIn("INFO  [provider.request] Request completed", content)
            self.assertIn("query=avatar", content)
            self.assertIn("[redacted]", content)
            self.assertNotIn("secret", content)
            self.assertNotIn("abc123", content)
            self.assertNotIn("direct-token", content)
            self.assertNotIn("nested-password", content)
            self.assertTrue(content.endswith("\n\n"))

    def test_configure_prunes_logs_older_than_retention(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.mkdir(exist_ok=True)
            old_date = datetime.now().date() - timedelta(days=31)
            old_log = root / f"omedia-{old_date:%Y-%m-%d}.log"
            old_log.write_text("old", encoding="utf-8")

            AppLog().configure(root)

            self.assertFalse(old_log.exists())


if __name__ == "__main__":
    unittest.main()
