"""Exercise malformed/unsupported snapshots against the actual GEANT4 binary."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class NativeInputTests(unittest.TestCase):
    def setUp(self):
        self.executable = os.environ.get("GRAAL_GEOMETRY_EXE")
        if not self.executable:
            self.skipTest("Set GRAAL_GEOMETRY_EXE for native input tests")
        self.source = (
            Path(__file__).resolve().parents[1] / "reference/geometry.g3"
        ).read_text()

    def assert_rejected(self, text, message):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "malformed.g3"
            source.write_text(text)
            result = subprocess.run(
                [self.executable, str(source), str(root / "output")],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stderr[-2000:])
            self.assertIn(message, result.stderr)
            self.assertFalse((root / "output/summary.json").exists())

    def test_axial_cutter_without_parameters_is_rejected(self):
        lines = self.source.splitlines()
        for index, line in enumerate(lines):
            row = line.split()
            if row[:2] == ["V", "FEN3"]:
                lines[index] = "V FEN3 TUBE 10 0"
        self.assert_rejected("\n".join(lines), "Invalid parameter count for FEN3")

    def test_transversely_shifted_cutter_is_rejected(self):
        lines = self.source.splitlines()
        for index, line in enumerate(lines):
            row = line.split()
            if row[:3] == ["P", "FEN3", "2"]:
                row[4] = "10.0"
                lines[index] = " ".join(row)
        self.assert_rejected("\n".join(lines), "unexpected transverse displacement")

    def test_missing_rotation_is_rejected(self):
        self.assert_rejected(
            "\n".join(
                line
                for line in self.source.splitlines()
                if line.split()[:2] != ["R", "481"]
            ),
            "Unresolved placement",
        )

    def test_existing_output_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(__file__).resolve().parents[1] / "reference/geometry.g3"
            sentinel = Path(directory) / "sentinel"
            sentinel.write_text("keep")
            result = subprocess.run(
                [self.executable, str(source), directory],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("refusing overwrite", result.stderr)
            self.assertEqual(sentinel.read_text(), "keep")
