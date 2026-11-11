"""Selected26 is a distinct chamber contract, never period09 inferred from run."""
import hashlib
import json
from pathlib import Path

import pytest
import uproot

from mc_simulation.geant4.legacy_response import read_selected26_newplan, write_newplan_config

DATA = Path(__file__).resolve().parents[1] / "docs/reference/fortran/prog/data"


def test_selected26_source_fields_and_typed_atomic_config(tmp_path):
    response = read_selected26_newplan(DATA)
    assert [response[k] for k in ("xp1_cm", "xp2_cm", "zp1_cm", "zp2_cm", "nf1", "nf2", "angle_deg")] == [48.,57.6,94.4,134.4,320,384,-45.]
    assert response["sources"][0]["sha256"] == hashlib.sha256((DATA / "base/data26.base").read_bytes()).hexdigest()
    assert response["baseline"] == ["GRAAL_26", "GRAAL_NEW_PLAN", "GRAAL_OLD_CYL"]
    output = tmp_path / "config.root"
    write_newplan_config(DATA, output)
    original = output.read_bytes()
    with pytest.raises(FileExistsError): write_newplan_config(DATA, output)
    assert output.read_bytes() == original
    with uproot.open(output) as root:
        assert root["scalars"].num_entries == 1
        assert root["scalars"]["nf1"].typename == "int32_t"
        assert root["scalars"]["xp1_cm"].typename == "double"
        assert json.loads(str(root["metadata"])) == response
    assert not list(tmp_path.glob("*.partial"))


@pytest.mark.parametrize("record,value", [(84,"-48."),(85,"NaN"),(92,"00256"),(114,"45."),(118,"0.99")])
def test_rejects_wrong_newplan_configuration(tmp_path, record, value):
    lines = (DATA / "base/data26.base").read_text().splitlines()
    lines[record-1] = value.ljust(15) + lines[record-1][15:]
    (tmp_path / "base").mkdir()
    (tmp_path / "base/data26.base").write_text("\n".join(lines))
    with pytest.raises(ValueError): read_selected26_newplan(tmp_path)


def test_record_labels_and_data09_identity_cannot_masquerade_as_selected26(tmp_path):
    (tmp_path / "base").mkdir()
    target = tmp_path / "base/data26.base"
    target.write_bytes((DATA / "base/data09.base").read_bytes())
    with pytest.raises(ValueError): read_selected26_newplan(tmp_path)
    target.write_text((DATA / "base/data26.base").read_text().replace("!XP1", "!BAD"))
    with pytest.raises(ValueError, match="label XP1"): read_selected26_newplan(tmp_path)
