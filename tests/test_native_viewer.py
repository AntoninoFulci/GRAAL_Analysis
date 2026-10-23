"""Exercise viewer path/command plumbing without Geant4, Qt, or transport."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

REPO = Path(__file__).resolve().parents[1]
GDML = Path('results_test/archive/geant4-migration-audit-20261023/conversion-spack-certified/geometry.gdml')


@pytest.mark.parametrize('explicit', [False, True])
def test_native_viewer_preserved_default_and_build_commands(tmp_path, explicit):
    assert (REPO / GDML).is_file()
    script = tmp_path / '03_mc_simulation/geant4/view_native.sh'
    script.parent.mkdir(parents=True)
    shutil.copyfile(REPO / '03_mc_simulation/geant4/view_native.sh', script)
    geometry = tmp_path / ('explicit geometry.gdml' if explicit else GDML)
    geometry.parent.mkdir(parents=True, exist_ok=True)
    geometry.write_text('<gdml/>')
    build = tmp_path / 'results_test/build/graal-geant4-viewer'
    (build / 'G01-build').mkdir(parents=True)
    prefix = tmp_path / 'geant4'
    (prefix / 'bin').mkdir(parents=True)
    (prefix / 'bin/geant4.sh').write_text('export VIEWER_DATA_READY=1\n')
    bin_dir = tmp_path / 'bin'; bin_dir.mkdir()
    log = tmp_path / 'commands.log'
    for executable, body in [
        (bin_dir / 'spack', 'printf "%s\\n" "$VIEWER_PREFIX"'),
        (bin_dir / 'cmake', 'printf "cmake" >> "$VIEWER_LOG"; printf " <%s>" "$@" >> "$VIEWER_LOG"; printf "\\n" >> "$VIEWER_LOG"'),
        (build / 'G01-build/load_gdml', 'printf "viewer <%s> <%s> <%s> <%s> <%s>\\n" "$PWD" "$1" "$G4FORCENUMBEROFTHREADS" "$G4UI_USE_QT" "$VIEWER_DATA_READY" >> "$VIEWER_LOG"'),
    ]:
        executable.write_text('#!/bin/bash\nset -eu\n' + body + '\n')
        executable.chmod(0o755)
    env = {**os.environ, 'PATH': str(bin_dir) + os.pathsep + os.environ['PATH'],
           'SPACK_BIN': str(bin_dir / 'spack'), 'VIEWER_PREFIX': str(prefix), 'VIEWER_LOG': str(log)}
    result = subprocess.run(['bash', str(script), *([str(geometry)] if explicit else [])],
                            env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert log.read_text().splitlines() == [
        f'cmake <-S> <{script.parent / "viewer"}> <-B> <{build}> <-DGeant4_DIR={prefix}/lib/cmake/Geant4> <-DCMAKE_BUILD_TYPE=Release>',
        f'cmake <--build> <{build}> <--target> <load_gdml> <--parallel> <4>',
        f'viewer <{build}> <{geometry}> <1> <1> <1>',
    ]
