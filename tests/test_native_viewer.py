"""Exercise viewer path/command plumbing without Geant4, Qt, or transport."""
import os
from pathlib import Path
import subprocess

import pytest

REPO = Path(__file__).resolve().parents[1]
GDML = Path('results_test/archive/geant4-migration-audit-20261023/conversion-spack-certified/geometry.gdml')


@pytest.mark.parametrize('explicit', [False, True])
def test_native_viewer_delegates_to_portable_launcher(tmp_path, explicit):
    script = REPO / '03_mc_simulation/geant4/view_native.sh'
    geometry = tmp_path / 'explicit geometry.gdml'
    log = tmp_path / 'arguments'
    python = tmp_path / 'python'
    python.write_text('#!/bin/bash\nprintf "%s\\n" "$@" > "$VIEWER_LOG"\n')
    python.chmod(0o755)
    env = {**os.environ, 'PYTHON': str(python), 'VIEWER_LOG': str(log)}
    result = subprocess.run(['bash', str(script), *([str(geometry)] if explicit else [])],
                            env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert log.read_text().splitlines() == [
        '-B', str(script.with_name('run.py')), 'view',
        *(['--gdml', str(geometry)] if explicit else []),
    ]


def test_preserved_native_viewer_geometry_matches_registered_hash():
    import hashlib
    import json

    geometry = REPO / GDML
    if not geometry.is_file():
        pytest.skip('historical certified GDML is not available in this checkout')
    manifest = json.loads((REPO / '03_mc_simulation/geant4/reference/manifest.json').read_text())
    historical_path = 'results/geant4-migration-audit-20261023/conversion-spack-certified/geometry.gdml'
    expected = manifest['artifact_sha256'][historical_path]
    assert hashlib.sha256(geometry.read_bytes()).hexdigest() == expected
