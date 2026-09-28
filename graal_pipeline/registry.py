from __future__ import annotations

from types import MappingProxyType

from .model import FinalStateSpec, ObservableCapability, ObservableSpec


class CapabilityError(ValueError):
    """Raised when a requested final-state/observable pair cannot run."""


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
