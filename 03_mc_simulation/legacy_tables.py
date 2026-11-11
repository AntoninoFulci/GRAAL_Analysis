"""Read recovered LAGGEN angular tables; no automatic production normalization.

Use explicit ECDM labels in GeV, as approved for the new reader. The historical
generator's implicit offset is deliberately not reproduced. Channel IDs remain
legacy IDs: mapping to modern reactions, units and branching needs source audit.
"""
from bisect import bisect_left
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import re


@dataclass(frozen=True)
class ChannelMatrix:
    energies_gev: tuple[float, ...]
    values: tuple[tuple[tuple[float, ...], ...], ...]
    source_sha256: str
    ignored_channel: int | None

    def at_energy(self, channel: int, energy_gev: float) -> tuple[float, ...]:
        """Interpolate 19 angular ordinates at W; refuse extrapolation."""
        if type(channel) is not int or not 1 <= channel <= 64:
            raise ValueError('channel must be an integer from 1 to 64')
        if (not math.isfinite(energy_gev)
                or not self.energies_gev[0] <= energy_gev <= self.energies_gev[-1]):
            raise ValueError('energy must be finite and inside the tabulated W range')
        upper = bisect_left(self.energies_gev, energy_gev)
        rows = self.values[channel - 1]
        if self.energies_gev[upper] == energy_gev:
            return rows[upper]
        lower = upper - 1
        weight = ((energy_gev - self.energies_gev[lower]) /
                  (self.energies_gev[upper] - self.energies_gev[lower]))
        return tuple(a + weight * (b - a) for a, b in zip(rows[lower], rows[upper]))


def read_channel_matrix(path: str | Path) -> ChannelMatrix:
    """Read 64 × 50 × 19 values and ignore only an optional final channel 65.

    The hash covers the exact bytes parsed, including the ignored block. Original
    files are never changed. All channels must share the explicit energy grid.
    """
    payload = Path(path).read_bytes()
    lines = payload.decode('ascii').splitlines()
    required = 64 * (1 + 50 * 3)
    if len(lines) < required:
        raise ValueError('truncated channel matrix')
    channels, grid = [], None
    for channel in range(1, 65):
        start = (channel - 1) * 151
        header = re.fullmatch(r'CHANNEL\s+(\d+)\s*', lines[start])
        if not header or int(header[1]) != channel:
            raise ValueError(f'Expected channel {channel} at line {start + 1}')
        energies, rows = [], []
        for node in range(50):
            index = start + 1 + 3 * node
            label = re.fullmatch(r'ECDM\s*=\s*(\d+(?:\.\d+)?)\s*:?\s*', lines[index][:20])
            if not label:
                raise ValueError(f'Missing energy label at line {index + 1}')
            energy = float(label[1])
            if not math.isfinite(energy) or energy <= 0 or (energies and energy <= energies[-1]):
                raise ValueError('energy grid must be finite, positive and strictly increasing')
            energies.append(energy)
            values = []
            for offset, skip, count in ((0, 20, 5), (1, 0, 7), (2, 0, 7)):
                line = lines[index + offset]
                if line[skip + 10 * count:].strip():
                    raise ValueError(f'Unexpected numeric columns at line {index + offset + 1}')
                for column in range(count):
                    field = line[skip + column * 10:skip + (column + 1) * 10]
                    try:
                        value = float(field.replace('D', 'E').replace('d', 'e'))
                    except ValueError as error:
                        raise ValueError(f'Invalid or truncated numeric field at line {index + offset + 1}') from error
                    if not math.isfinite(value):
                        raise ValueError('Matrix values must be finite')
                    if value < 0:
                        raise ValueError('Matrix contains negative values')
                    # Recovered G10.3 records carry at least three significant
                    # digits. Permit omitted trailing spaces, not clipped digits
                    # or a partially written exponent that float() would accept.
                    token = field.strip().upper().replace('D', 'E')
                    # Fixed G10.3 output has a six-column numeric region. Some
                    # recovered zero fields end earlier within that region;
                    # accept their padding while still checking precision below.
                    if len(field) < 10 and (len(field) < 6 or field[6:].strip()
                                            or 'E' in token):
                        raise ValueError('truncated G10.3 numeric record')
                    if not re.fullmatch(r'\+?\d*\.\d*(?:E[+-]\d{2,3})?', token):
                        raise ValueError('Unsupported or truncated G10.3 numeric field')
                    mantissa = token.split('E')[0].replace('.', '').lstrip('+')
                    significant = mantissa.lstrip('0') or mantissa
                    if len(significant) < 3:
                        raise ValueError('truncated G10.3 precision')
                    values.append(value)
            rows.append(tuple(values))
        if grid is not None and tuple(energies) != grid:
            raise ValueError('Channels have inconsistent energy grids')
        grid = tuple(energies)
        channels.append(tuple(rows))
    tail = [line for line in lines[required:] if line.strip()]
    ignored = None
    if tail:
        if not re.fullmatch(r'CHANNEL\s+65\s*', tail[0]) or any(
                line.lstrip().startswith('CHANNEL') for line in tail[1:]):
            raise ValueError('Unexpected trailing content; only final channel 65 may be ignored')
        ignored = 65
    return ChannelMatrix(grid, tuple(channels), hashlib.sha256(payload).hexdigest(), ignored)
