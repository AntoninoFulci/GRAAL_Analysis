"""Pin the approved explicit-energy convention independently of the legacy offset."""
import hashlib

import pytest

from mc_simulation import legacy_tables


def matrix_text():
    lines = []
    for channel in range(1, 65):
        lines.append(f'CHANNEL {channel}')
        for node in range(50):
            energy = 1.05 + .05 * node
            # Analytic linear function: midpoint interpolation has a known answer.
            values = [channel + 2 * energy + angle for angle in range(19)]
            lines.append(f'ECDM = {energy:.2f} :'.ljust(20) + ''.join(f'{v:10.3E}' for v in values[:5]))
            lines.append(''.join(f'{v:10.3E}' for v in values[5:12]))
            lines.append(''.join(f'{v:10.3E}' for v in values[12:]))
    return '\n'.join(lines) + '\n'


def test_explicit_energies_interpolate_and_ignore_last_channel(tmp_path):
    path = tmp_path / 'channel.mat'
    path.write_text(matrix_text() + 'CHANNEL 65\nignored legacy contents\n')
    table = legacy_tables.read_channel_matrix(path)
    assert table.energies_gev == pytest.approx([1.05 + .05 * i for i in range(50)])
    assert table.at_energy(1, 1.075) == pytest.approx([3.15 + i for i in range(19)])
    assert table.at_energy(64, 3.5) == pytest.approx([71 + i for i in range(19)])
    assert table.at_energy(1, 1.05)[0] == pytest.approx(3.1)
    assert table.ignored_channel == 65
    assert table.source_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize('energy', [1.0, 3.501, float('nan'), float('inf')])
def test_no_extrapolation_or_invalid_energy(tmp_path, energy):
    path = tmp_path / 'channel.mat'
    path.write_text(matrix_text())
    table = legacy_tables.read_channel_matrix(path)
    with pytest.raises(ValueError, match='energy'):
        table.at_energy(1, energy)


@pytest.mark.parametrize('channel', [0, 65, True, 1.5])
def test_only_first_64_integer_channel_ids_are_addressable(tmp_path, channel):
    path = tmp_path / 'channel.mat'
    path.write_text(matrix_text())
    with pytest.raises(ValueError, match='channel'):
        legacy_tables.read_channel_matrix(path).at_energy(channel, 1.5)


@pytest.mark.parametrize('change, message', [
    (lambda s: s.replace('CHANNEL 2\n', 'CHANNEL 1\n'), 'channel'),
    (lambda s: s.replace('ECDM = 1.10', 'ECDM = 1.05', 1), 'increasing'),
    (lambda s: s.replace('ECDM = 1.10', 'ECDM = 1.11', 1), 'grid'),
    (lambda s: s.replace(' 3.100E+00', '       nan', 1), 'finite'),
    (lambda s: s.replace(' 3.100E+00', '-3.100E+00', 1), 'negative'),
    (lambda s: '\n'.join(s.splitlines()[:-1]), 'truncated'),
    (lambda s: s + 'CHANNEL 66\n', 'trailing'),
])
def test_bad_consumed_matrix_is_rejected(tmp_path, change, message):
    path = tmp_path / 'channel.mat'
    path.write_text(change(matrix_text()))
    with pytest.raises(ValueError, match=message):
        legacy_tables.read_channel_matrix(path)


def test_table_without_ignored_channel_and_fortran_d_exponents(tmp_path):
    path = tmp_path / 'channel.mat'
    path.write_text(matrix_text().replace('E+', 'D+'))
    table = legacy_tables.read_channel_matrix(path)
    assert table.ignored_channel is None
    assert table.at_energy(1, 1.05)[0] == pytest.approx(3.1)


def test_truncation_inside_parseable_numeric_token_is_rejected(tmp_path):
    path = tmp_path / 'channel.mat'
    lines = matrix_text().splitlines()
    lines[2] = lines[2][:65]  # Final G10.3 field is still float-parseable.
    path.write_text('\n'.join(lines))
    with pytest.raises(ValueError, match='truncated'):
        legacy_tables.read_channel_matrix(path)


def test_omitted_trailing_padding_is_allowed_but_not_significant_digits(tmp_path):
    path = tmp_path / 'channel.mat'
    text = matrix_text().replace(' 3.100E+00', '  3.10    ')
    path.write_text('\n'.join(line.rstrip() for line in text.splitlines()))
    assert legacy_tables.read_channel_matrix(path).at_energy(1, 1.05)[0] == pytest.approx(3.1)


@pytest.mark.parametrize('width', [8, 9])
def test_recovered_zero_records_with_abbreviated_padding(tmp_path, width):
    path = tmp_path / 'channel.mat'
    lines = matrix_text().splitlines()
    # Recovered channel 52 uses one leading space for zero and shortened padding.
    lines[2] = lines[2][:60] + ' 0.00'.ljust(width)
    path.write_text('\n'.join(lines))
    assert legacy_tables.read_channel_matrix(path).at_energy(1, 1.05)[11] == 0
