from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import TextIO

from .config import (
    ConfigError,
    configuration_snapshot,
    load_config,
    materialize_profile_run,
    validate_profile_inputs,
)
from .model import ArtifactState, PipelinePlan
from .planner import PlanningError, PlanningPolicies, plan_target
from .registry import (
    CapabilityError,
    FINAL_STATES,
    OBSERVABLES,
    build_stage_invocation,
    capability,
    require_capability,
    target_closure,
)
from .runner import RunLockedError, run_plan
from .state import CheckpointStore, inspect_invocation_status
from .validators import validate_invocation


def _common_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--config", help="Percorso configurazione TOML")
    parser.add_argument("--profile", default="production", help="Profilo di esecuzione")
    parser.add_argument("--state-dir", help="Directory checkpoint, log e report")
    parser.add_argument("--dry-run", action="store_true", help="Pianifica senza eseguire")
    parser.add_argument("--non-interactive", action="store_true", help="Disabilita domande interattive")
    parser.add_argument("--yes", action="store_true", help="Conferma piano finale")
    parser.add_argument("--force-stage", action="append", default=[], metavar="STAGE", help="Forza rifacimento stage")
    parser.add_argument("--old-policy", choices=("ask", "rebuild", "reuse", "fail"), default="ask")
    parser.add_argument("--stale-policy", choices=("ask", "rebuild", "reuse", "fail"), default="ask")
    parser.add_argument("--untracked-policy", choices=("ask", "adopt", "rebuild", "fail"), default="ask")
    parser.add_argument("--verify", choices=("fast", "full"), help="Livello verifica artifact")
    parser.add_argument("--keep-failed-work", action="store_true", help="Conserva prodotti staged falliti")
    return parser


def build_parser() -> argparse.ArgumentParser:
    common = _common_parser()
    parser = argparse.ArgumentParser(
        prog="graal-pipeline",
        description="GRAAL pipeline orchestrator — pianificazione, checkpoint ed estrazione",
        parents=[common],
    )
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("resume", parents=[common], help="Resume latest incomplete run").set_defaults(command="resume")
    status = commands.add_parser("status", parents=[common], help="Inspect checkpoints and artifacts")
    status.add_argument("--final-state", default="eta_pi0", choices=tuple(FINAL_STATES))
    status.set_defaults(command="status")

    plan = commands.add_parser("plan", help="Build an execution plan")
    plan_operations = plan.add_subparsers(dest="operation", required=True)
    plan_extract = plan_operations.add_parser("extract", help="Plan observable extraction")
    plan_observables = plan_extract.add_subparsers(dest="observable_command", required=True)
    plan_beam = plan_observables.add_parser("beam-asymmetry", parents=[common])
    plan_beam.add_argument("--final-state", default="eta_pi0", choices=tuple(FINAL_STATES))
    plan_beam.set_defaults(command="plan", operation="extract")

    extract = commands.add_parser("extract", help="Extract a physics observable")
    extract_operations = extract.add_subparsers(dest="operation", required=True)
    beam = extract_operations.add_parser("beam-asymmetry", parents=[common])
    beam.add_argument("--final-state", default="eta_pi0", choices=tuple(FINAL_STATES))
    beam.set_defaults(command="extract", operation="beam-asymmetry")

    validate = commands.add_parser("validate", help="Validate pipeline integration")
    validate_operations = validate.add_subparsers(dest="operation", required=True)
    validate_beam = validate_operations.add_parser("beam-asymmetry", parents=[common])
    validate_beam.add_argument("--final-state", default="eta_pi0", choices=tuple(FINAL_STATES))
    validate_beam.set_defaults(command="validate", operation="beam-asymmetry")
    validate_full = validate_operations.add_parser("full", parents=[common])
    validate_full.add_argument("--final-state", default="eta_pi0", choices=tuple(FINAL_STATES))
    validate_full.set_defaults(command="validate", operation="full")
    return parser


def _write(output: TextIO, text: str = "") -> None:
    output.write(text + "\n")


def ask_state_policy(
    state: ArtifactState,
    *,
    input_fn: Callable[[str], str] = input,
    output: TextIO = sys.stdout,
) -> str:
    if state is ArtifactState.UNTRACKED:
        choices = {"1": "adopt", "2": "rebuild", "4": "fail"}
        _write(output, "Output valido senza checkpoint:")
        _write(output, "1. Validare e adottare")
        _write(output, "2. Ricostruire")
    else:
        choices = {"1": "rebuild", "2": "reuse", "4": "fail"}
        _write(output, f"Artifact {state.value}:")
        _write(output, "1. Ricostruire")
        _write(output, "2. Riutilizzare")
    _write(output, "3. Mostrare dettagli")
    _write(output, "4. Interrompere")
    while True:
        answer = input_fn("Scelta: ").strip()
        if answer == "3":
            _write(output, "La decisione sarà registrata nel report di esecuzione.")
            continue
        if answer in choices:
            return choices[answer]
        _write(output, "Scelta non valida.")


def confirm_plan(
    *,
    input_fn: Callable[[str], str] = input,
    output: TextIO = sys.stdout,
) -> bool:
    answer = input_fn("Eseguire questo piano? [s/N] ").strip().casefold()
    accepted = answer in {"s", "si", "sì", "y", "yes"}
    _write(output, "Piano confermato." if accepted else "Esecuzione annullata.")
    return accepted


def _show_main_menu(output: TextIO) -> None:
    _write(output, "GRAAL Pipeline")
    _write(output)
    entries = (
        ("1", "Continua ultima esecuzione", "Riparte dal primo checkpoint incompleto o scelto per il rifacimento."),
        ("2", "Prepara dati e modelli", "Esegue preanalisi, selezione, MC, feature e training necessari."),
        ("3", "Ricostruisci final state", "Produce campioni standard, BDT, fit e controlli sideband."),
        ("4", "Estrai osservabile", "Calcola quantità fisiche usando ricostruzione, flusso e correzioni."),
        ("5", "Valida pipeline", "Esegue profili ridotti o completi e produce un report."),
        ("6", "Controlla checkpoint e output", "Mostra validità, età, dipendenze e motivi dello stato."),
        ("7", "Esci", "Chiude senza modificare output."),
    )
    for number, label, description in entries:
        _write(output, f"{number}. {label}")
        _write(output, f"   {description}")


def _choose_final_state(input_fn: Callable[[str], str], output: TextIO) -> str | None:
    _write(output, "Stato finale")
    keys = tuple(FINAL_STATES)
    for index, key in enumerate(keys, 1):
        spec = FINAL_STATES[key]
        suffix = "" if spec.enabled else " [non disponibile]"
        _write(output, f"{index}. {spec.label}{suffix}")
        _write(output, f"   {spec.description}")
    answer = input_fn("Scelta: ").strip()
    return keys[int(answer) - 1] if answer.isdigit() and 1 <= int(answer) <= len(keys) else None


def _observable_menu(final_state: str, input_fn: Callable[[str], str], output: TextIO) -> str | None:
    keys = tuple(OBSERVABLES)
    for index, key in enumerate(keys, 1):
        spec = OBSERVABLES[key]
        selected = capability(final_state, key)
        suffix = "" if selected.enabled else " [non disponibile]"
        _write(output, f"{index}. {spec.label}{suffix}")
        _write(output, f"   {spec.description}")
        if not selected.enabled:
            _write(output, f"   {selected.disabled_reason}")
    answer = input_fn("Scelta: ").strip()
    if answer.isdigit() and 1 <= int(answer) <= len(keys):
        key = keys[int(answer) - 1]
        return key if capability(final_state, key).enabled else None
    return None


def _beam_menu(input_fn: Callable[[str], str], output: TextIO) -> None:
    while True:
        entries = (
            ("1", "Estrazione finale", "Esegue correzioni, sideband e covarianze complete."),
            ("2", "Prima passata non corretta", "Controlla rapidamente flusso e campione BDT raw."),
            ("3", "Valida estrazione", "Esegue profilo smoke o farm isolato."),
            ("4", "Configurazione avanzata", "Imposta estimatore, bootstrap, binning e seed."),
            ("5", "Stato", "Mostra checkpoint e validità degli output richiesti."),
            ("6", "Indietro", "Torna al menu principale."),
        )
        for number, label, description in entries:
            _write(output, f"{number}. {label}")
            _write(output, f"   {description}")
        answer = input_fn("Scelta (? per aiuto): ").strip()
        if answer == "?":
            _write(output, "Estrazione finale è target produzione; prima passata è diagnostica.")
        elif answer == "6":
            return
        elif answer in {"1", "2", "3", "4", "5"}:
            _write(output, "Comando disponibile nella CLI riproducibile.")
        else:
            _write(output, "Scelta non valida.")


def run_wizard(
    *,
    input_fn: Callable[[str], str] = input,
    output: TextIO = sys.stdout,
) -> int:
    while True:
        _show_main_menu(output)
        answer = input_fn("Scelta: ").strip()
        if answer == "7":
            return 0
        if answer == "4":
            final_state = _choose_final_state(input_fn, output)
            if final_state is None:
                _write(output, "Scelta non valida.")
                continue
            observable = _observable_menu(final_state, input_fn, output)
            if observable == "beam_asymmetry":
                _beam_menu(input_fn, output)
            continue
        if answer == "?":
            _write(output, "Scegli target; planner controllerà artifact e checkpoint disponibili.")
        elif answer in {"1", "2", "3", "5", "6"}:
            _write(output, "Selezione disponibile anche tramite CLI.")
        else:
            _write(output, "Scelta non valida.")


def _target_from_args(args: argparse.Namespace, state_root: Path | None = None) -> tuple[str, str, str | None]:
    final_state = getattr(args, "final_state", "eta_pi0")
    if args.command == "resume":
        if state_root is None or not (state_root / "latest.json").is_file():
            raise PlanningError("no previous run is available to resume")
        latest = json.loads((state_root / "latest.json").read_text())
        previous = json.loads((state_root / "runs" / latest["run_id"] / "plan.json").read_text())
        return previous["target"], previous.get("final_state") or "eta_pi0", previous.get("observable")
    if args.command == "status":
        return "beam_asymmetry_full", final_state, "beam_asymmetry"
    operation = getattr(args, "operation", None)
    if operation in {"extract", "beam-asymmetry"}:
        selected = require_capability(final_state, "beam_asymmetry")
        assert selected.production_target is not None
        return selected.production_target, final_state, "beam_asymmetry"
    if operation == "full":
        return "beam_asymmetry_full", final_state, "beam_asymmetry"
    raise PlanningError(f"unsupported command: {args.command}")


def _print_statuses(statuses, output: TextIO) -> None:
    for stage, status in statuses.items():
        _write(output, f"{status.state.value:<10} {stage:<30} {'; '.join(status.reasons)}")


def _print_plan(plan: PipelinePlan, output: TextIO) -> None:
    for item in plan.items:
        duration = f" ~{item.estimated_seconds:.0f}s" if item.estimated_seconds else ""
        _write(output, f"{item.action.value:<8} {item.stage_key:<30}{duration} {'; '.join(item.reasons)}")


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        return run_wizard()
    args = build_parser().parse_args(arguments)
    if args.command is None:
        build_parser().print_help()
        return 0
    try:
        config = load_config(args.config, profile=args.profile)
        if args.verify:
            config = replace(config, checkpoint=replace(config.checkpoint, verification=args.verify))
        profile_run_id = None
        if config.profile_settings.requires_real_fixture:
            validate_profile_inputs(config)
        if config.profile_settings.isolated_results:
            profile_run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            config = materialize_profile_run(config, profile_run_id)
        if args.command == "validate":
            print(f"CLAIM: {config.profile_settings.claim}")
        state_root = Path(args.state_dir).expanduser().resolve() if args.state_dir else config.paths.results_dir / ".pipeline"
        target, final_state, observable = _target_from_args(args, state_root)
        enabled_optional = frozenset({"grid_search"}) if config.runtime.use_grid_search else frozenset()
        ordered = target_closure(target, enabled_optional_dependencies=enabled_optional)
        invocations = {stage: build_stage_invocation(stage, config, final_state=final_state) for stage in ordered}
        snapshot = configuration_snapshot(config)
        store = CheckpointStore(state_root)
        statuses = {
            stage: inspect_invocation_status(
                invocation,
                checkpoint_store=store,
                configuration=snapshot,
                repository_root=config.repository_root,
                final_state=final_state,
                observable=observable,
                max_age_days=config.checkpoint.max_age_days,
                verification=config.checkpoint.verification,
                validator=validate_invocation,
            )
            for stage, invocation in invocations.items()
        }
        if args.command == "status":
            _print_statuses(statuses, sys.stdout)
            return 0
        old_policy, stale_policy, untracked_policy = args.old_policy, args.stale_policy, args.untracked_policy
        if not args.non_interactive:
            states = {status.state for status in statuses.values()}
            if old_policy == "ask" and ArtifactState.OLD in states:
                old_policy = ask_state_policy(ArtifactState.OLD)
            if stale_policy == "ask" and ArtifactState.STALE in states:
                stale_policy = ask_state_policy(ArtifactState.STALE)
            if untracked_policy == "ask" and ArtifactState.UNTRACKED in states:
                untracked_policy = ask_state_policy(ArtifactState.UNTRACKED)
        plan = plan_target(
            target,
            statuses,
            policies=PlanningPolicies(old_policy, stale_policy, untracked_policy),
            forced=set(args.force_stage),
            non_interactive=args.non_interactive,
            yes=args.yes,
            enabled_optional_dependencies=enabled_optional,
            final_state=final_state,
            observable=observable,
        )
        _print_plan(plan, sys.stdout)
        if args.command == "plan" or args.dry_run:
            return 0 if plan.executable else 2
        if not args.yes and not args.non_interactive and not confirm_plan():
            return 0
        summary = run_plan(
            plan,
            invocations,
            state_directory=state_root,
            validator=validate_invocation,
            keep_failed_work=args.keep_failed_work,
            configuration=snapshot,
            run_id=profile_run_id,
        )
        return summary.exit_code
    except (CapabilityError, ConfigError, PlanningError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except RunLockedError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 73
