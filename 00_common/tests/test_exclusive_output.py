import pytest

from graal_common.io.filesystem import atomic_output_directory


def test_exclusive_output_reservation_prevents_competing_writer(tmp_path):
    destination = tmp_path / "study"
    with atomic_output_directory(destination, overwrite=False) as stage:
        (stage / "result").write_text("first")
        with pytest.raises(FileExistsError):
            with atomic_output_directory(destination, overwrite=False):
                pytest.fail("competing output writer entered")
    assert (destination / "result").read_text() == "first"
    with pytest.raises(FileExistsError):
        with atomic_output_directory(destination, overwrite=False):
            pytest.fail("existing study was overwritten")
    assert (destination / "result").read_text() == "first"


def test_failed_exclusive_output_removes_only_its_empty_reservation(tmp_path):
    destination = tmp_path / "study"
    with pytest.raises(RuntimeError):
        with atomic_output_directory(destination, overwrite=False):
            raise RuntimeError("failure")
    assert not destination.exists()
    with pytest.raises(RuntimeError):
        with atomic_output_directory(destination, overwrite=False):
            (destination / "foreign").write_text("preserve")
            raise RuntimeError("failure")
    assert (destination / "foreign").read_text() == "preserve"
