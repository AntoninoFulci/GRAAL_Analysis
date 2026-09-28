from __future__ import annotations

import pytest


def test_production_graph_is_acyclic_and_dependencies_exist():
    from graal_pipeline.registry import STAGES, validate_stage_graph

    validate_stage_graph(STAGES)


def test_graph_rejects_unknown_dependency():
    from graal_pipeline.model import StageSpec
    from graal_pipeline.registry import GraphError, validate_stage_graph

    stages = {"consumer": StageSpec("consumer", "Consumer", ("missing",))}

    with pytest.raises(GraphError, match="unknown dependency missing"):
        validate_stage_graph(stages)


def test_graph_rejects_dependency_cycle():
    from graal_pipeline.model import StageSpec
    from graal_pipeline.registry import GraphError, validate_stage_graph

    stages = {
        "a": StageSpec("a", "A", ("b",)),
        "b": StageSpec("b", "B", ("a",)),
    }

    with pytest.raises(GraphError, match="dependency cycle"):
        validate_stage_graph(stages)


def test_full_asymmetry_closure_has_deterministic_dependency_order():
    from graal_pipeline.registry import target_closure

    ordered = target_closure("beam_asymmetry_full")

    assert ordered[-1] == "beam_asymmetry_full"
    assert ordered.index("preanalysis") < ordered.index("event_selection")
    assert ordered.index("event_selection") < ordered.index("reco_bdt_fit")
    assert ordered.index("signal_mc_generation") < ordered.index("signal_mc_adapter")
    assert ordered.index("signal_mc_adapter") < ordered.index("reco_signal_mc_sideband")
    assert ordered.index("flux_calibration") < ordered.index("beam_asymmetry_full")
    assert ordered == target_closure("beam_asymmetry_full")


def test_first_pass_excludes_independent_signal_mc_and_sideband_branches():
    from graal_pipeline.registry import target_closure

    closure = target_closure("beam_asymmetry_first_pass")

    assert "flux_calibration" in closure
    assert "reco_bdt_raw" in closure
    assert "reco_chi2_raw" not in closure
    assert "reco_data_sideband" not in closure
    assert "signal_mc_generation" not in closure
    assert "reco_signal_mc_sideband" not in closure


def test_grid_search_is_only_traversed_when_enabled():
    from graal_pipeline.registry import target_closure

    direct = target_closure("bdt_training")
    optimized = target_closure(
        "bdt_training", enabled_optional_dependencies=frozenset({"grid_search"})
    )

    assert "grid_search" not in direct
    assert "grid_search" in optimized
    assert optimized.index("grid_search") < optimized.index("bdt_training")


def test_unknown_target_is_rejected():
    from graal_pipeline.registry import GraphError, target_closure

    with pytest.raises(GraphError, match="unknown target"):
        target_closure("magic_result")
