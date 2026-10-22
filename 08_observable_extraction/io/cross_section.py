"""Explicit calibration contracts and ROOT publication for cross sections."""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
from array import array
from pathlib import Path

import numpy as np
import ROOT
from calibration.run_manifest import validate_manifest
from graal_common.io.filesystem import atomic_output_directory
from graal_common.physics.beam_profiles import get_beam_profile
from mc_simulation.response import response_probabilities
from observable_extraction.calibration.flux_v2 import load_exposures
from observable_extraction.core.cross_section import (
    checked_edges,
    cross_section_basis,
    design_shift,
    differential_transform,
    fit_cross_sections,
    response_uncertainty,
)
from observable_extraction.core.kinematics import project_all_pairs
from observable_extraction.core.systematics import validate_covariance
from observable_extraction.io.reconstructed_events import (
    read_reconstructed,
    read_run_universe,
    select_sigma_events,
)
from reconstruction.runtime.provenance import file_identities, validate_energy_domain


def read_json(path):
    def invalid_constant(value):
        raise ValueError(f"nonfinite JSON constant {value} in {path}")

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key {key!r} in {path}")
            result[key] = value
        return result

    return json.loads(
        Path(path).read_text(),
        parse_constant=invalid_constant,
        object_pairs_hook=unique_object,
    )


def canonical_hash(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, allow_nan=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


def selection_signature(metadata):
    """Identify selection/code/models, excluding event input identity and host paths."""
    if metadata.get("do_fit") is not False or not metadata.get("selection"):
        raise ValueError("response selection requires no-fit reconstruction provenance")
    signature = {
        name: metadata.get(name)
        for name in ("do_fit", "selection", "beam_profile", "bdt_domain")
    }
    for field in ("source_files", "model_inputs"):
        entries = metadata.get(field, [])
        if field == "source_files" and not entries:
            raise ValueError("selection source_files missing")
        signature[field] = []
        for entry in entries:
            digest = entry["sha256"]
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)
            ):
                raise ValueError("invalid selection input digest")
            parts = Path(entry["path"]).parts
            start = next(
                (
                    i
                    for i, p in enumerate(parts)
                    if p in ("00_common", "05_reconstruction")
                ),
                len(parts) - 1,
            )
            signature[field].append(("/".join(parts[start:]), digest))
        signature[field].sort()
    if (
        metadata["selection"].get("bdt_threshold") is not None
        and not signature["model_inputs"]
    ):
        raise ValueError("BDT selection model_inputs missing")
    return canonical_hash(signature)


def reconstruction_metadata(path):
    source = ROOT.TFile.Open(str(path), "READ")
    if not source or source.IsZombie():
        raise ValueError(f"cannot open reconstruction {path}")
    try:
        record = source.Get("reconstruction_provenance")
        if not record:
            raise ValueError("reconstruction provenance missing")
        return json.loads(record.GetTitle())
    finally:
        source.Close()


def validate_grid(grid):
    energy = checked_edges(grid["energy_edges_gev"], "energy")
    phi = checked_edges(grid["phi_edges_rad"], "phi")
    observable = grid["observable"]
    if observable not in ("total", "p_pi0", "p_eta", "eta_pi0"):
        raise ValueError("unsupported cross-section observable")
    mass = (
        None
        if grid.get("mass_edges_gev") is None
        else checked_edges(grid["mass_edges_gev"], "mass")
    )
    if (observable == "total") != (mass is None):
        raise ValueError(
            "total requires no mass grid; differential observable requires mass edges"
        )
    if energy[0] <= 0 or (mass is not None and mass[0] <= 0):
        raise ValueError("energy/mass edges must be positive")
    cross_section_basis([1], [0.5], phi, 1)  # common coverage validation
    return energy, phi, mass


def cell_indices(energy, phi, mass, grid):
    """Flatten E, mass (if present), phi. -1 is outside; final edge inclusive."""
    e, p, m = validate_grid(grid)
    coordinates, edges = [np.asarray(energy), np.asarray(phi)], [e, p]
    if m is not None:
        coordinates.insert(1, np.asarray(mass))
        edges.insert(1, m)
    shape = coordinates[0].shape
    if len(shape) != 1 or any(
        x.shape != shape or not np.all(np.isfinite(x)) for x in coordinates
    ):
        raise ValueError("nonfinite or mismatched event coordinates")
    output = np.zeros(shape, dtype=np.int64)
    valid = np.ones(shape, dtype=bool)
    for x, edge in zip(coordinates, edges):
        index = np.searchsorted(edge, x, side="right") - 1
        index[x == edge[-1]] = len(edge) - 2
        valid &= (index >= 0) & (index < len(edge) - 1)
        output = output * (len(edge) - 1) + index
    return np.where(valid, output, -1)


def _number(value, name, *, positive=False, upper=None):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not np.isfinite(value)
    ):
        raise ValueError(f"{name} must be a finite number, not an unknown calibration")
    if value < 0 or (positive and value <= 0) or (upper is not None and value > upper):
        raise ValueError(f"{name} outside allowed range")
    return float(value)


def _source(record, name):
    if not isinstance(record.get("source"), str) or not record["source"].strip():
        raise ValueError(f"{name} source is required")


def _background(record, raw, signature, root, paths, *, allow_shared_covariance=False):
    if record.get("mode") == "none_diagnostic":
        if not record.get("reason"):
            raise ValueError("no-background diagnostic requires reason")
        return raw, np.diag(np.maximum(raw, 1.0)), "background_not_corrected"
    if record.get("mode") != "net_yields":
        raise ValueError(
            "background mode must be net_yields or explicit none_diagnostic"
        )
    path = (root / record["path"]).resolve()
    paths.add(path)
    data = read_json(path)
    if (
        data.get("schema_version") != 1
        or data.get("observation_signature") != signature
    ):
        raise ValueError("background observation signature mismatch")
    _source(data, "background")
    if data.get("joint_covariance") and not allow_shared_covariance:
        raise ValueError(
            "shared background fit requires joint covariance for multiple samples"
        )
    if not np.array_equal(data["observed_counts"], raw):
        raise ValueError("background observed counts differ from selected sample")
    net = np.asarray(data["net_yields"], dtype=float)
    if net.shape != raw.shape or not np.all(np.isfinite(net)):
        raise ValueError("invalid background net_yields")
    # Supplied full covariance must include count/background correlations.
    warning = f"background_status:{data['status']}" if data.get("status") else None
    return net, validate_covariance(data["covariance"], size=len(raw)), warning


def joint_yield_covariance(spec, signatures, marginals, root, paths):
    """Restore shared mass-fit covariance in the exact observation order."""
    path = (root / spec["path"]).resolve()
    data = read_json(path)
    _source(data, "joint background")
    if (
        data.get("schema_version") != 1
        or data.get("observation_signatures") != signatures
    ):
        raise ValueError("joint background observation signature/order mismatch")
    sizes = [len(c) for c in marginals]
    if data.get("row_counts") != sizes:
        raise ValueError("joint background row counts mismatch")
    archive = (path.parent / data["covariance_npz"]).resolve()
    with np.load(archive, allow_pickle=False) as arrays:
        diagonal = np.asarray(arrays["diagonal"], dtype=float)
        factors = np.asarray(arrays["factors"], dtype=float)
        kernel = np.asarray(arrays["kernel"], dtype=float)
    n = sum(sizes)
    if (
        diagonal.shape != (n,)
        or factors.ndim != 2
        or factors.shape[0] != n
        or kernel.shape != (factors.shape[1], factors.shape[1])
    ):
        raise ValueError("joint background covariance factor dimensions mismatch")
    if any(not np.all(np.isfinite(a)) for a in (diagonal, factors, kernel)):
        raise ValueError("joint background covariance factors must be finite")
    if not np.allclose(kernel, kernel.T, rtol=1e-10, atol=1e-12):
        raise ValueError("joint background covariance kernel must be symmetric")
    # Influence-function kernels can be indefinite; the full covariance must be PSD.
    covariance = validate_covariance(np.diag(diagonal) + factors @ kernel @ factors.T)
    offset = 0
    for size, marginal in zip(sizes, marginals):
        block = covariance[offset : offset + size, offset : offset + size]
        tolerance = 1e-12 + 1e-10 * np.max(np.abs(marginal), initial=0.0)
        if not np.allclose(block, marginal, rtol=1e-9, atol=tolerance):
            raise ValueError("joint background covariance disagrees with marginal")
        offset += size
    paths.update((path, archive))
    return covariance


def load_reference(path, grid, *, nominal_energies=None):
    """Load digitized points; nominal Fig.3 overlays do not assert matching windows."""
    path = Path(path).resolve()
    meta = read_json(path)
    differential = grid["observable"] != "total"
    if differential and nominal_energies is None:
        raise ValueError(
            "differential comparison requires documented energy windows or explicit nominal energy overlay"
        )
    required = {
        "schema_version": 1,
        "energy_units": "GeV",
        "observable": "invariant_mass" if differential else "total",
        "units": "ub/MeV" if differential else "ub",
        "figure": 3 if differential else 2,
        "energy_bins": "nominal_centers_only" if differential else "centers_only",
        "errors": meta.get("errors")
        if differential
        else "published_total_including_systematics",
    }
    if differential:
        if meta.get("errors") not in ("not_published", "not_resolvable_in_figure"):
            raise ValueError("Fig3 error convention must declare unavailable errors")
        required["mass_units"] = "GeV"
    if any(meta.get(k) != v for k, v in required.items()):
        raise ValueError("reference observable/figure/units/error convention mismatch")
    for name in ("source", "label", "extraction"):
        if not isinstance(meta.get(name), str) or not meta[name].strip():
            raise ValueError(f"reference {name} required")
    uncertainty = (
        "digitization_uncertainty_ub_per_mev"
        if differential
        else "digitization_uncertainty_ub"
    )
    if differential and uncertainty not in meta:
        by_energy = meta.get(uncertainty + "_by_energy", {})
        if not by_energy:
            raise ValueError("digitization uncertainty missing")
        for value in by_energy.values():
            _number(value, uncertainty)
    else:
        _number(meta.get(uncertainty), uncertainty)
    data = (path.parent / meta["data"]).resolve()
    columns = (
        [
            "panel",
            "row",
            "pair",
            "energy_gev",
            "mass_gev",
            "dsigma_ub_per_mev",
            "error_ub_per_mev",
        ]
        if differential
        else ["energy_gev", "sigma_ub", "error_ub"]
    )
    error_column = columns[-1]
    rows = []
    with data.open(newline="") as stream:
        reader = csv.DictReader(stream)
        optional = (
            {"error_available", "point_index", "center_inside_frame"}
            if differential
            else {"error_available", "error_low_ub", "error_high_ub"}
        )
        if (
            not reader.fieldnames
            or len(set(reader.fieldnames)) != len(reader.fieldnames)
            or not set(columns) <= set(reader.fieldnames)
            or set(reader.fieldnames) - set(columns) - optional
        ):
            raise ValueError("reference columns do not match declared observable")
        for row in reader:
            if set(row) != set(reader.fieldnames) or any(
                v is None for v in row.values()
            ):
                raise ValueError("malformed reference row")
            available = row.get("error_available", "true").lower()
            if available not in ("true", "false") or (available == "false") != (
                row[error_column] == ""
            ):
                raise ValueError("reference error availability disagrees with value")
            parsed = {}
            for key in columns:
                if key in ("panel", "row", "pair"):
                    parsed[key] = row[key]
                elif key == error_column and available == "false":
                    parsed[key] = None
                elif key == "dsigma_ub_per_mev":
                    value = float(row[key])
                    if not np.isfinite(value):
                        raise ValueError("nonfinite differential reference value")
                    parsed[key] = value
                else:
                    parsed[key] = _number(
                        float(row[key]), key, positive=key in ("energy_gev", "mass_gev")
                    )
            parsed["error_available"] = available == "true"
            if differential:
                if parsed["pair"] not in ("p_pi0", "p_eta", "eta_pi0"):
                    raise ValueError("unknown reference mass pair")
                if parsed["pair"] != grid["observable"]:
                    continue
            rows.append(parsed)
    if not rows:
        raise ValueError("reference points must be nonempty")
    extra = {}
    if differential:
        nominal = np.asarray(nominal_energies, dtype=float)
        ne = len(grid["energy_edges_gev"]) - 1
        if (
            nominal.shape != (ne,)
            or not np.all(np.isfinite(nominal))
            or np.any(np.diff(nominal) <= 0)
        ):
            raise ValueError(
                "one increasing nominal reference energy required per analysis bin"
            )
        for value in nominal:
            points = [
                x for x in rows if np.isclose(x["energy_gev"], value, rtol=0, atol=1e-8)
            ]
            if not points or any(
                y["mass_gev"] <= x["mass_gev"] for x, y in itertools.pairwise(points)
            ):
                raise ValueError(
                    "nominal reference energy missing or mass points unordered"
                )
        rows = [
            x
            for x in rows
            if np.any(np.isclose(x["energy_gev"], nominal, rtol=0, atol=1e-8))
        ]
        extra = {
            "nominal_energies_gev": nominal.tolist(),
            "analysis_energy_edges_gev": grid["energy_edges_gev"],
            "comparison": "nominal_energy_overlay; published integration windows unknown",
        }
    elif any(y["energy_gev"] <= x["energy_gev"] for x, y in itertools.pairwise(rows)):
        raise ValueError("reference energies must be nonempty and strictly increasing")
    return {
        **{key: [row[key] for row in rows] for key in columns + ["error_available"]},
        **extra,
        "metadata": meta,
        "inputs": file_identities([path, data]),
    }


def prepare_analysis(config_path, *, observations_only=False):
    path = Path(config_path).resolve()
    root = path.parent
    config = read_json(path)
    if config.get("schema_version") != 1 or not config.get("samples"):
        raise ValueError("analysis requires schema_version=1 and nonempty samples")
    grid = config["grid"]
    energy, phi, mass = validate_grid(grid)
    reference = (
        load_reference(
            root / config["reference"],
            grid,
            nominal_energies=config.get("reference_nominal_energies_gev"),
        )
        if config.get("reference") and not observations_only
        else None
    )
    ne, np_, nm = len(energy) - 1, len(phi) - 1, 1 if mass is None else len(mass) - 1
    nparameters, ncells = ne * nm, ne * nm * np_
    kind = config.get("analysis_kind", "experimental")
    if kind not in ("experimental", "synthetic_closure"):
        raise ValueError("invalid analysis_kind")
    if not observations_only:
        branching = config["branching"]
        _source(branching, "branching")
        br = _number(branching["value"], "branching.value", positive=True, upper=1)
        if (
            len(config["samples"]) > 1
            and any(
                x.get("background", {}).get("mode") == "net_yields"
                for x in config["samples"]
            )
            and config.get("background_cross_sample_covariance") != "independent"
            and not config.get("joint_background")
        ):
            raise ValueError(
                "multiple samples require explicit independent background_cross_sample_covariance; shared controls need joint covariance"
            )
    manifest = (root / config["run_manifest"]).resolve()
    flux_path = (root / config["flux_file"]).resolve()
    records = {r.run_number: r for r in validate_manifest(manifest)}
    paths = {path, manifest, flux_path}
    audit = {
        "status": "conditional",
        "analysis_kind": kind,
        "flux_assumption": "already_absolute_and_corrected_user_2026-10-21",
        "flux_binning": "calibrated strip mean energies, no fractional splitting",
        "estimator": "Gaussian GLS; empty raw-count variance 1 only in no-background diagnostic",
        "samples": [],
        "missing_uncertainties": [],
        "limitations": [
            "response conditional on production model within cells",
            "target/run association supplied externally",
            "first-order uncertainties; no low-count coverage claim",
        ],
    }
    missing = {
        "production_model",
        "energy_calibration_and_binning",
        "polarization_scale",
    }
    blocks = []
    used = set()
    responses = {}
    responses_by_id = {}
    scale_shifts = {}
    for sample in config["samples"]:
        reco = (root / sample["reconstructed"]).resolve()
        paths.add(reco)
        metadata = reconstruction_metadata(reco)
        signature = selection_signature(metadata)
        profile = get_beam_profile(sample["profile"])
        # Every sample must cover the requested grid. UV/VIS can be combined
        # only on a common supported energy interval, not across missing bins.
        validate_energy_domain(
            metadata,
            profile.name,
            (energy[0], energy[-1]),
            requires_bdt=metadata["selection"].get("bdt_threshold") is not None,
        )
        universe, _ = read_run_universe(reco)
        if universe - set(records):
            raise ValueError(
                "inclusive reconstruction runs absent from canonical manifest"
            )
        runs = {
            run for run in universe if records[run].source_period == sample["period"]
        }
        if not runs:
            raise ValueError("selected period absent from inclusive run universe")
        if any(
            records[run].target != "P" or records[run].beam_type != profile.beam_type
            for run in runs
        ):
            raise ValueError("period target/beam conflicts with sample profile")
        if used & runs:
            raise ValueError("overlapping run universes between samples")
        used |= runs
        flux_audit = {}
        exposures = load_exposures(
            flux_path,
            manifest_path=manifest,
            run_numbers=runs,
            target="P",
            beam_type=profile.beam_type,
            polarization_model=profile.polarization,
            energy_range=(energy[0], energy[-1]),
            audit=flux_audit,
        )
        events = read_reconstructed(
            reco, sample["tree"], vector_mode="raw", require_no_fit=True
        )
        if set(map(int, events.run_number)) - universe:
            raise ValueError("reconstructed event outside inclusive run universe")
        period_events = events.take(np.isin(events.run_number, sorted(runs)))
        event_audit = {}
        selected = select_sigma_events(
            period_events,
            exposures,
            energy_range=(energy[0], energy[-1]),
            drop_missing=True,
            audit=event_audit,
        )
        pair = "eta_pi0" if grid["observable"] == "total" else grid["observable"]
        masses, angles = project_all_pairs(selected.proton, selected.eta, selected.pi0)[
            pair
        ]
        cell = cell_indices(selected.beam_energy_gev, angles, masses, grid)
        raw = np.concatenate(
            [
                np.bincount(
                    cell[(cell >= 0) & (selected.polarization == s)], minlength=ncells
                )
                for s in (1, 2)
            ]
        ).astype(float)
        accepted_runs = sorted({key[0] for key in exposures})
        observation_signature = canonical_hash(
            {
                "reconstruction": file_identities([reco])[0]["sha256"],
                "selection": signature,
                "grid": grid,
                "runs": accepted_runs,
                "states": [1, 2],
                "flux": file_identities([flux_path])[0]["sha256"],
            }
        )
        sample_audit = {
            "period": sample["period"],
            "profile": profile.name,
            "runs": accepted_runs,
            "zero_yield_runs": sorted(
                set(accepted_runs)
                - set(map(int, selected.run_number))
                - {row["run"] for row in event_audit["missing_exposure_strata"]}
            ),
            "event_selection": event_audit,
            "raw_counts": raw.tolist(),
            "observation_signature": observation_signature,
            "selection_signature": signature,
            "flux_audit": flux_audit,
            "inclusive_runs": sorted(runs),
            "selected_events": len(selected),
            "outside_grid_events": int(np.count_nonzero(cell < 0)),
        }
        audit["samples"].append(sample_audit)
        if observations_only:
            continue
        target = sample["target"]
        _source(target, "target")
        density = _number(
            target["areal_density_cm2"], "target.areal_density_cm2", positive=True
        )
        response_path = (root / sample["response"]).resolve()
        paths.add(response_path)
        response_data = read_json(response_path)
        if (
            response_data.get("schema_version") != 1
            or response_data.get("grid") != grid
        ):
            raise ValueError("response grid/schema mismatch")
        if response_data.get("selection_signature") != signature:
            raise ValueError("response selection signature mismatch")
        provenance = response_data["provenance"]
        required = ("simulator", "geometry", "validation")
        if any(
            not isinstance(provenance.get(k), str) or not provenance[k].strip()
            for k in required
        ):
            raise ValueError(
                "response simulator/geometry/validation provenance missing"
            )
        if (
            provenance.get("independent_of_training") is not True
            or provenance.get("generated_complete") is not True
        ):
            raise ValueError(
                "response requires independent MC and complete generated denominator"
            )
        if provenance.get("migration_domain") != "closed":
            raise ValueError(
                "response must account for migration into/out of the fitted domain"
            )
        if (
            provenance["simulator"] == "synthetic_closure"
            and kind != "synthetic_closure"
        ):
            raise ValueError("synthetic response cannot calibrate experimental data")
        if provenance["simulator"] not in ("GEANT3", "synthetic_closure"):
            raise ValueError("response must be GEANT3, not generator-only smearing")
        decays = provenance.get("decays")
        if decays not in ("forced_gamma_gamma", "inclusive"):
            raise ValueError("response decay convention missing")
        effective_br = br if decays == "forced_gamma_gamma" else 1.0
        r, mc_cov = response_probabilities(
            response_data["generated"], response_data["selected"]
        )
        if r.shape != (ncells, ncells):
            raise ValueError("response count dimensions differ from grid")
        sample_id = response_data.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id.strip():
            raise ValueError("MC sample_id missing")
        response_hash = canonical_hash(response_data)
        if sample_id in responses_by_id and responses_by_id[sample_id] != response_hash:
            raise ValueError(
                "same MC sample_id has different response; joint covariance required"
            )
        responses_by_id[sample_id] = response_hash
        responses[sample_id] = (r, mc_cov, response_data)
        net, ycov, bg_warning = _background(
            sample["background"],
            raw,
            observation_signature,
            root,
            paths,
            allow_shared_covariance=len(config["samples"]) == 1
            or bool(config.get("joint_background")),
        )
        if bg_warning:
            audit["limitations"].append(bg_warning)
        sample_audit["response"] = provenance
        bases = []
        flux_counts = []
        for state in (1, 2):
            photons = np.zeros(ne)
            polarized = np.zeros(ne)
            for exposure in exposures.values():
                index = int(
                    np.searchsorted(energy, exposure.energy_gev, side="right") - 1
                )
                if exposure.energy_gev == energy[-1]:
                    index = ne - 1
                if not 0 <= index < ne:
                    continue
                count = (
                    exposure.flux_vertical if state == 1 else exposure.flux_horizontal
                )
                pol = (
                    exposure.polarization_vertical
                    if state == 1
                    else exposure.polarization_horizontal
                )
                photons[index] += count
                polarized[index] += count * pol
            pol = np.divide(polarized, photons, out=np.zeros(ne), where=photons > 0)
            bases.append(
                cross_section_basis(
                    np.repeat(photons * density * 1e-30 * effective_br, nm),
                    np.repeat(pol, nm),
                    phi,
                    state,
                )
            )
            flux_counts.append(photons.tolist())
        sample_audit["photons_by_state_energy"] = flux_counts
        block = {
            "a": np.vstack([r @ b for b in bases]),
            "bases": bases,
            "raw": raw,
            "y": net,
            "cov": ycov,
            "sample_id": sample_id,
            "normalization": [],
        }
        for prefix, record in [("target", target), ("flux", sample["flux_scale"])]:
            _source(record, prefix)
            group = record.get("correlation_group")
            if not isinstance(group, str) or not group.strip():
                raise ValueError(f"{prefix} correlation_group required")
            name = f"{prefix}:{group}"
            error = record.get("relative_uncertainty")
            if error is None:
                missing.add(name)
            else:
                block["normalization"].append((name, _number(error, name)))
        if decays == "forced_gamma_gamma":
            error = branching.get("relative_uncertainty")
            if error is None:
                missing.add("branching")
            else:
                block["normalization"].append(
                    ("branching", _number(error, "branching uncertainty"))
                )
        blocks.append(block)
    if observations_only:
        audit.update(
            status="observations_only", inputs=file_identities(paths), grid=grid
        )
        return {"audit": audit, "grid": grid}
    design = np.vstack([b["a"] for b in blocks])
    yields = np.concatenate([b["y"] for b in blocks])
    yield_cov = np.zeros((len(yields), len(yields)))
    response_blocks = {key: [] for key in responses}
    offset = 0
    for b in blocks:
        n = len(b["y"])
        rows = slice(offset, offset + n)
        yield_cov[rows, rows] = b["cov"]
        for state_index, basis in enumerate(b["bases"]):
            response_blocks[b["sample_id"]].append(
                (
                    slice(
                        offset + state_index * ncells,
                        offset + (state_index + 1) * ncells,
                    ),
                    basis,
                )
            )
        for name, relative in b["normalization"]:
            scale_shifts.setdefault(name, np.zeros_like(design))[rows] += (
                b["a"] * relative
            )
        offset += n
    if config.get("joint_background"):
        if config.get("background_cross_sample_covariance") == "independent":
            raise ValueError(
                "joint background conflicts with independent covariance declaration"
            )
        yield_cov = joint_yield_covariance(
            config["joint_background"],
            [s["observation_signature"] for s in audit["samples"]],
            [b["cov"] for b in blocks],
            root,
            paths,
        )
    fit = fit_cross_sections(yields, yield_cov, design)
    components = {"signal_yield": fit.covariance}
    for key, (_, mc_cov, _) in responses.items():
        components[f"mc:{key}"] = response_uncertainty(
            fit, mc_cov, response_blocks[key]
        )
    for name, da in scale_shifts.items():
        delta = design_shift(fit, da)
        components[name] = np.outer(delta, delta)
    transform = (
        np.eye(nparameters) if mass is None else differential_transform(ne, mass)
    )
    values = transform @ fit.coefficients[:nparameters]
    projected = {
        name: validate_covariance(
            transform @ c[:nparameters, :nparameters] @ transform.T
        )
        for name, c in components.items()
    }
    audit["missing_uncertainties"] = sorted(missing)
    audit["reference"] = reference
    audit["reference_comparison"] = (
        "visual overlay only; no rescaling or independence assumption"
        if reference
        else "not supplied; Ajaka numerical comparison pending"
    )
    audit.update(
        chi2=fit.chi2,
        dof=fit.dof,
        condition_number=fit.condition,
        inputs=file_identities(paths),
        grid=grid,
        config=config,
        uncertainty="known components only; missing components are not zero",
        background_cross_sample_covariance=(
            "joint shared-fit covariance"
            if config.get("joint_background")
            else "single sample or explicitly independent backgrounds"
        ),
    )
    return {
        "reference": reference,
        "values": values,
        "components": projected,
        "known_covariance": sum(projected.values()),
        "fit": fit,
        "audit": audit,
        "grid": grid,
        "raw_counts": np.concatenate([b["raw"] for b in blocks]),
        "net_yields": yields,
        "yield_covariance": yield_cov,
        "design": design,
        "responses": responses,
    }


def write_result(result, output_dir):
    from observable_extraction.plotting.cross_section import plot_cross_sections

    with atomic_output_directory(Path(output_dir), overwrite=False) as staging:
        f = ROOT.TFile(str(staging / "cross_sections.root"), "RECREATE")
        if not f or f.IsZombie():
            raise RuntimeError("cannot create cross_sections.root")
        try:
            energy, _, mass = validate_grid(result["grid"])
            nm = 1 if mass is None else len(mass) - 1
            tree = ROOT.TTree(
                "cross_section_points", "Conditional cross sections; see provenance"
            )
            columns = {
                name: array("d", [0])
                for name in (
                    "energy_low_gev",
                    "energy_high_gev",
                    "mass_low_gev",
                    "mass_high_gev",
                    "value",
                    "known_error",
                )
            }
            for name, value in columns.items():
                tree.Branch(name, value, f"{name}/D")
            for i, value in enumerate(result["values"]):
                e, m = divmod(i, nm)
                row = [
                    energy[e],
                    energy[e + 1],
                    0 if mass is None else mass[m],
                    0 if mass is None else mass[m + 1],
                    value,
                    np.sqrt(result["known_covariance"][i, i]),
                ]
                for column, item in zip(columns.values(), row):
                    column[0] = float(item)
                tree.Fill()
            tree.Write()

            def matrix(directory, name, values):
                directory.cd()
                a = np.asarray(values)
                obj = ROOT.TMatrixD(*a.shape)
                for i in range(len(a)):
                    for j in range(a.shape[1]):
                        obj[i][j] = float(a[i, j])
                obj.Write(name)

            cov = f.mkdir("covariance")
            matrix(cov, "known_total", result["known_covariance"])
            component_names = {}
            for i, (name, values) in enumerate(result["components"].items()):
                key = f"component_{i}"
                matrix(cov, key, values)
                component_names[key] = name
            f.cd()
            ROOT.TNamed("covariance_components", json.dumps(component_names)).Write()
            ROOT.TNamed(
                "provenance",
                json.dumps(result["audit"], sort_keys=True, allow_nan=False),
            ).Write()
            ROOT.TNamed("units", "ub" if mass is None else "ub/MeV").Write()
            inputs = f.mkdir("inference_inputs")
            for name in ("raw_counts", "net_yields", "yield_covariance", "design"):
                a = np.asarray(result[name])
                matrix(inputs, name, a[:, None] if a.ndim == 1 else a)
            matrix(inputs, "parameters", result["fit"].coefficients[:, None])
            response_dir = f.mkdir("responses")
            for i, (key, (r, _, data)) in enumerate(result["responses"].items()):
                sub = response_dir.mkdir(f"response_{i}")
                matrix(sub, "probability", r)
                matrix(sub, "generated", np.array(data["generated"])[:, None])
                matrix(sub, "selected", data["selected"])
                sub.cd()
                ROOT.TNamed("metadata", json.dumps(data, sort_keys=True)).Write()
        finally:
            f.Close()
        plot_cross_sections(
            result, staging / "cross_sections.pdf", reference=result.get("reference")
        )
