from __future__ import annotations

from types import MappingProxyType
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

from graal_common.physics.channels import CHANNEL_NAMES, get_channel

from .config import ConfigError, PipelineConfig
from .model import (
    CheckpointScope,
    FinalStateSpec,
    ObservableCapability,
    ObservableSpec,
    StageInvocation,
    StageSpec,
)


class CapabilityError(ValueError):
    """Raised when a requested final-state/observable pair cannot run."""


class GraphError(ValueError):
    """Raised when a stage graph is incomplete or cyclic."""


FINAL_STATES = MappingProxyType(
    {
        "eta_pi0": FinalStateSpec(
            key="eta_pi0",
            label="eta pi0",
            description="Ricostruisce lo stato finale eta pi0 con selezione chi2 e BDT.",
            hypothesis="eta_pi0",
            model_dir="04_bdt_training/artifacts/stage1",
            reconstruction_target="reco_bdt_fit",
        ),
        "2pi0": FinalStateSpec(
            key="2pi0",
            label="2 pi0",
            description="Ricostruisce lo stato finale 2pi0 con selezione chi2.",
            hypothesis="2pi0",
            model_dir=None,
            reconstruction_target="reco_2pi0",
        ),
    }
)


OBSERVABLES = MappingProxyType(
    {
        "beam_asymmetry": ObservableSpec(
            key="beam_asymmetry",
            label="Asimmetria del fascio",
            description="Estrae Sigma da campioni polarizzati, flusso e sideband.",
            enabled=True,
        ),
        "cross_section": ObservableSpec(
            key="cross_section",
            label="Sezione d'urto",
            description=(
                "Estrarrà yield corretto per flusso, efficienza e accettanza."
            ),
            enabled=False,
            disabled_reason="Sezione d'urto non ancora implementata.",
        ),
    }
)


_CAPABILITIES = MappingProxyType(
    {
        ("eta_pi0", "beam_asymmetry"): ObservableCapability(
            final_state="eta_pi0",
            observable="beam_asymmetry",
            enabled=True,
            disabled_reason=None,
            production_target="beam_asymmetry_full",
            first_pass_target="beam_asymmetry_first_pass",
            validation_target="beam_asymmetry_full",
        ),
        ("eta_pi0", "cross_section"): ObservableCapability(
            final_state="eta_pi0",
            observable="cross_section",
            enabled=False,
            disabled_reason="Sezione d'urto non ancora implementata.",
        ),
        ("2pi0", "beam_asymmetry"): ObservableCapability(
            final_state="2pi0",
            observable="beam_asymmetry",
            enabled=False,
            disabled_reason="Asimmetria del fascio per 2pi0 non ancora implementata.",
        ),
        ("2pi0", "cross_section"): ObservableCapability(
            final_state="2pi0",
            observable="cross_section",
            enabled=False,
            disabled_reason="Sezione d'urto per 2pi0 non ancora implementata.",
        ),
    }
)


STAGES = MappingProxyType(
    {
        "preanalysis": StageSpec(
            "preanalysis", "Convert raw detector files to pre-analysis h80 trees."
        ),
        "event_selection": StageSpec(
            "event_selection",
            "Select analysis events and write h85 trees.",
            ("preanalysis",),
        ),
        "mc_generation": StageSpec(
            "mc_generation", "Generate Monte Carlo training channels."
        ),
        "beam_spectrum": StageSpec(
            "beam_spectrum",
            "Measure selected-data beam spectrum for MC weighting.",
            ("event_selection",),
        ),
        "feature_build": StageSpec(
            "feature_build",
            "Build Stage-1 signal and background features.",
            ("beam_spectrum", "mc_generation"),
        ),
        "grid_search": StageSpec(
            "grid_search",
            "Optimize Stage-1 BDT hyperparameters.",
            ("feature_build",),
        ),
        "bdt_training": StageSpec(
            "bdt_training",
            "Train and publish the Stage-1 BDT model bundle.",
            ("feature_build",),
            optional_dependencies=("grid_search",),
        ),
        "flux_calibration": StageSpec(
            "flux_calibration",
            "Build strip-energy and photon-flux calibration.",
            ("preanalysis",),
        ),
        "reco_chi2_raw": StageSpec(
            "reco_chi2_raw",
            "Run raw chi2 eta-pi0 reconstruction.",
            ("event_selection",),
        ),
        "reco_bdt_raw": StageSpec(
            "reco_bdt_raw",
            "Run raw eta-pi0 reconstruction with the BDT gate.",
            ("event_selection", "bdt_training"),
        ),
        "reco_bdt_fit": StageSpec(
            "reco_bdt_fit",
            "Run BDT-gated eta-pi0 reconstruction with kinematic fit.",
            ("event_selection", "bdt_training"),
        ),
        "reco_data_sideband": StageSpec(
            "reco_data_sideband",
            "Run broad eta-pi0 sideband reconstruction on data.",
            ("event_selection", "bdt_training"),
        ),
        "signal_mc_generation": StageSpec(
            "signal_mc_generation", "Generate eta-pi0 signal Monte Carlo."
        ),
        "signal_mc_adapter": StageSpec(
            "signal_mc_adapter",
            "Adapt generated signal MC to detector-like h85 input.",
            ("signal_mc_generation",),
        ),
        "reco_signal_mc_sideband": StageSpec(
            "reco_signal_mc_sideband",
            "Run broad sideband reconstruction on eta-pi0 signal MC.",
            ("signal_mc_adapter", "bdt_training"),
        ),
        "beam_asymmetry_first_pass": StageSpec(
            "beam_asymmetry_first_pass",
            "Extract an uncorrected first-pass beam asymmetry.",
            ("flux_calibration", "reco_bdt_raw"),
        ),
        "beam_asymmetry_full": StageSpec(
            "beam_asymmetry_full",
            "Extract corrected beam asymmetry with sideband products.",
            (
                "flux_calibration",
                "reco_chi2_raw",
                "reco_bdt_raw",
                "reco_bdt_fit",
                "reco_data_sideband",
                "reco_signal_mc_sideband",
            ),
        ),
        "reco_2pi0": StageSpec(
            "reco_2pi0",
            "Run basic chi2 reconstruction for the 2pi0 final state.",
            ("event_selection",),
        ),
    }
)


_STAGE_METADATA = {
    "preanalysis": (CheckpointScope.SHARED, "preanalysis", ("01_pre_analysis/PreAnalysis.C",)),
    "event_selection": (CheckpointScope.SHARED, "event_selection", ("02_event_selector/select_events.py",)),
    "mc_generation": (CheckpointScope.SHARED, "monte_carlo", ("03_mc_simulation/generators", "00_common/physics/channels.py")),
    "beam_spectrum": (CheckpointScope.SHARED, "beam_spectrum", ("04_bdt_training/beam_spectrum.py",)),
    "feature_build": (CheckpointScope.FINAL_STATE, "stage1_features", ("04_bdt_training/build_background_features.py", "00_common/stage1/features.py")),
    "grid_search": (CheckpointScope.FINAL_STATE, "grid_search", ("04_bdt_training/grid_search_stage1.py",)),
    "bdt_training": (CheckpointScope.FINAL_STATE, "stage1_model", ("04_bdt_training/train_bdt_stage1.py", "00_common/stage1/artifacts.py")),
    "flux_calibration": (CheckpointScope.SHARED, "flux_calibration", ("scripts/build_strip_energy_flux.py", "00_common/calibration/strip_energy_flux.py")),
    "reco_chi2_raw": (CheckpointScope.FINAL_STATE, "reconstruction", ("05_reconstruction/reconstruct_eta_pi0_chi2.py", "05_reconstruction/runtime/reco_core.py")),
    "reco_bdt_raw": (CheckpointScope.FINAL_STATE, "reconstruction", ("05_reconstruction/reconstruct_eta_pi0_bdt.py", "05_reconstruction/runtime/reco_core.py", "05_reconstruction/runtime/stage1_gate.py")),
    "reco_bdt_fit": (CheckpointScope.FINAL_STATE, "reconstruction", ("05_reconstruction/reconstruct_eta_pi0_bdt.py", "05_reconstruction/runtime/reco_core.py", "05_reconstruction/core/kinematic_fit.py")),
    "reco_data_sideband": (CheckpointScope.FINAL_STATE, "reconstruction", ("05_reconstruction/reconstruct_eta_pi0_bdt_sideband.py", "05_reconstruction/runtime/reco_core.py")),
    "signal_mc_generation": (CheckpointScope.FINAL_STATE, "monte_carlo", ("03_mc_simulation/generators/generate_eta_pi0_dataset.C",)),
    "signal_mc_adapter": (CheckpointScope.FINAL_STATE, "event_selection", ("05_reconstruction/prepare_signal_mc_selected.py",)),
    "reco_signal_mc_sideband": (CheckpointScope.FINAL_STATE, "reconstruction", ("05_reconstruction/reconstruct_eta_pi0_bdt_sideband.py", "05_reconstruction/runtime/reco_core.py")),
    "beam_asymmetry_first_pass": (CheckpointScope.OBSERVABLE, "beam_asymmetry", ("06_observable_extraction/beam_asymmetry.py", "06_observable_extraction/io/root_output.py")),
    "beam_asymmetry_full": (CheckpointScope.OBSERVABLE, "beam_asymmetry", ("06_observable_extraction/beam_asymmetry.py", "06_observable_extraction/io/root_output.py")),
    "reco_2pi0": (CheckpointScope.FINAL_STATE, "reconstruction", ("05_reconstruction/reconstruct_2pi0.py", "05_reconstruction/runtime/reco_core.py")),
}

STAGES = MappingProxyType(
    {
        key: replace(
            stage,
            scope=_STAGE_METADATA[key][0],
            validator=_STAGE_METADATA[key][1],
            responsible_paths=_STAGE_METADATA[key][2],
        )
        for key, stage in STAGES.items()
    }
)


def result_path(config: PipelineConfig, *parts: str) -> Path:
    root = config.paths.results_dir.resolve()
    candidate = root.joinpath(*parts).resolve()
    if not candidate.is_relative_to(root):
        raise ConfigError(f"output path escapes result root: {candidate}")
    return candidate


def pipeline_paths(config: PipelineConfig, final_state: str) -> dict[str, Path]:
    if final_state not in FINAL_STATES:
        raise CapabilityError(f"unknown final state: {final_state}")
    reconstruction = result_path(config, final_state, "reconstruction")
    observable = result_path(config, final_state, "observables", "beam_asymmetry")
    return {
        "calibration_dir": result_path(config, "shared", "strip_energy_flux"),
        "reconstruction_dir": reconstruction,
        "reco_chi2_raw": reconstruction / f"reco_{final_state}_chi2_raw.root",
        "reco_bdt_raw": reconstruction / f"reco_{final_state}_bdt_raw.root",
        "reco_bdt_fit": reconstruction / f"reco_{final_state}_bdt_fit.root",
        "reco_data_sideband": reconstruction / f"reco_{final_state}_bdt_sideband.root",
        "signal_mc_selected_dir": reconstruction / "signal_mc_selected",
        "signal_mc_selected_file": reconstruction / "signal_mc_selected/eta_pi0_mc_selected.root",
        "reco_signal_mc_sideband": reconstruction / f"reco_{final_state}_signal_mc.root",
        "beam_asymmetry_first_dir": observable / "first_pass",
        "beam_asymmetry_dir": observable,
        "reco_2pi0": reconstruction / "reco_2pi0.root",
    }


def _module_command(config: PipelineConfig, module: str, *arguments: object) -> tuple[str, ...]:
    return (
        config.runtime.python_executable,
        "-m",
        module,
        *(str(argument) for argument in arguments),
    )


def build_stage_invocation(
    stage_key: str,
    config: PipelineConfig,
    *,
    final_state: str = "eta_pi0",
) -> StageInvocation:
    if stage_key not in STAGES:
        raise GraphError(f"unknown target: {stage_key}")
    if final_state not in FINAL_STATES:
        raise CapabilityError(f"unknown final state: {final_state}")
    stage = STAGES[stage_key]
    root = config.repository_root
    paths = pipeline_paths(config, final_state)
    python = config.runtime.python_executable
    commands: tuple[tuple[str, ...], ...]
    inputs: tuple[Path, ...]
    outputs: tuple[Path, ...]
    working_directory = root

    if stage_key == "preanalysis":
        expression = (
            f'gROOT->ProcessLine(".L {root / "01_pre_analysis/PreAnalysis.C"}"); '
            f'AnalyzeAll("{config.paths.raw_dir}", "{config.paths.preanalysis_dir}", '
            f'"{root / "01_pre_analysis/cuts"}");'
        )
        commands = ((config.runtime.root_executable, "-l", "-b", "-q", "-e", expression),)
        inputs, outputs = (config.paths.raw_dir,), (config.paths.preanalysis_dir,)
    elif stage_key == "event_selection":
        commands = ((python, "-u", "-m", "event_selector.select_events", "--input-dir", str(config.paths.preanalysis_dir), "--output-dir", str(config.paths.selected_dir), "--threads", str(config.runtime.threads)),)
        inputs, outputs = (config.paths.preanalysis_dir,), (config.paths.selected_dir,)
    elif stage_key == "mc_generation":
        commands = tuple(
            (
                config.runtime.root_executable,
                "-l",
                "-b",
                "-q",
                str(root / f"03_mc_simulation/generators/generate_{channel}_dataset.C")
                + f"({config.runtime.mc_events})",
            )
            for channel in CHANNEL_NAMES
        )
        working_directory = config.paths.mc_data_dir
        inputs = tuple(root / f"03_mc_simulation/generators/generate_{channel}_dataset.C" for channel in CHANNEL_NAMES)
        outputs = tuple(config.paths.mc_data_dir / get_channel(channel).mc_filename for channel in CHANNEL_NAMES)
    elif stage_key == "beam_spectrum":
        commands = ((python, "-u", "-m", "bdt_training.beam_spectrum", "--selected-dir", str(config.paths.selected_dir), "--tree", config.runtime.input_tree, "--output", str(config.paths.beam_spectrum_file)),)
        inputs, outputs = (config.paths.selected_dir,), (config.paths.beam_spectrum_file,)
    elif stage_key == "feature_build":
        commands = ((python, "-u", "-m", "bdt_training.build_background_features", "--mc-dir", str(config.paths.mc_data_dir), "--signal-channel", config.runtime.signal_channel, "--signal-prior", str(config.runtime.signal_prior), "--beam-spectrum", str(config.paths.beam_spectrum_file), "--output", str(config.paths.features_file)),)
        inputs = (config.paths.mc_data_dir, config.paths.beam_spectrum_file)
        outputs = (config.paths.features_file,)
    elif stage_key == "grid_search":
        commands = (_module_command(config, "bdt_training.grid_search_stage1", "--features", config.paths.features_file, "--out-dir", config.paths.model_dir, "--n-iter", config.runtime.grid_search_iterations),)
        inputs = (config.paths.features_file,)
        outputs = (config.paths.model_dir / "best_hyperparams.json", config.paths.model_dir / "grid_search_results.csv")
    elif stage_key == "bdt_training":
        arguments: list[object] = ["--features", config.paths.features_file, "--out-dir", config.paths.model_dir]
        if config.runtime.use_grid_search:
            arguments.extend(("--hyperparams", config.paths.model_dir / "best_hyperparams.json"))
        commands = (_module_command(config, "bdt_training.train_bdt_stage1", *arguments),)
        inputs = (config.paths.features_file,)
        if config.runtime.use_grid_search:
            inputs += (config.paths.model_dir / "best_hyperparams.json",)
        outputs = tuple(config.paths.model_dir / name for name in ("bdt_stage1.json", "stage1_threshold.txt", "stage1_provenance.json", "stage1_metrics.txt"))
    elif stage_key == "flux_calibration":
        commands = ((python, str(root / "scripts/build_strip_energy_flux.py"), "--preanalysis-dir", str(config.paths.preanalysis_dir), "--manifest", str(config.paths.run_manifest), "--flux", str(config.paths.external_flux), "--output-dir", str(paths["calibration_dir"]), "--progress-every-events", str(config.runtime.flux_progress_every_events), "--samples-per-run-strip", str(config.runtime.flux_samples_per_run_strip), "--threads", str(config.runtime.threads)),)
        inputs = (config.paths.preanalysis_dir, config.paths.run_manifest, config.paths.external_flux)
        outputs = (paths["calibration_dir"],)
    elif stage_key in {"reco_chi2_raw", "reco_bdt_raw", "reco_bdt_fit"}:
        module = "reconstruction.reconstruct_eta_pi0_chi2" if stage_key == "reco_chi2_raw" else "reconstruction.reconstruct_eta_pi0_bdt"
        output = paths[stage_key]
        arguments = ["--input-dir", config.paths.selected_dir, "--input-tree", config.runtime.input_tree, "--partner", config.runtime.partner]
        if stage_key != "reco_bdt_fit":
            arguments.append("--no-fit")
        arguments.extend(("--output-file", output))
        if stage_key != "reco_chi2_raw":
            arguments.extend(("--model-dir", config.paths.model_dir))
        commands = (_module_command(config, module, *arguments),)
        inputs = (config.paths.selected_dir,) + (() if stage_key == "reco_chi2_raw" else (config.paths.model_dir,))
        outputs = (output,)
    elif stage_key == "reco_data_sideband":
        commands = (_module_command(config, "reconstruction.reconstruct_eta_pi0_bdt_sideband", "--input-dir", config.paths.selected_dir, "--input-tree", config.runtime.input_tree, "--partner", config.runtime.partner, "--output-file", paths["reco_data_sideband"], "--model-dir", config.paths.model_dir),)
        inputs, outputs = (config.paths.selected_dir, config.paths.model_dir), (paths["reco_data_sideband"],)
    elif stage_key == "signal_mc_generation":
        signal = config.paths.mc_data_dir / "eta_pi0_mc.root"
        commands = ((config.runtime.root_executable, "-l", "-b", "-q", str(root / "03_mc_simulation/generators/generate_eta_pi0_dataset.C") + f"({config.runtime.mc_events})"),)
        working_directory = config.paths.mc_data_dir
        inputs, outputs = (root / "03_mc_simulation/generators/generate_eta_pi0_dataset.C",), (signal,)
    elif stage_key == "signal_mc_adapter":
        signal = config.paths.mc_data_dir / "eta_pi0_mc.root"
        commands = (_module_command(config, "reconstruction.prepare_signal_mc_selected", "--input-file", signal, "--output-dir", paths["signal_mc_selected_dir"], "--threads", config.runtime.threads),)
        inputs, outputs = (signal,), (paths["signal_mc_selected_file"],)
    elif stage_key == "reco_signal_mc_sideband":
        commands = (_module_command(config, "reconstruction.reconstruct_eta_pi0_bdt_sideband", "--input-dir", paths["signal_mc_selected_dir"], "--output-file", paths["reco_signal_mc_sideband"], "--model-dir", config.paths.model_dir),)
        inputs, outputs = (paths["signal_mc_selected_dir"], config.paths.model_dir), (paths["reco_signal_mc_sideband"],)
    elif stage_key == "beam_asymmetry_first_pass":
        commands = (_module_command(config, "observable_extraction.beam_asymmetry", "--raw-bdt", paths["reco_bdt_raw"], "--calibration-dir", paths["calibration_dir"], "--output-dir", paths["beam_asymmetry_first_dir"]),)
        inputs, outputs = (paths["reco_bdt_raw"], paths["calibration_dir"]), (paths["beam_asymmetry_first_dir"],)
    elif stage_key == "beam_asymmetry_full":
        commands = (_module_command(config, "observable_extraction.beam_asymmetry", "--raw", paths["reco_chi2_raw"], "--raw-bdt", paths["reco_bdt_raw"], "--raw-bdt-fit", paths["reco_bdt_fit"], "--sideband", paths["reco_data_sideband"], "--signal-mc", paths["reco_signal_mc_sideband"], "--calibration-dir", paths["calibration_dir"], "--output-dir", paths["beam_asymmetry_dir"], "--estimator", config.runtime.estimator, "--bootstrap-replicas", config.runtime.bootstrap_replicas, "--bootstrap-seed", config.runtime.bootstrap_seed),)
        inputs = tuple(paths[name] for name in ("reco_chi2_raw", "reco_bdt_raw", "reco_bdt_fit", "reco_data_sideband", "reco_signal_mc_sideband", "calibration_dir"))
        outputs = (paths["beam_asymmetry_dir"],)
    elif stage_key == "reco_2pi0":
        commands = (_module_command(config, "reconstruction.reconstruct_2pi0", "--input-dir", config.paths.selected_dir, "--input-tree", config.runtime.input_tree, "--partner", config.runtime.partner, "--output-file", paths["reco_2pi0"]),)
        inputs, outputs = (config.paths.selected_dir,), (paths["reco_2pi0"],)
    else:
        raise GraphError(f"stage has no command builder: {stage_key}")

    return StageInvocation(
        stage_key=stage_key,
        commands=commands,
        working_directory=working_directory,
        inputs=inputs,
        outputs=outputs,
        output_argument=(
            config.paths.model_dir
            if stage_key in {"grid_search", "bdt_training"}
            else config.paths.mc_data_dir
            if stage_key in {"mc_generation", "signal_mc_generation"}
            else paths["signal_mc_selected_dir"]
            if stage_key == "signal_mc_adapter"
            else outputs[0]
        ),
        output_kind=(
            "directory"
            if stage_key
            in {
                "preanalysis",
                "event_selection",
                "mc_generation",
                "grid_search",
                "bdt_training",
                "flux_calibration",
                "signal_mc_generation",
                "signal_mc_adapter",
                "beam_asymmetry_first_pass",
                "beam_asymmetry_full",
            }
            else "file"
        ),
        scope=stage.scope,
        validator=stage.validator or "unknown",
        responsible_paths=stage.responsible_paths,
    )


def validate_stage_graph(stages: Mapping[str, StageSpec]) -> None:
    for key, stage in stages.items():
        for dependency in (*stage.dependencies, *stage.optional_dependencies):
            if dependency not in stages:
                raise GraphError(f"stage {key} has unknown dependency {dependency}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(key: str) -> None:
        if key in visiting:
            raise GraphError(f"dependency cycle contains {key}")
        if key in visited:
            return
        visiting.add(key)
        stage = stages[key]
        for dependency in (*stage.dependencies, *stage.optional_dependencies):
            visit(dependency)
        visiting.remove(key)
        visited.add(key)

    for key in stages:
        visit(key)


def target_closure(
    target: str,
    *,
    enabled_optional_dependencies: frozenset[str] = frozenset(),
    stages: Mapping[str, StageSpec] = STAGES,
) -> tuple[str, ...]:
    if target not in stages:
        raise GraphError(f"unknown target: {target}")
    validate_stage_graph(stages)
    ordered: list[str] = []
    visited: set[str] = set()

    def visit(key: str) -> None:
        if key in visited:
            return
        stage = stages[key]
        dependencies = list(stage.dependencies)
        dependencies.extend(
            dependency
            for dependency in stage.optional_dependencies
            if dependency in enabled_optional_dependencies
        )
        for dependency in dependencies:
            visit(dependency)
        visited.add(key)
        ordered.append(key)

    visit(target)
    return tuple(ordered)


def capability(final_state: str, observable: str) -> ObservableCapability:
    if final_state not in FINAL_STATES:
        raise CapabilityError(f"unknown final state: {final_state}")
    if observable not in OBSERVABLES:
        raise CapabilityError(f"unknown observable: {observable}")
    return _CAPABILITIES[(final_state, observable)]


def require_capability(final_state: str, observable: str) -> ObservableCapability:
    selected = capability(final_state, observable)
    if not selected.enabled:
        raise CapabilityError(
            f"{final_state} / {observable} is disabled: {selected.disabled_reason}"
        )
    return selected
