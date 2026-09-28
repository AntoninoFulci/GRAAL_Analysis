from __future__ import annotations

from types import MappingProxyType
from collections.abc import Mapping

from .model import FinalStateSpec, ObservableCapability, ObservableSpec, StageSpec


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
