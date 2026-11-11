#!/usr/bin/env python3
"""Recover the solid Fig.6 path without executing PostScript or extracting a tar.

Only this hash-pinned source dialect is supported. Coordinates remain in its
user space: the uniform 0.24 scale cancels in axis calibration. SVG diagnostics
redraw every source segment and overlay the selected path in red.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import tarfile

ARCHIVE_SHA256 = '703501be0948d5a68ce189fd69968c26819aa3e13c9ea80f69fcd2b438674f11'
MEMBER_SHA256 = '10180ad940497afd6dc4886b48ad4865e17faa6ce4582efb3b57b98616eebf1f'


@dataclass(frozen=True)
class VectorPath:
    start_line: int
    width: float
    vertices: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class AxisCalibration:
    anchors: tuple[tuple[float, float], tuple[float, float]]
    checks: tuple[tuple[float, float], ...]

    def __post_init__(self):
        values = [v for pair in (*self.anchors, *self.checks) for v in pair]
        if not all(math.isfinite(v) for v in values):
            raise ValueError('nonfinite calibration')
        if self.anchors[1][0] <= self.anchors[0][0] or self.anchors[1][1] <= self.anchors[0][1]:
            raise ValueError('axes must increase')
        if not self.checks:
            raise ValueError('independent calibration check required')
        if self.residual > abs(self.scale):
            raise ValueError('axis check exceeds one source coordinate unit')

    @property
    def scale(self):
        (x0,y0),(x1,y1) = self.anchors
        return (y1-y0)/(x1-x0)

    def convert(self, value):
        x0,y0 = self.anchors[0]
        return y0 + (value-x0)*self.scale

    @property
    def residual(self):
        return max(abs(self.convert(x)-y) for x,y in self.checks)


def parse_body(body: str, *, line_offset: int = 0) -> list[VectorPath]:
    """Read m/l/s/setlinewidth only. Unknown tokens and dangling operands fail."""
    paths = []
    points = []
    operands = []
    width = 2.
    start = 0

    def flush():
        if len(points) > 1:
            paths.append(VectorPath(start, width, tuple(points)))
        points.clear()

    for line_no, line in enumerate(body.splitlines(), 1 + line_offset):
        for token in line.split('%',1)[0].split():
            if re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)', token):
                value = float(token)
                if not math.isfinite(value): raise ValueError('nonfinite coordinate')
                operands.append(value)
                if len(operands) > 2: raise ValueError('too many operands')
                continue
            if token in ('m','l'):
                if len(operands) != 2: raise ValueError('coordinate pair required')
                if token == 'm':
                    flush()
                    start = line_no
                elif not points:
                    raise ValueError('lineto without moveto')
                points.append(tuple(operands))
            elif token == 's':
                if operands: raise ValueError('stroke operands')
                flush()
            elif token == 'setlinewidth':
                if len(operands) != 1 or operands[0] <= 0 or points:
                    raise ValueError('unsupported line width change')
                width = operands[0]
            else:
                raise ValueError(f'unsupported PostScript token: {token}')
            operands.clear()
    if operands: raise ValueError('dangling PostScript operands')
    if points: raise ValueError('unstroked path')
    return paths


def verify_member(content: bytes) -> None:
    if hashlib.sha256(content).hexdigest() != MEMBER_SHA256:
        raise ValueError('member hash mismatch')


def read_figure(archive_path: Path) -> str:
    # Hash before parsing; read only a regular member, no filesystem extraction.
    if archive_path.stat().st_size > 10_000_000:
        raise ValueError('archive too large')
    if hashlib.sha256(archive_path.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        raise ValueError('archive hash mismatch')
    with tarfile.open(archive_path, 'r:gz') as archive:
        members = [m for m in archive.getmembers() if m.name == 'fig6.ps']
        if len(members) != 1 or not members[0].isfile() or members[0].size > 1_000_000:
            raise ValueError('expected one bounded regular fig6.ps member')
        with archive.extractfile(members[0]) as stream:
            content = stream.read()
    verify_member(content)
    return content.decode('ascii')


def calibrate_path(path, x_axis, y_axis):
    x = [x_axis.convert(p[0]) for p in path.vertices]
    y = [y_axis.convert(p[1]) for p in path.vertices]
    if any(b <= a for a,b in zip(x,x[1:])):
        raise ValueError('curve ascissae must strictly increase')
    return x,y


def extract_ratio(archive_path: Path, output_path: Path, diagnostic_dir: Path) -> None:
    if output_path.exists(): raise FileExistsError(output_path)
    source = read_figure(archive_path)
    # Fixed prolog/footer are authenticated by verify_member; never interpreted.
    prefix, body = source.split('%%EndProlog\n',1)
    body, footer = body.split('saveobj restore',1)
    if footer.strip() != 'showpage\n%%Trailer':
        raise ValueError('unsupported footer')
    paths = parse_body(body, line_offset=prefix.count('\n')+1)
    selected = [p for p in paths if p.start_line == 700]
    if len(selected) != 1: raise ValueError('solid solution-I path not identified')
    curve = selected[0]
    if len(curve.vertices) != 80 or curve.vertices[0] != (812.,2090.) or curve.vertices[-1] != (1344.,2152.):
        raise ValueError('unexpected solution-I geometry')
    x = AxisCalibration(((812.,1.),(1351.,1.4)), ((947.,1.1),(1081.,1.2),(1216.,1.3)))
    y = AxisCalibration(((1908.,0.),(2462.,3.)), ((2093.,1.),(2277.,2.)))
    energies,rho = calibrate_path(curve,x,y)
    # Conservative envelope, not standard deviations. Axis errors correlated.
    axis_offset = .5*y.scale
    axis_scale = 1./554
    local_error = (.5 + curve.width/2)*y.scale
    rho_bound = local_error + y.residual + axis_offset + max(abs(v) for v in rho)*axis_scale
    x_bound = (.5 + curve.width/2 + .5)*x.scale + x.residual + .4/539
    data = {
        'schema_version':1, 'baseline':'Fix2010', 'solution':'I',
        'label':'Reconstruction of solution I with figure-derived helicity ratio',
        'units':{'energy_lab_gev':'GeV','rho':'dimensionless'},
        'quantity':'A_3/2 / A_1/2', 'interpolation':'piecewise_linear_no_extrapolation',
        'requested_domain_lab_gev':[1.,1.4],
        'support_lab_gev':[energies[0],energies[-1]],
        'covers_requested_domain':False,
        'endpoint_note':'Last source vertex x=1344 precedes axis edge x=1351 by 7 units; no reconciliation or extension.',
        'energy_lab_gev':energies, 'rho':rho,
        # Preserve the original derivation's provenance and byte-reproducible
        # curated product; current location is in paper-relocations-20261111.json.
        'source':{'archive':'docs/papers/Fix_2010_1004.5240v1_source.tar.gz',
                  'archive_sha256':ARCHIVE_SHA256,'member':'fig6.ps','member_sha256':MEMBER_SHA256,
                  'version':'arXiv:1004.5240v1','page':8,'figure':6,
                  'curve':'solid = solution I (caption)', 'path_start_line':700,
                  'path_end_line':779,'vertices':80},
        'axis_calibration':{
            'coordinate_space':'PostScript user coordinates before uniform 0.24 scale',
            'x_anchors':x.anchors,'x_checks':x.checks,'x_scale':x.scale,
            'y_anchors':y.anchors,'y_checks':y.checks,'y_scale':y.scale,
            'x_max_check_residual_gev':x.residual,'y_max_check_residual_rho':y.residual},
        'reading_error':{
            'interpretation':'Conservative envelopes, not statistical errors; dense vertices are not independent measurements.',
            'coordinate_quantization_half_unit':.5,'stroke_half_width_units':curve.width/2,
            'local_vertical_bound_rho':local_error,
            'axis_offset_bound_rho':axis_offset,'axis_relative_scale_bound':axis_scale,
            'calibration_residual_rho':y.residual,'vertical_envelope_rho':rho_bound,
            'horizontal_envelope_gev':x_bound,'target_vertical_0_01_met':rho_bound <= .01,
            'correlated_scenarios':'Common vertical offset +/-axis_offset_bound_rho and common scale 1+/-axis_relative_scale_bound; horizontal axis shifts also correlated. No pointwise independent-error claim.'}}
    diagnostic_dir.mkdir(parents=True,exist_ok=True)
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="730" height="840" viewBox="750 1780 620 740">',
           '<rect x="750" y="1780" width="620" height="740" fill="white"/>',
           '<g transform="translate(0 4300) scale(1 -1)" fill="none" stroke="black">']
    for path in paths:
        coords=' '.join(f'{a},{b}' for a,b in path.vertices)
        svg.append(f'<polyline points="{coords}" stroke-width="{path.width}"/>')
    coords=' '.join(f'{a},{b}' for a,b in curve.vertices)
    svg.append(f'<polyline points="{coords}" stroke="red" stroke-width="3" opacity="0.65"/>')
    svg.append('</g></svg>')
    (diagnostic_dir/'fig6-overlay.svg').write_text('\n'.join(svg)+'\n')
    with output_path.open('x') as stream:
        json.dump(data,stream,indent=2,allow_nan=False)
        stream.write('\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('diagnostic_dir',type=Path)
    args=parser.parse_args()
    extract_ratio(args.archive,args.output,args.diagnostic_dir)


if __name__ == '__main__': main()
