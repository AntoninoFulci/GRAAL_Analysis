from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).parents[1]
WIKI = ROOT / 'wiki'
REPO_URL = 'https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/'
LINK = re.compile(r'(?<!!)\[[^]]+\]\(([^)]+)\)')


def _pages():
    return {p.name: p.read_text(encoding='utf-8') for p in WIKI.glob('*.md')}


def _resolve(source: Path, target: str):
    """Resolve wiki-slug and checkout links as GitHub Wiki will publish them."""
    target = unquote(target)
    if target.startswith(REPO_URL):
        path = ROOT / target[len(REPO_URL):].split('#')[0]
    elif urlsplit(target).scheme:
        return None
    else:
        clean = target.split('#', 1)[0]
        if not clean:
            path = source
        else:
            path = source.parent / clean
            if source.parent == WIKI and not path.suffix:
                path = path.with_suffix('.md')
    return path.resolve()


def test_sidebar_lists_every_public_page_once():
    pages = _pages()
    assert 'Home.md' in pages and '_Sidebar.md' in pages
    targets = [_resolve(WIKI / '_Sidebar.md', t) for t in LINK.findall(pages['_Sidebar.md'])]
    expected = {(WIKI / name).resolve() for name in pages if name != '_Sidebar.md'}
    assert set(targets) == expected
    assert all(n == 1 for n in Counter(targets).values())


def test_all_documentation_links_resolve():
    for source in [ROOT / 'README.md', *WIKI.glob('*.md')]:
        for target in LINK.findall(source.read_text()):
            resolved = _resolve(source, target)
            if resolved is not None:
                assert resolved.exists(), f'{source.name}: broken {target}'
                assert resolved.is_relative_to(ROOT.resolve()), target


def test_wiki_pages_are_substantive_and_code_fences_are_closed():
    for name, text in _pages().items():
        assert text.startswith('# '), name
        assert not re.search(r'\b(?:TODO|TBD|FIXME)\b', text), name
        assert len(re.findall(r'^```', text, re.M)) % 2 == 0, name
        assert len(text.split()) >= (20 if name == '_Sidebar.md' else 80), name


def test_wiki_does_not_offer_retired_interfaces():
    for name, text in _pages().items():
        for obsolete in ('--no-fit', '--use-fit', '--fit-cl', 'raw_bdt_fit',
                         '05-kinematic-fit', 'run_pipeline.sh', 'graal_pipeline',
                         'docs/runbooks/', 'test_data/', '08_polarization'):
            assert obsolete not in text, (name, obsolete)


def test_documented_launcher_options_match_parser():
    from graal_workflow.cli import build_parser
    text = (WIKI / 'commands-and-configuration.md').read_text()
    args = build_parser().parse_args([
        '--mode', 'production', '--output-dir', 'results/my-campaign',
        '--cpus', '4', '--extraction-workers', '2', '--seed', '42',
    ])
    assert args.cpus == 4 and args.extraction_workers == 2
    for flag in ('--phi-bins', '--best-binning', '--energy-config'):
        assert flag in text
        assert flag in build_parser()._option_string_actions
    assert build_parser().parse_args(['--mode', 'test_data']).phi_bins == 12


def test_repository_has_one_project_readme_and_current_doc_layout():
    # Deliberately enumerate source roots: environments, archives and dependency
    # checkouts have their own READMEs and are not this project's documentation.
    roots = [p for p in ROOT.iterdir() if p.is_dir() and
             (p.name[:2].isdigit() or p.name in
              {'config', 'docs', 'wiki', 'scripts', 'plots', 'graal_workflow', 'presentations', 'tests'})]
    nested = [p.relative_to(ROOT) for directory in roots for p in directory.rglob('*')
              if p.is_file() and p.name.casefold() == 'readme.md']
    assert (ROOT / 'README.md').is_file()
    assert not nested, nested
    assert {p.name for p in (ROOT / 'docs').iterdir() if not p.name.startswith('.')} == {'papers', 'plans', 'reference'}
    assert not (ROOT / '.superpowers').exists()
    assert not (ROOT / '08_observable_extraction/theory').exists()


def test_declared_scientific_sources_exist_and_match_registered_hashes():
    import hashlib
    import json
    audit = json.loads((ROOT / 'docs/reference/theory/eta_pi0_literature_audit.json').read_text())
    # Traverse the bibliography schema so a relocated source cannot quietly
    # disappear while its scientific hash remains advertised.
    def records(value):
        if isinstance(value, dict):
            if 'path' in value and 'sha256' in value:
                yield value
            for child in value.values():
                yield from records(child)
        elif isinstance(value, list):
            for child in value:
                yield from records(child)
    count = 0
    for record in records(audit):
        if not record['path'].endswith('.pdf'):
            continue
        source = ROOT / record['path']
        assert source.is_file(), source
        assert hashlib.sha256(source.read_bytes()).hexdigest() == record['sha256'], source
        count += 1
    assert count > 0


def test_reference_render_commands_keep_papers_as_inputs(tmp_path):
    """Execute documented shell paths with a cheap renderer stand-in.

    This checks mkdir/variable expansion and the actual final output argument,
    without rendering papers or executing any physics calculation.
    """
    import os
    import subprocess

    commands = []
    for directory in (ROOT / 'docs/reference/theory', ROOT / 'docs/reference/research'):
        for source in directory.glob('*.md'):
            for block in re.findall(r'```bash\n(.*?)\n```', source.read_text(), re.S):
                if 'pdftoppm ' in block:
                    commands.append((source, block))
    assert commands, 'no paper-render examples inspected'
    for index, (source, block) in enumerate(commands):
        working = tmp_path / str(index)
        (working / 'docs/papers').mkdir(parents=True)
        (working / 'scratch').mkdir()
        capture = working / 'render-outputs.txt'
        # Each block only contains digest reads, scratch setup and rendering.
        # The stub records shell-expanded output paths and requires the output
        # parent to exist, just as the real renderer does.
        stubs = '''
shasum() { :; }
pdftoppm() {
    output="${!#}"
    printf '%s\\n' "$output" >> "$RENDER_CAPTURE"
    printf 'render fixture\\n' > "${output}.png"
}
'''
        result = subprocess.run(
            ['bash', '-e', '-c', stubs + block], cwd=working,
            env={**os.environ, 'TMPDIR': str(working / 'scratch'),
                 'RENDER_CAPTURE': str(capture)},
            text=True, capture_output=True,
        )
        assert result.returncode == 0, (source, result.stderr)
        outputs = capture.read_text().splitlines()
        assert outputs
        for output in outputs:
            path = (working / output).resolve()
            assert not path.is_relative_to(working / 'docs'), (source, output)
            assert path.is_relative_to(working), (source, output)
            assert Path(str(path) + '.png').is_file()
        assert not list((working / 'docs/papers').iterdir()), source
