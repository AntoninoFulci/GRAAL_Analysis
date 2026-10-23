"""Run the complete UV/VIS eta-pi0 analysis from pre-analysis files."""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
import shutil
import sys
import textwrap

from calibration.run_manifest import validate_manifest
from graal_common.parallel import available_cpus, validate_workers
from graal_common.physics.beam_profiles import get_beam_profile
from graal_common.physics.energy_binning import EnergyBinning, load_energy_config
from graal_common.physics.channels import get_channel
from observable_extraction.core.binning import PHI_BIN_CHOICES
from . import artifact_manifest as cache
from . import logging as console
from .models import ModeConfig, PipelineError, PipelinePaths, PreflightResult, Stage, ArtifactGroup, flatten_stages, PROFILE_PATTERNS, UV_CHANNELS, VIS_CHANNELS
from .paths import mode_config, build_paths, preflight, pipeline_lock, prepare_output_dirs, validate_test_output, validate_production_output, _replace_test_output, resolve_repo_root
from .planning import build_pipeline_plan
from .execution import execute_cached_plan
from .resources import configure_resources, bounded_runner


def _use_color() -> bool:
    return console.use_color()


def _print_table(title: str, rows: Sequence[tuple[str, str]], *, warning: bool = False) -> None:
    """Render a table within the current terminal width, including long paths."""
    columns = shutil.get_terminal_size(fallback=(80, 24)).columns
    color = _use_color()
    border_code = "\x1b[2;33m" if warning else "\x1b[2;36m"
    title_code = "\x1b[1;33m" if warning else "\x1b[1;36m"
    key_code = "\x1b[33m" if warning else "\x1b[36m"

    def paint(value: str, code: str) -> str:
        return f"{code}{value}\x1b[0m" if color and code else value

    def wrapped(value: str, width: int) -> list[str]:
        return textwrap.wrap(
            value, width=width, break_on_hyphens=False,
            drop_whitespace=False, replace_whitespace=False,
        ) or [""]

    print()
    for line in wrapped(title, max(columns, 1)):
        print(paint(line, title_code))
    if columns < 8:
        for label, value in rows:
            for line in wrapped(f"{label}: {value}", max(columns, 1)):
                print(paint(line, key_code))
        return
    if columns < 56:
        cell_width = columns - 4
        top = f"╭{'─' * (columns - 2)}╮"
        middle = f"├{'─' * (columns - 2)}┤"
        bottom = f"╰{'─' * (columns - 2)}╯"
        print(paint(top, border_code))
        for index, (label, value) in enumerate(rows):
            if index:
                print(paint(middle, border_code))
            for line in wrapped(label, cell_width):
                print(f"{paint('│', border_code)} {paint(f'{line:<{cell_width}}', key_code)} {paint('│', border_code)}")
            for line in wrapped(value, cell_width):
                print(f"{paint('│', border_code)} {line:<{cell_width}} {paint('│', border_code)}")
        print(paint(bottom, border_code), flush=True)
        return

    label_width = min(max(len("Campo"), *(len(label) for label, _ in rows)), max(5, (columns - 7) // 3))
    value_width = columns - label_width - 7
    top = f"╭{'─' * (label_width + 2)}┬{'─' * (value_width + 2)}╮"
    middle = f"├{'─' * (label_width + 2)}┼{'─' * (value_width + 2)}┤"
    bottom = f"╰{'─' * (label_width + 2)}┴{'─' * (value_width + 2)}╯"

    def print_row(label: str, value: str, *, header: bool = False) -> None:
        left_lines = wrapped(label, label_width)
        right_lines = wrapped(value, value_width)
        for index in range(max(len(left_lines), len(right_lines))):
            left = left_lines[index] if index < len(left_lines) else ""
            right = right_lines[index] if index < len(right_lines) else ""
            left_code = "\x1b[1m" if header else key_code
            right_code = "\x1b[1m" if header else ("\x1b[1;33m" if warning else "")
            print(
                f"{paint('│', border_code)} {paint(f'{left:<{label_width}}', left_code)} "
                f"{paint('│', border_code)} {paint(f'{right:<{value_width}}', right_code)} "
                f"{paint('│', border_code)}"
            )

    print(paint(top, border_code))
    print_row("Campo", "Valore", header=True)
    print(paint(middle, border_code))
    for label, value in rows:
        print_row(label, value)
    print(paint(bottom, border_code), flush=True)


def print_preflight_warnings(checked: PreflightResult) -> None:
    if checked.old_preanalysis_inputs:
        _print_table(
            f"Avvisi pre-analisi ({len(checked.old_preanalysis_inputs)})",
            [(f"{index:02d} · oltre 10 giorni", str(path))
             for index, path in enumerate(checked.old_preanalysis_inputs, 1)],
            warning=True,
        )


def print_run_summary(
    config: ModeConfig,
    paths: PipelinePaths,
    args: argparse.Namespace,
    stages: Sequence[Stage | ArtifactGroup],
) -> None:
    """Show the validated campaign configuration before touching its outputs."""
    def relative(path: Path) -> str:
        return str(path.relative_to(config.repo_root))

    rows = [
        ("Modalità", config.name),
        ("Repository", str(config.repo_root)),
        ("Input h80", relative(paths.preanalysis_dir)),
        ("Risultati", relative(paths.output_root)),
        ("Flux input", relative(paths.raw_flux)),
        ("Studio flussi", getattr(args, "flux_study", "off")),
        ("Run manifest", relative(paths.manifest)),
        ("Iperparametri BDT", relative(paths.hyperparams)),
        ("Riferimento AJAKA", relative(paths.ajaka_reference)),
        ("Eventi MC/canale", str(config.mc_events)),
    ]
    for profile, channels in (("uv", UV_CHANNELS), ("vis", VIS_CHANNELS)):
        grid = load_energy_config(getattr(args, "energy_config", None)).get(
            profile, EnergyBinning(get_beam_profile(profile).energy_edges_gev))
        energy_min, energy_max = grid.energy_range_gev
        channels = tuple(name for name in channels if get_channel(name).production_threshold_gev < energy_max)
        rows.extend((
            (f"{profile.upper()} h80", ", ".join(
                path.name for path in sorted(paths.preanalysis_dir.glob(PROFILE_PATTERNS[profile]))
                if path.is_file()
            )),
            (f"{profile.upper()} energia", f"{energy_min:g}-{energy_max:g} GeV"),
            (f"{profile.upper()} canali MC", ", ".join(channels)),
            (f"{profile.upper()} selected", relative(paths.selected_dir(profile))),
            (f"{profile.upper()} MC", relative(paths.mc_dir(profile))),
            (f"{profile.upper()} BDT", relative(paths.bdt_dir(profile))),
        ))
    rows.extend((
        ("Estrazione", f"ratio + likelihood; phi bins {'best 8/12/16' if getattr(args, 'best_binning', False) else args.phi_bins}; bootstrap 0; workers {getattr(args, 'extraction_workers', 1)}"),
        ("Plot", "UV, VIS e confronto combinato"),
    ))
    if config.name == "production":
        rows.extend((
            ("Cache", "selected, MC, BDT: riuso se validi entro 10 giorni; decisione RUN/SKIP durante esecuzione"),
            ("Forzatura", ", ".join(
                f"force-{name}={'sì' if getattr(args, f'force_{name}') else 'no'}"
                for name in ("selected", "mc", "bdt")
            )),
            ("Scrittura", "intermedi persistenti in results/_cache/; risultati in nuova campagna"),
        ))
    else:
        rows.extend((
            ("Cache", "disattivata; selected, MC e BDT sempre rigenerati"),
            ("Flag force", "ignorati in test_data"),
            ("Sovrascrittura", "intermedi e risultati nella campagna results_test/"),
        ))
    commands = flatten_stages(stages)
    rows.append(("Stage previsti", str(len(commands))))
    rows.extend((f"{index:02d}", stage.name) for index, stage in enumerate(commands, 1))
    _print_table("Riepilogo pipeline", rows)


def confirm_run() -> bool:
    try:
        answer = input("Avviare la pipeline? [s/N]: ")
    except EOFError:
        return False
    return answer.strip().casefold() in {"s", "si", "sì", "y", "yes"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, help="GRAAL checkout containing native resources (required for wheel installs)")
    parser.add_argument(
        "--mode", required=True, choices=("test_data", "production")
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="empty or absent campaign output root",
    )
    parser.add_argument("--cpus", type=int, default=available_cpus(), help="total CPU budget for each active stage")
    parser.add_argument("--extraction-workers", type=lambda value: validate_workers(int(value)), default=1,
                        help="observable extraction processes (default: 1); must not exceed --cpus")
    parser.add_argument("--seed", type=int, default=42, help="reproducible MC and feature master seed")
    parser.add_argument("--color", choices=("auto", "always", "never"), default="auto",
                        help="terminal colors (default: auto); NO_COLOR disables colors in all modes")
    parser.add_argument("--preanalysis-dir", type=Path, help="explicit fresh h80 input directory")
    parser.add_argument("--require-current-preanalysis", action="store_true", help="reject h80 without tagger-discard marker and raw identities")
    parser.add_argument("--force-selected", action="store_true", help="rebuild production selection")
    parser.add_argument("--force-mc", action="store_true", help="regenerate production MC")
    parser.add_argument("--force-bdt", action="store_true", help="retrain production BDT")
    parser.add_argument("--phi-bins", type=int, choices=PHI_BIN_CHOICES, default=12,
                        help="azimuth bins for UV/VIS ratio fits (default: 12)")
    parser.add_argument("--best-binning", action="store_true",
                        help="select each ratio point from simultaneous 8/12/16 phi-bin fits")
    parser.add_argument("--energy-config", type=Path, help="JSON UV/VIS energy grids; default: historical bins")
    parser.add_argument("--flux-study", choices=("off", "audit", "study"), default="off",
                        help="optional offline missing-flux stage (default: off)")
    parser.add_argument("--flux-study-metadata", type=Path,
                        help="acquisition conditions and independent exposure JSON")
    return parser


def run(args: argparse.Namespace, *, repo_root: Path | None = None) -> int:
    if repo_root is None:
        repo_root = resolve_repo_root(getattr(args, "repo_root", None))
    config = mode_config(args.mode, repo_root)
    if getattr(args, "preanalysis_dir", None) is not None:
        config = replace(config, preanalysis_dir=args.preanalysis_dir.expanduser().resolve())
    cpus = validate_workers(getattr(args, "cpus", 1))
    extraction_workers = validate_workers(getattr(args, "extraction_workers", 1))
    if extraction_workers > cpus:
        raise PipelineError("--extraction-workers must not exceed --cpus")
    paths = build_paths(config, args.output_dir)
    flux_mode = getattr(args, "flux_study", "off")
    flux_metadata = getattr(args, "flux_study_metadata", None)
    if flux_metadata is not None:
        if flux_mode == "off":
            raise PipelineError("--flux-study-metadata requires --flux-study audit or study")
        from flux_studies.metadata import load_metadata
        try:
            load_metadata(flux_metadata, validate_manifest(paths.manifest))
        except (OSError, ValueError) as exc:
            raise PipelineError(f"invalid flux study metadata: {exc}") from exc
    if config.name == "test_data":
        validate_test_output(paths)
    else:
        validate_production_output(paths)
    with pipeline_lock(config.repo_root, mode=config.name):
        if getattr(args, "require_current_preanalysis", False):
            for pattern in PROFILE_PATTERNS.values():
                cache.validate_current_preanalysis(sorted(paths.preanalysis_dir.glob(pattern)))
        checked = preflight(config, paths)
        stages = build_pipeline_plan(config, paths, checked, phi_bins=args.phi_bins,
                                     flux_study=flux_mode, flux_study_metadata=flux_metadata,
                                     best_binning=getattr(args, "best_binning", False),
                                     energy_binnings=load_energy_config(getattr(args, "energy_config", None)))
        stages = configure_resources(stages, cpus=cpus, seed=getattr(args, "seed", 42),
                                     extraction_workers=extraction_workers)
        console.emit(f"CPU budget: {cpus}; MC/feature master seed: {getattr(args, 'seed', 42)}", "info")
        print_run_summary(config, paths, args, stages)
        print_preflight_warnings(checked)
        if not confirm_run():
            console.emit("Pipeline annullata.", "warning")
            return 0
        publication = _replace_test_output(paths) if config.name == "test_data" else nullcontext()
        with publication:
            prepare_output_dirs(paths)
            execute_cached_plan(
                stages, config, paths,
                force_selected=args.force_selected,
                force_mc=args.force_mc,
                force_bdt=args.force_bdt,
                cpus=cpus, runner=bounded_runner,
            )
    console.emit(f"\nPipeline complete: {paths.output_root}", "success")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    with console.color_mode(args.color):
        try:
            return run(args)
        except KeyboardInterrupt:
            console.emit("ERROR: pipeline interrupted", "error", stream=sys.stderr)
            return 130
        except PipelineError as exc:
            console.emit(f"ERROR: {exc}", "error", stream=sys.stderr)
            return 1
