"""Read-only certification of explicitly reused stage products.

Operational cache age is deliberately absent: scientific compatibility belongs
to the producing stage's contract, irrespective of when an OFF product was made.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import math
from pathlib import Path

from . import artifact_manifest
from .models import PipelineError, PipelinePaths, UV_CHANNELS, VIS_CHANNELS


def _options(config, stage, profile=None):
    values = config.get("stages", {}).get(stage, {})
    return values.get(profile, {}) if profile else values


def _edges(config, profile):
    return tuple(config["profiles"][profile]["energy_edges_gev"])


def _require_path(value, *, directory=False):
    path = Path(value)
    if not (path.is_dir() if directory else path.is_file()):
        raise ValueError(f"missing {'directory' if directory else 'file'}: {path}")
    return path


@contextmanager
def _root(path):
    import ROOT
    source = ROOT.TFile.Open(str(path), "READ")
    if not source or source.IsZombie():
        raise ValueError(f"cannot open ROOT product: {path}")
    try:
        yield source
    finally:
        source.Close()


def _production_marker(payload, config):
    if config["campaign"]["mode"] != "production":
        return
    if isinstance(payload, dict):
        if (payload.get("diagnostic_only") is True or payload.get("scope") == "diagnostic"
                or payload.get("cache_scope") == "diagnostic" or payload.get("mode") == "test_data"):
            raise ValueError("diagnostic-only product cannot be reused in production")
        for value in payload.values():
            _production_marker(value, config)
    elif isinstance(payload, list):
        for value in payload:
            _production_marker(value, config)


def _directory_markers(directory, config):
    for name in ("manifest.json", "bundle.json", "stage1_provenance.json"):
        path = directory / name
        if path.is_file():
            _production_marker(json.loads(path.read_text()), config)


def _root_markers(path, config):
    if config["campaign"]["mode"] != "production":
        return
    import uproot
    with uproot.open(path) as source:
        for key in ("sample_provenance", "preanalysis_provenance", "reconstruction_provenance",
                    "extraction_metadata"):
            if key in source:
                record = source[key]
                _production_marker(json.loads(record.member("fTitle") if record.classname == "TNamed"
                                              else str(record)), config)


def _match(key, requested, recorded):
    if isinstance(requested, (int, float)) and not isinstance(requested, bool):
        matches = (isinstance(recorded, (int, float)) and not isinstance(recorded, bool)
                   and math.isclose(requested, recorded, rel_tol=0., abs_tol=1e-12))
    else:
        matches = requested == recorded
    if not matches:
        raise ValueError(f"{key}: requested {requested!r}, recorded {recorded!r}; "
                         "enable the producer to regenerate a compatible product")


def _profile_catalog(paths):
    """Use available manual classifications without adding a common-input dependency."""
    from calibration.run_manifest import validate_manifest
    try:
        return {row.run_number: row for row in validate_manifest(paths.manifest)}
    except (OSError, ValueError):
        return {}


def _acquisition_profile(source, path, profile, catalog):
    from reconstruction.runtime.provenance import input_run_states
    states = input_run_states(source)
    record = source.Get("preanalysis_provenance")
    metadata = json.loads(record.GetTitle()) if record else {}
    embedded = metadata.get("beam_profile")
    if embedded in ("uv", "vis"):
        _match(f"{path}: beam_profile", profile, embedded)
    uncertain = not states
    for state in states:
        row = catalog.get(state["run"])
        if row is None or row.classification_source != "manual":
            uncertain = True
            continue
        _match(f"{path}: run {row.run_number} target", "P", row.target)
        _match(f"{path}: run {row.run_number} beam_type", profile.upper(), row.beam_type)
    if uncertain:
        return [f"{path}: cannot certify profile from metadata for requested {profile!r}; "
                "acquisition run provenance or manual catalog classification is unavailable; "
                "action=retain explicit external binding with this uncertainty, without inferring profile from filenames"]
    return []


def _preanalysis(directory, config, profile, paths):
    patterns = [_options(config, "selection", profile).get("pattern", f"pre_analisi_*{profile}*.root")] if profile else ["*.root"]
    files = sorted({path for pattern in patterns for path in directory.glob(pattern)})
    artifact_manifest.validate_preanalysis(files)
    if profile:
        for path in files:
            artifact_manifest.validate_root(path, "h80", (*artifact_manifest.PREANALYSIS_BRANCHES,
                                                          "protons", "pions_theta"), nonempty=False)
    if profile and _options(config, "selection", profile).get("require_current_preanalysis", False):
        artifact_manifest.validate_current_preanalysis(files)
    warnings = []
    catalog = _profile_catalog(paths) if profile else {}
    for path in files:
        _root_markers(path, config)
        if profile:
            with _root(path) as source:
                warnings.extend(_acquisition_profile(source, path, profile, catalog))
    return warnings


def _selected(directory, config, profile, paths):
    files = sorted(directory.glob("*.root"))
    if not files:
        raise ValueError(f"no selected h85 ROOT files in {directory}")
    required = (*artifact_manifest.PREANALYSIS_BRANCHES, "beam", "protons", "neutrons")
    warnings = []
    catalog = _profile_catalog(paths)
    for path in files:
        artifact_manifest.validate_root(path, "h85", required, nonempty=False)
        with _root(path) as source:
            warnings.extend(_acquisition_profile(source, path, profile, catalog))
        _root_markers(path, config)
    return warnings


def _mc(directory, config, profile):
    from graal_common.physics.channels import get_channel
    import uproot
    edges = _edges(config, profile)
    names = _options(config, "monte_carlo", profile).get("channels")
    if names is None:
        names = UV_CHANNELS if profile == "uv" else VIS_CHANNELS
        names = [name for name in names if get_channel(name).production_threshold_gev < edges[-1]]
    for name in names:
        channel = get_channel(name)
        path = _require_path(directory / channel.mc_filename)
        artifact_manifest.validate_mc(path, name)
        with uproot.open(path) as source:
            low = float(source["beam_min_gev"].member("fVal"))
            high = float(source["beam_max_gev"].member("fVal"))
        required_low = max(edges[0], channel.production_threshold_gev)
        if (not math.isfinite(low) or not math.isfinite(high) or low >= high
                or low > required_low + 1e-9 or high < edges[-1] - 1e-9):
            raise ValueError(f"{name}: generation energy domain [{low}, {high}] does not cover "
                             f"requested [{required_low}, {edges[-1]}]")
        _root_markers(path, config)


def _bdt(directory, config, profile):
    from reconstruction.runtime.stage1_gate import Stage1Gate
    from graal_common.physics.beam_profiles import get_beam_profile
    from graal_common.physics.channels import ETA_PI0_HYP
    from graal_common.stage1.features import N_FEATURES_S1, feature_names
    from graal_common.stage1.artifacts import Stage1ArtifactPaths, Stage1Provenance
    artifacts = Stage1ArtifactPaths.from_directory(directory)
    provenance = Stage1Provenance.from_json(artifacts.provenance.read_text())
    _match("bdt.feature_names", tuple(feature_names(ETA_PI0_HYP)), provenance.feature_names)
    gate = Stage1Gate.load(directory)
    edges = _edges(config, profile)
    gate.check_hypothesis(ETA_PI0_HYP)
    gate.check_profile(get_beam_profile(profile), energy_range_gev=(edges[0], edges[-1]))
    _match("bdt.signal_channel", "eta_pi0", gate.signal_channel)
    if not math.isfinite(gate.threshold) or not 0 <= gate.threshold <= 1:
        raise ValueError("invalid BDT threshold")
    _match("bdt.feature_count", N_FEATURES_S1, gate.model.get_booster().num_features())


def _reconstruction(products, config, profile):
    from reconstruction.runtime.provenance import validate_reconstruction_selection, validate_energy_domain
    from observable_extraction.io.reconstructed_events import read_run_universe
    options = _options(config, "reconstruction", profile)
    edges = _edges(config, profile)
    required = ("RunNumber", "Xstrip", "Polarization", "beam", "eta", "pi0", "proton",
                "missing", "eta_mass", "pi0_mass", "n_photons_input")
    universes = []
    warnings = []
    for branch in ("chi2", "bdt"):
        path = _require_path(products[branch])
        tree_name = f"reco_eta_pi0_{branch}"
        artifact_manifest.validate_root(path, tree_name, required, nonempty=False)
        with _root(path) as source:
            metadata = validate_reconstruction_selection(source, source.Get(tree_name))
        validate_energy_domain(metadata, profile, (edges[0], edges[-1]), requires_bdt=branch == "bdt")
        recorded_range = tuple(metadata["selection"]["energy_range_gev"])
        if recorded_range != (edges[0], edges[-1]):
            warnings.append(f"inputs.reconstruction.{profile}.{branch}.energy_range_gev: "
                            f"requested {(edges[0], edges[-1])!r}, recorded {recorded_range!r}; "
                            "compatible coverage, the consumer restricts events to the requested domain")
        _match("reconstruction.channel", "eta_pi0", metadata.get("channel"))
        for key, default in (("chi2_cut", 10.), ("missing_mass_window_gev", .06)):
            _match(f"stages.reconstruction.{profile}.{key}", options.get(key, default),
                   metadata.get("selection", {}).get(key))
        if _options(config, "extraction", profile).get("enabled", False):
            _, rows = read_run_universe(path)
            universes.append({(row["run"], row["polarization"]): row["input"] for row in rows})
        _production_marker(metadata, config)
        _root_markers(path, config)
    if universes and universes[0] != universes[1]:
        raise ValueError("chi2 and BDT inclusive run/state input counts differ")
    return warnings


def _calibration(products, config, paths):
    from calibration.calibration_qa import load_calibration_qa, sha256_file
    root = _require_path(products["root"])
    qa_path = _require_path(products["qa"])
    expected = {"manifest": sha256_file(_require_path(paths.manifest)),
                "raw_flux": sha256_file(_require_path(paths.raw_flux))}
    qa = load_calibration_qa(qa_path, root, expected_inputs=expected)
    thresholds = qa.get("diagnostics", {}).get("pre_write", {}).get("thresholds", {})
    for key in ("min_events_per_strip", "max_mad_gev", "monotonic_tolerance_gev"):
        requested = _options(config, "calibration").get(key)
        if requested is not None:
            _match(f"stages.calibration.{key}", requested, thresholds.get(key))
    _production_marker(qa, config)
    _directory_markers(root.parent, config)
    _root_markers(root, config)
    # Authenticate the historical cohort declaration without requiring archived
    # h80 files to be mounted again or replacing their historical identities.
    cohort = qa.get("inputs", {}).get("h80")
    if not isinstance(cohort, list) or not cohort:
        raise ValueError("calibration QA inclusive h80 input identities missing")
    for row in cohort:
        if (not isinstance(row, list) or len(row) != 4 or not isinstance(row[0], str)
                or not Path(row[0]).is_absolute() or type(row[1]) is not int or row[1] < 0
                or type(row[2]) is not int or not isinstance(row[3], str) or len(row[3]) != 64
                or any(char not in "0123456789abcdef" for char in row[3])):
            raise ValueError("calibration QA inclusive h80 input identities invalid")
    accepted = [row for row in qa["coverage"] if isinstance(row, dict) and row.get("accepted") is True]
    if not accepted:
        raise ValueError("calibration QA has no accepted run/state coverage")
    with _root(root) as source:
        for row in accepted:
            name = f"run{row['run_number']}_{row['state']}"
            histogram = source.Get(name)
            if (not histogram or not histogram.InheritsFrom("TH1") or histogram.GetDimension() != 1
                    or histogram.GetNbinsX() != 128):
                raise ValueError(f"calibrated flux missing valid 128-strip histogram {name}")
    # Existing cache receipts also certify scope and producer settings. No TTL
    # or implementation fingerprint comparison applies to an OFF product.
    # Campaign publication relocates QA and its receipt to metadata/common.
    for receipt_path in {root.parent / "calibration_reuse.json", qa_path.parent / "calibration_reuse.json"}:
        if not receipt_path.is_file():
            continue
        receipt = json.loads(receipt_path.read_text())
        _production_marker(receipt, config)
        signature = receipt.get("signature", {})
        for key, value in expected.items():
            _match(f"calibration.{key}", value, signature.get(key))
        for key in ("min_events_per_strip", "max_mad_gev", "monotonic_tolerance_gev", "samples_per_run_strip"):
            requested = _options(config, "calibration").get(key)
            if requested is not None:
                _match(f"stages.calibration.{key}", requested, signature.get("options", {}).get(key))


def _extraction(path, config, profile):
    from observable_extraction.io.root_input import read_output_contract, read_output_points
    from observable_extraction.core.binning import PAIR_NAMES, pair_mass_edges, phi_bin_divisor
    contract = read_output_contract(path)
    options = _options(config, "extraction", profile)
    if "candle_enabled" in options:
        _match(f"stages.extraction.{profile}.candle_enabled", options["candle_enabled"], contract.candle is not None)
    if contract.candle is not None:
        for key, recorded in (("candle_mass_half_width_gev", contract.candle.mass_half_width_gev),
                              ("candle_balance_seed", contract.candle.balance_seed)):
            if key in options:
                _match(f"stages.extraction.{profile}.{key}", options[key], recorded)
    _match("extraction.profile", profile, contract.profile)
    _match(f"profiles.{profile}.energy_edges_gev", _edges(config, profile), contract.energy_edges_gev)
    _match(f"stages.extraction.{profile}.best_binning", options.get("best_binning", False), contract.best_binning)
    if not contract.best_binning:
        _match(f"stages.extraction.{profile}.phi_bins", options.get("phi_bins", 12), len(contract.phi_edges_rad) - 1)
        _match("extraction.phi_bin_divisor", phi_bin_divisor(contract.phi_edges_rad), contract.phi_bin_divisor)
    with _root(path) as source:
        record = source.Get("provenance")
        lines = record.GetTitle().splitlines() if record else []
        estimators = [line.partition("=")[2] for line in lines if line.startswith("estimator=")]
        _match(f"stages.extraction.{profile}.estimator", [options.get("estimator", "both")], estimators)
        for pair in PAIR_NAMES:
            vector = source.Get(f"binning/{pair}_mass_edges")
            if not vector or not hasattr(vector, "GetNrows"):
                raise ValueError(f"extraction missing {pair} mass binning")
            recorded = tuple(float(vector[index]) for index in range(vector.GetNrows()))
            expected = tuple(pair_mass_edges(pair, options.get("mass_bins", 10)))
            _match(f"stages.extraction.{profile}.mass_bins ({pair})", expected, recorded)
    # The output is small (fit points, not raw events); this owner reader also
    # checks the per-point finite-bin contract for adaptive binning.
    read_output_points(path)
    _root_markers(path, config)
    # An ON producer was executed with the recorded effective configuration.
    # Only OFF reuse lacks that invocation evidence for older output contracts.
    if options.get('enabled', False):
        return []
    return [f"stages.extraction.{profile}.{key}: requested {options[key]!r}; "
            "cannot certify the recorded setting from the extraction output contract; "
            "action=retain this uncertainty when reusing the artifact, or enable extraction to regenerate"
            for key in ("by_period", "bootstrap_replicas", "bootstrap_seed") if key in options]


def validate_product(kind: str, value: Path | dict, *, profile: str | None,
                     config: dict, paths: PipelinePaths) -> list[str]:
    """Validate an external dependency using its scientific owner's contracts."""
    warnings = []
    try:
        if kind in ("preanalysis", "selected", "mc", "bdt"):
            directory = _require_path(value, directory=True)
            _directory_markers(directory, config)
            if kind == "preanalysis":
                warnings.extend(_preanalysis(directory, config, profile, paths))
            elif kind == "selected":
                warnings.extend(_selected(directory, config, profile, paths))
            elif kind == "mc":
                _mc(directory, config, profile)
            else:
                _bdt(directory, config, profile)
        elif kind == "reconstruction":
            warnings.extend(_reconstruction(value, config, profile))
        elif kind == "calibration":
            _calibration(value, config, paths)
        elif kind == "extraction":
            warnings.extend(_extraction(_require_path(value), config, profile))
        else:
            raise ValueError(f"unknown external product kind {kind!r}")
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, AttributeError, ImportError) as exc:
        raise PipelineError(f"inputs.{kind}{'.' + profile if profile else ''}: {exc}") from exc
    return warnings
