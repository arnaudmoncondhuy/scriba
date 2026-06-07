"""
Tests du marqueur "deja traite par Scriba" (flux NTFS) et du filtrage
de scan_existing. Sans dependance reseau : Gemini n'est jamais sollicite.

Lancement : python -m unittest discover -s tests
"""

import queue
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scan_engine import ScanEngine, is_done, mark_done  # noqa: E402


class MarkerTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def _make(self, name: str) -> Path:
        f = self.dir / name
        f.write_bytes(b"%PDF-1.4 contenu de test")
        return f

    def test_roundtrip(self):
        f = self._make("scan.pdf")
        self.assertFalse(is_done(f))
        mark_done(f)
        self.assertTrue(is_done(f))

    def test_marker_does_not_alter_content(self):
        f = self._make("scan.pdf")
        before = f.read_bytes()
        mark_done(f)
        self.assertEqual(f.read_bytes(), before)

    def test_marker_follows_rename(self):
        f = self._make("scan.pdf")
        mark_done(f)
        g = f.with_name("facture_edf.pdf")
        f.rename(g)
        self.assertTrue(is_done(g))

    def test_scan_existing_skips_marked(self):
        a = self._make("brut_a.pdf")        # a traiter
        b = self._make("facture_edf.pdf")   # deja traite
        mark_done(b)

        engine = ScanEngine(api_key="x", model="m", watch_dir=self.dir)
        engine.scan_existing()

        queued = set()
        while True:
            try:
                queued.add(engine._queue.get_nowait())
            except queue.Empty:
                break

        self.assertIn(a, queued)
        self.assertNotIn(b, queued)

    def test_scan_existing_ignores_unsupported_extensions(self):
        pdf = self._make("scan.pdf")
        txt = self.dir / "notes.txt"
        txt.write_text("pas un scan")

        engine = ScanEngine(api_key="x", model="m", watch_dir=self.dir)
        engine.scan_existing()

        queued = set()
        while True:
            try:
                queued.add(engine._queue.get_nowait())
            except queue.Empty:
                break

        self.assertEqual(queued, {pdf})


if __name__ == "__main__":
    unittest.main()
