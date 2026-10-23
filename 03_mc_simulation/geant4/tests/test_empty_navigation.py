"""A vacuous 0-versus-0 navigation comparison must never certify geometry."""

import os
import tempfile
import unittest
from pathlib import Path

from verify_native import verify


class NavigationContractTests(unittest.TestCase):
    def test_empty_reference_cannot_pass(self):
        executable = os.environ.get("GRAAL_GEOMETRY_EXE")
        if not executable:
            self.skipTest(
                "Set GRAAL_GEOMETRY_EXE to run the native integration contract"
            )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference = Path(__file__).resolve().parents[1] / "reference/geometry.g3"
            navigation = root / "empty.g3"
            navigation.write_text("")
            with self.assertRaisesRegex(AssertionError, "[Ee]mpty|[Nn]o navigation"):
                verify(Path(executable), reference, navigation, root / "conversion")
