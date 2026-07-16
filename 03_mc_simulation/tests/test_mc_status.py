import os
import time
from datetime import datetime

import pytest

from mc_simulation import mc_status as ms


def _make_mc(data_dir, name, age_days=0.0):
    path = data_dir / f"{name}_mc.root"
    path.write_bytes(b"")
    if age_days:
        old = time.time() - age_days * 86400
        os.utime(path, (old, old))
    return path


def test_all_channels_missing(tmp_path):
    statuses = ms.status(tmp_path)
    assert len(statuses) == len(ms.CHANNELS)
    assert all(not s.exists for s in statuses)
    assert ms.all_present(statuses) is False


def test_all_channels_present_and_fresh(tmp_path):
    for name in ms.CHANNELS:
        _make_mc(tmp_path, name, age_days=1.0)

    statuses = ms.status(tmp_path)
    assert ms.all_present(statuses) is True
    assert ms.stale(statuses) == []
    assert all(0.5 < s.age_days < 1.5 for s in statuses)


def test_one_channel_is_stale(tmp_path):
    for name in ms.CHANNELS:
        _make_mc(tmp_path, name, age_days=1.0)
    _make_mc(tmp_path, "pi0pi0", age_days=12.0)

    statuses = ms.status(tmp_path)
    stale = ms.stale(statuses)

    assert ms.all_present(statuses) is True  # stale still counts as present
    assert [s.name for s in stale] == ["pi0pi0"]
    assert stale[0].age_days > ms.STALE_DAYS


def test_a_fresh_file_is_not_stale(tmp_path):
    for name in ms.CHANNELS:
        _make_mc(tmp_path, name, age_days=9.0)

    # 9 days is under the 10-day threshold: no warning
    assert ms.stale(ms.status(tmp_path)) == []


def test_a_missing_file_has_no_age(tmp_path):
    _make_mc(tmp_path, "eta_pi0")
    statuses = {s.name: s for s in ms.status(tmp_path)}

    assert statuses["eta_pi0"].age_days is not None
    assert statuses["pi0pi0"].mtime is None
    assert statuses["pi0pi0"].age_days is None


def test_age_is_measured_against_the_given_now(tmp_path):
    path = _make_mc(tmp_path, "eta_pi0")
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    now = mtime.replace(year=mtime.year + 1)  # a year later

    statuses = {s.name: s for s in ms.status(tmp_path, now=now)}
    assert statuses["eta_pi0"].age_days > 360


def test_cli_exits_zero_when_everything_is_present(tmp_path):
    for name in ms.CHANNELS:
        _make_mc(tmp_path, name, age_days=1.0)

    assert ms.main(["--data-dir", str(tmp_path)]) == 0


def test_cli_exits_one_when_a_file_is_missing(tmp_path):
    for name in ms.CHANNELS[:-1]:
        _make_mc(tmp_path, name)

    assert ms.main(["--data-dir", str(tmp_path)]) == 1


def test_cli_still_exits_zero_when_files_are_stale(tmp_path, capsys):
    # stale warns, it does not block
    for name in ms.CHANNELS:
        _make_mc(tmp_path, name, age_days=30.0)

    assert ms.main(["--data-dir", str(tmp_path)]) == 0
    assert "WARNING" in capsys.readouterr().out


def test_cli_exits_two_on_internal_error(monkeypatch, capsys, tmp_path):
    # Exit 2 must be distinct from exit 1 ("a channel is missing"): the
    # pipeline treats them very differently (fatal vs. "go generate"), and
    # conflating them is exactly the bug this module used to have.
    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(ms, "status", _boom)

    assert ms.main(["--data-dir", str(tmp_path)]) == 2
    assert "boom" in capsys.readouterr().err


def test_cli_help_still_exits_zero_via_systemexit():
    # argparse's own --help path raises SystemExit(0); main() must let it
    # through rather than swallowing it into the generic error->2 handler.
    with pytest.raises(SystemExit) as excinfo:
        ms.main(["--help"])
    assert excinfo.value.code == 0
