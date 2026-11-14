import hashlib
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "provenance" / "private-resources.json"
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


class PrivateResourceIndexTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = json.loads(INDEX.read_text(encoding="utf-8"))

    def test_points_at_private_store(self):
        self.assertEqual(self.index["repository"], "Takazudo/circuit-dev-resources")
        self.assertEqual(self.index["visibility"], "private")

    def test_documents_are_well_formed_and_unique(self):
        docs = self.index["documents"]
        self.assertTrue(docs)
        hashes = [d["sha256"] for d in docs]
        paths = [d["path"] for d in docs]
        self.assertEqual(len(hashes), len(set(hashes)))
        self.assertEqual(len(paths), len(set(paths)))
        for doc in docs:
            self.assertRegex(doc["sha256"], SHA256)
            self.assertRegex(doc["path"], r"^[a-z0-9-]+/[a-z0-9-]+/[a-z0-9.-]+\.[a-z]+$")
            self.assertGreater(doc["bytes"], 0)

    def test_cited_hashes_are_still_cited(self):
        for doc in self.index["documents"]:
            for rel in doc["cited_by"]:
                text = (ROOT / rel).read_text(encoding="utf-8")
                self.assertIn(doc["sha256"], text, f"{rel} no longer cites {doc['path']}")

    def test_no_datasheet_bytes_committed_outside_a5(self):
        tracked = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
        ).stdout.decode().split("\0")
        indexed = {d["sha256"] for d in self.index["documents"]}
        for rel in tracked:
            if not rel or rel.startswith("engineering/a5/"):
                continue
            path = ROOT / rel
            if path.suffix.lower() not in {".pdf", ".png", ".txt"} or not path.is_file():
                continue
            self.assertNotIn(sha256_bytes(path.read_bytes()), indexed, f"{rel} duplicates a private resource")

    def test_a5_capture_copy_matches_immutable_tree(self):
        for capture in self.index["captures"]:
            base = ROOT / "engineering" / "a5"
            files = sorted(
                p for d in capture["source_dirs"] for p in (ROOT / d).glob("*.json")
            )
            self.assertEqual(len(files), capture["files"])
            lines = "".join(
                f"{sha256_bytes(p.read_bytes())}  ./{p.relative_to(base).as_posix()}\n" for p in files
            )
            self.assertEqual(sha256_bytes(lines.encode()), capture["sha256"])


if __name__ == "__main__":
    unittest.main()
