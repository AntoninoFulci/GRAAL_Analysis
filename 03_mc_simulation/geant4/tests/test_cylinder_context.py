"""Passive reset information must survive without recording every passive step."""
from collections import Counter
import hashlib
from pathlib import Path

import numpy as np
import uproot

from mc_simulation.geant4.tests.test_detector_hits import native, transport


def test_cylinder_context_preserves_callback_order_across_runs(native, tmp_path):
    output = transport(native, tmp_path,
        "/gps/particle chargedgeantino\n/gps/energy 200 MeV\n"
        "/gps/position 0 0 0 mm\n/gps/direction 1 0 0\n/run/beamOn 2\n"
        "/gps/position 1000 1000 -3000 mm\n/gps/direction 0 0 -1\n/run/beamOn 1\n"
        "/gps/position 0 0 0 mm\n/gps/direction 1 0 0\n/run/beamOn 1\n")
    import json
    with uproot.open(output / "transport.root") as root:
        assert "cylinder_step_context" in root, "Passive reset context is discarded"
        summary = json.loads(str(root["summary"]))
        metadata = json.loads(str(root["cylinder_context_metadata"]))
        source = Path(__file__).resolve().parents[3] / "docs/reference/fortran/prog/laggen/src/gustep.F"
        assert metadata.get("legacy_source_sha256") == hashlib.sha256(source.read_bytes()).hexdigest()
        assert summary["hit_schema_version"] == 2
        assert summary["cylinder_context_schema"] == 1
        context = root["cylinder_step_context"].arrays(library="np")
        steps = root["detector_steps"].arrays(library="np")
        events = root["events"].arrays(library="np")
        channels = root["channels"].arrays(library="np")
    roles = dict(zip(channels["path"], channels["sensitive"]))
    expected = np.array([i for i, path in enumerate(steps["path"])
                         if roles[path] in (6, 7, 10, 11)], dtype=np.uint64)
    assert len(expected) > 0
    assert np.array_equal(context["source_step_entry"], expected)
    assert np.array_equal(context["run"], steps["run"][expected])
    assert np.array_equal(context["event"], steps["event"][expected])
    assert np.all(steps["edep_MeV"][expected] == 0), "Zero deposit context must be retained"
    assert np.all(np.diff(context["callback_index"].astype(np.int64)) > 0)
    assert np.all(np.diff(context["passive_epoch"].astype(np.int64)) >= 0)
    # Every earlier callback is either a stored sensitive row or a passive reset.
    assert np.array_equal(context["callback_index"], expected + context["passive_epoch"])
    assert context["passive_epoch"][0] > 0
    assert summary["all_callbacks"] == int(events["steps"].sum())
    assert summary["passive_callbacks"] == summary["all_callbacks"] - len(steps["run"])
    assert summary["cylinder_context_rows"] == len(expected)
    assert set(context["run"].tolist()) == {0, 2}
    assert context["passive_epoch"][context["run"] == 2][0] > context["passive_epoch"][context["run"] == 0][-1]
    counts = Counter(zip(context["run"].tolist(), context["event"].tolist()))
    offset = 0
    for run, event, count in zip(events["run"], events["event"], events["steps"]):
        selected = (context["run"] == run) & (context["event"] == event)
        assert np.all(context["callback_index"][selected] >= offset)
        assert np.all(context["callback_index"][selected] < offset + int(count))
        offset += int(count)
    assert counts[(1, 0)] == 0  # Passive-only event still advances reset state.
