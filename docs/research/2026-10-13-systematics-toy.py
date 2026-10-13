"""Reproducible software diagnostic; Gaussian run model, not detector coverage.

Run from the installed repository: python3 docs/research/2026-10-13-systematics-toy.py
No input data or campaign outputs are modified. JSON is printed to stdout.
"""
from dataclasses import fields
import json

import numpy as np

from observable_extraction.core.models import FluxExposure
from observable_extraction.core.systematics import paired_bootstrap_by_run
from observable_extraction.io.reconstructed_events import EventArrays


def ensemble(values, replicas, seed):
    runs = np.arange(1, len(values) + 1)
    arrays = {field.name: np.zeros(len(runs)) for field in fields(EventArrays)}
    arrays.update(run_number=runs, beam_energy_gev=np.asarray(values))
    events = EventArrays(**arrays)
    exposures = {(int(run), 1): FluxExposure(int(run), 1, 1.15, 1., 1., 0., .6, .6)
                 for run in runs}
    return paired_bootstrap_by_run(
        lambda samples, _: [samples['a'].beam_energy_gev.mean(), samples['b'].beam_energy_gev.mean()],
        {'a': events, 'b': events}, exposures,
        run_strata={int(run): 'toy:one_period' for run in runs},
        point_keys=('a', 'same_events_b'), replicas=replicas, seed=seed)


def main():
    sigma, run_sd, run_count = .3, .1, 20
    rng = np.random.default_rng(20261013)
    values = rng.normal(sigma, run_sd, run_count)
    # Conditional run empirical distribution: exact variance of mean of n draws.
    target = float(values.var(ddof=0) / run_count)
    stability = []
    for replicas in (100, 500, 2000):
        for seed in (8, 19, 44):
            result = ensemble(values, replicas, seed)
            stability.append(dict(replicas=replicas, seed=seed,
                                  variance=float(result.covariance[0, 0]),
                                  mc_se=float(result.covariance_standard_error[0, 0]),
                                  relative_error=float(result.covariance[0, 0] / target - 1),
                                  rank=result.rank, effective_runs=result.effective_runs,
                                  max_paired_difference=float(np.max(np.abs(result.replicas[:, 0] - result.replicas[:, 1])))))
    covered, errors = 0, []
    trials = 120
    for trial in range(trials):
        sample = rng.normal(sigma, run_sd, run_count)
        result = ensemble(sample, 200, trial + 1000)
        error = float(sample.mean() - sigma)
        errors.append(error)
        covered += bool(abs(error) <= np.sqrt(result.covariance[0, 0]))
    print(json.dumps(dict(
        model='20 independent Gaussian run means; true Sigma=0.3, run SD=0.1; equal fixed exposures',
        seed=20261013, exact_conditional_variance=target, stability=stability,
        coverage=dict(trials=trials, replicas_per_trial=200, covered=covered,
                      fraction=covered/trials, binomial_se=float(np.sqrt((covered/trials)*(1-covered/trials)/trials)),
                      mean_bias=float(np.mean(errors)), bias_mc_se=float(np.std(errors, ddof=1)/np.sqrt(trials))),
        limitation='Software toy only; no detector bias, Poisson/event bootstrap, production replica count or physical correlation model certified',
    ), indent=2))


if __name__ == '__main__':
    main()
