"""Independent checks for the frozen GRAAL_26 / old-cylinder geometry.

These catch missing copies, a different target/profile, and confusion between
tracking-medium and material IDs. They do not assert physical calibration.
"""

import unittest
from pathlib import Path

REFERENCE = Path(__file__).resolve().parents[1] / "reference" / "geometry.g3"


class LegacyReferenceTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(REFERENCE.is_file(), "GEANT3 reference has not been extracted")
        self.rows = [
            line.split() for line in REFERENCE.read_text().splitlines() if line.strip()
        ]

    def test_world_and_deuterium_target(self):
        volumes = {r[1]: r for r in self.rows if r[0] == "V"}
        self.assertEqual(volumes["LAGR"][2:5], ["BOX", "7", "3"])
        self.assertEqual(list(map(float, volumes["LAGR"][5:])), [200.0, 200.0, 370.0])
        self.assertEqual(volumes["CIBM"][2:5], ["TUBE", "1", "3"])
        self.assertAlmostEqual(float(volumes["CIBM"][7]), 3.06, places=5)
        material = next(r for r in self.rows if r[:2] == ["M", "1"])
        self.assertEqual(material[2], "DEUTERIUM$")
        self.assertAlmostEqual(float(material[5]), 0.162, places=6)

    def test_all_bgo_crystals_keep_individual_shape_and_identity(self):
        crystals = [r for r in self.rows if r[:2] == ["P", "BGO"]]
        self.assertEqual(sorted(int(r[2]) for r in crystals), list(range(1, 481)))
        self.assertEqual({r[3] for r in crystals}, {"NID1", "NID2"})
        self.assertTrue(all(r[9] == "11" for r in crystals))
        self.assertGreater(len({tuple(r[10:]) for r in crystals}), 1)

    def test_medium_mapping_and_active_subdetectors(self):
        media = {int(r[1]): int(r[2]) for r in self.rows if r[0] == "T"}
        self.assertEqual(media[16], 14)
        self.assertEqual(media[20], 18)
        self.assertEqual(media[25], 11)
        placements = [r for r in self.rows if r[0] == "P"]
        names = {r[1] for r in placements}
        self.assertTrue({"CYL1", "CYL2", "PLG1", "PLG2", "DSK1", "DSK2"} <= names)
        self.assertTrue({"BC44", "CYGI", "CYGE"}.isdisjoint(names))
        self.assertEqual(sum(r[1] == "CASC" for r in placements), 16)
        self.assertEqual(sum(r[1] in {"CEL1", "CES1"} for r in placements), 26)
        self.assertEqual(sum(r[1] == "CEL2" for r in placements), 26)


if __name__ == "__main__":
    unittest.main()
