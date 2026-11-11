"""Read the per-run constants consumed by PREAN for late-1998 proton data.

This validates structure and identity, not physical calibration or trigger
efficiency. BGO pedestal order is FERA readout order, not crystal copy number.
Shared databases, linearity, geometry, dead-channel maps and compile-time
options must also be reconciled before these constants define a response.
"""
import hashlib
import math
from pathlib import Path
import re


def _numbers(line):
    values = tuple(float(value.replace('D', 'E').replace('d', 'e'))
                   for value in line.split('!', 1)[0].replace(',', ' ').split())
    if not all(map(math.isfinite, values)):
        raise ValueError('Nonfinite numeric value')
    return values


def _rows(lines, widths):
    if len(lines) != len(widths):
        raise ValueError('Wrong record count')
    values = tuple(_numbers(line) for line in lines)
    if any(len(row) != width for row, width in zip(values, widths)):
        raise ValueError('Wrong numeric column count')
    return values


def _f8_3(field):
    """Preserve F8.3 implicit decimals; reject partially written fields."""
    if len(field) != 8:
        raise ValueError('Truncated F8.3 field')
    token = field.strip()
    if re.fullmatch(r'[+-]?\d+', token):
        return int(token) / 1000
    if not re.fullmatch(r'[+-]?\d*\.\d{3}', token):
        raise ValueError('Unsupported or truncated F8.3 field')
    return float(token)


def read_1998_calibration(directory: str | Path, run: int) -> dict:
    """Load six per-run files for the data09/PREAN 1186–1517 format.

    Parse only the first 480 BGO source constants and first 480 FERA pedestal
    channels, exactly as CONSTAN; later laser/readout sections remain unused.
    Strip edge records may have two extra values unused by the scalar READ.
    The original values and bytes are never rewritten.
    """
    if type(run) is not int or not 1186 <= run <= 1517:
        raise ValueError('Expected an integer run in the late-1998 range 1186–1517')
    directory = Path(directory)
    sources = []

    def read(relative):
        path = directory / relative
        payload = path.read_bytes()
        sources.append({'path': relative, 'sha256': hashlib.sha256(payload).hexdigest()})
        return payload.decode('ascii').splitlines()

    try:
        lines = read(f'calib_bgo/run{run}.cal')
        if len(lines) < 482:
            raise ValueError('Truncated BGO source constants')
        gains = []
        for i, line in enumerate(lines[2:482], start=1):
            if line[1:14].strip() != 'BGO Source =' or int(line[14:18]) != i:
                raise ValueError('BGO source channel identity mismatch')
            gains.append(_f8_3(line[21:29]))

        lines = read(f'calib_bgo/run{run}.ped')
        if len(lines) < 483:
            raise ValueError('Truncated BGO pedestals')
        pedestal = []
        for i, line in enumerate(lines[3:483]):
            if (line[1:17].strip() != 'Fera Pedestal ='
                    or (int(line[17:20]), int(line[23:26])) != divmod(i, 16)):
                raise ValueError('FERA readout channel identity mismatch')
            pedestal.append(_f8_3(line[29:37]))

        tagger = _rows(read(f'calib_tag/calib_{run}.dat'), (7,) * 9 + (2,))
        strip_lines = read(f'calib_strip/calstrip_{run}.dat')
        if len(strip_lines) != 16:
            raise ValueError('Wrong strip record count')
        strips = _rows(strip_lines[:15], (5,) * 15)
        edge = _numbers(strip_lines[15])
        if len(edge) not in (1, 3):
            raise ValueError('Missing or malformed strip edge')
        barrel = _rows(read(f'calib_barrel/calib_{run}.dat'), (2,) * 32)
        if any(lower > upper for lower, upper in barrel):
            raise ValueError('Reversed barrel TDC window')
        wall = tuple(value for line in read(f'calib_wall/calib_{run}.cal') for value in _numbers(line))
        if len(wall) != 660:
            raise ValueError('Expected 660 wall constants')
    except (OSError, ValueError, UnicodeError) as error:
        raise ValueError(f'Invalid calibration for run {run}: {error}') from error

    wall_names = ('pedestals', 'tdc_calibration', 'gain_cards', 'time_walk', 'tdc_offset', 'gain_pms')
    return {
        'run': run, 'status': 'structural_read_only', 'sources': sources,
        'bgo_source_constants': tuple(gains), 'bgo_pedestal_by_readout': tuple(pedestal),
        'tagger_windows': tagger[:9], 'tagger_timing': tagger[9],
        'strip_windows': strips, 'strip_edge': edge[0], 'strip_unused_edge_values': edge[1:],
        'barrel_tdc_windows': barrel,
        'wall': {name: wall[i * 110:(i + 1) * 110] for i, name in enumerate(wall_names)},
    }
