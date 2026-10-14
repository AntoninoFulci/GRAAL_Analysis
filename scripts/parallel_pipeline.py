"""Apply one CPU budget to existing pipeline commands."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import os
import subprocess

from graal_common.parallel import thread_environment, validate_workers


def configure_resources(stages, *, cpus: int, seed: int):
    validate_workers(cpus)
    if isinstance(seed, bool) or not isinstance(seed, int) or not 1 <= seed < 2**32:
        raise ValueError('seed must be between 1 and 2**32-1')
    result = []
    for stage in stages:
        argv = stage.argv
        kind = stage.name.split(':')[-1]
        if ':generate:' in stage.name:
            digest = hashlib.sha256(f'{seed}:{stage.name}'.encode()).digest()
            task_seed = int.from_bytes(digest[:4], 'big') or 1
            argv = (*argv[:-1], argv[-1][:-1] + f',{task_seed})')
        elif kind in ('select', 'calibrate_flux'):
            argv += ('--threads', str(cpus))
        elif kind == 'train':
            argv += ('--nthread', str(cpus))
        elif kind == 'features':
            argv += ('--workers', str(cpus), '--seed-policy', 'channel-v1', '--loss-seed', str(seed))
        elif kind in ('reconstruct_chi2', 'reconstruct_bdt', 'extract', 'flux_study', 'plots'):
            argv += ('--workers', str(cpus))
        result.append(replace(stage, argv=argv))
    return tuple(result)


def bounded_runner(argv, **kwargs):
    """Native stages opt into their explicit budget; all other pools default1."""
    return subprocess.run(argv, env={**os.environ, **thread_environment(1)}, **kwargs)
