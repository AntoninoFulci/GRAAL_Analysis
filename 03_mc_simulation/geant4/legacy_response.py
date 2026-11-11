"""Strict, source-backed configuration for the diagnostic GRAAL_09 response.

This is the simulation ADC/direct-TDC convention. Data gains, pedestals, CBAR,
nonlinearity and timing windows are never applied to simulated deposits here.
It does not qualify the frozen GRAAL_26 detector as a 1998 detector.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

from mc_simulation.legacy_calibration import read_1998_calibration


# One-based source records in data/base/data09.base, read with FORMAT(F15.3).
SCALAR_RECORDS = {
    "scbgo": 2, "vscbgo_GeV": 3, "thres_GeV": 4,
    "scdeb": 40, "vscdeb_GeV": 41, "debdis": 42, "dthres_GeV": 43,
    "zc3_cm": 83, "sdetof": 152, "vdetof_s": 153, "ddetof_s": 154,
}
SCALAR_KEYS = (*SCALAR_RECORDS, "dlight_cm_s", "dedxat", "historical_run")
_REAL = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?")


def _f15_3(line):
    """F15.3: a mantissa without a point has implied /1000, even with exponent."""
    if len(line) < 15:
        raise ValueError("Truncated F15.3 field")
    token = line[:15].strip()
    if not _REAL.fullmatch(token):
        raise ValueError("Malformed F15.3 field")
    value = float(token.replace("D", "E").replace("d", "e"))
    if "." not in token:
        value /= 1000
    if not math.isfinite(value):
        raise ValueError("Nonfinite F15.3 field")
    return value


def _i5(line):
    if len(line) < 5:
        raise ValueError("Truncated I5 field")
    token = line[:5].strip()
    if not re.fullmatch(r"[+-]?\d+", token):
        raise ValueError("Malformed I5 field")
    return int(token)


def _channel(channel, maximum, detector):
    if type(channel) is not int or not 1 <= channel <= maximum:
        raise ValueError(f"{detector} channel must be an integer in 1..{maximum}")
    return channel - 1


def bgo_electronics(channel):
    """Crystal copy 1..480 -> LAGCRI theta/phi and DETECTB FERA address."""
    index = _channel(channel, 480, "BGO")
    return dict(theta_index=index//32+1, phi_index=index%32+1,
                fera_vsn=index//16, fera_sub=index%16)


def barrel_electronics(channel):
    """Bar 1..32 -> physical copy 101..132 and DETECTB ADC/TDC addresses."""
    index = _channel(channel, 32, "Barrel")
    return dict(physical_copy=channel+100, tdc_vsn=31+index//16,
                adc_vsn=34+index//16, fera_sub=index%16)


def _validate_scalars(values):
    for key in ("scbgo", "scdeb", "sdetof"):
        value = values[key]
        if not 0 < value <= 2**31-1 or not value.is_integer():
            raise ValueError(f"Invalid integral channel scale: {key}")
    for key in ("vscbgo_GeV", "vscdeb_GeV", "vdetof_s", "zc3_cm", "dlight_cm_s"):
        if not math.isfinite(values[key]) or values[key] <= 0:
            raise ValueError(f"Invalid positive response scale: {key}")
    for key in ("debdis", "ddetof_s"):
        if values[key] < 0:
            raise ValueError(f"Negative resolution: {key}")
    for threshold, full_scale in (("thres_GeV", "vscbgo_GeV"), ("dthres_GeV", "vscdeb_GeV")):
        if not 0 <= values[threshold] < values[full_scale]:
            raise ValueError(f"Threshold outside response scale: {threshold}")
    if values["dedxat"] != 1:
        raise ValueError("Only source-backed DEDXAT=1 is supported")


def _attenuation_rows(lines, zc3):
    result = []
    for channel, line in enumerate(lines[45:77], start=1):
        tokens = line.split("!", 1)[0].replace(",", " ").split()
        if len(tokens) != 4 or not all(_REAL.fullmatch(token) for token in tokens):
            raise ValueError(f"Malformed attenuation row {channel}")
        row = [float(token.replace("D", "E").replace("d", "e")) for token in tokens]
        if not all(map(math.isfinite, row)) or row[0] <= 0 or row[2] < 0:
            raise ValueError(f"Invalid attenuation parameters for bar {channel}")
        if row[0] > 1:
            raise ValueError(f"Unsupported attenuation X1>1 correction for bar {channel}")
        # Nonnegative amplitudes avoid cancellation; endpoint checks bound each
        # exponential and their sum everywhere inside [-ZC3, ZC3]. The positive
        # denominator is the +ZC3 endpoint in the legacy GRAAL_09 ratio.
        try:
            endpoints = []
            for position in (-zc3, zc3):
                response = row[0]*math.exp(row[1]*position) + row[2]*math.exp(row[3]*position)
                if not math.isfinite(response) or response <= 0:
                    raise ValueError(f"Unsafe attenuation denominator/domain for bar {channel}")
                endpoints.append(response)
            if not math.isfinite(endpoints[0]/endpoints[1]) or endpoints[0]/endpoints[1] <= 0:
                raise ValueError(f"Unsafe attenuation ratio for bar {channel}")
        except OverflowError as error:
            raise ValueError(f"Overflowing attenuation parameters for bar {channel}") from error
        result.append(row)
    return result


def read_legacy09_response(data_directory, historical_run):
    """Read data09 and six control families without calibrating simulation hits.

    Historical run selection is explicit and independent of the transport event
    run counter. Sources are paths relative to ``data_directory`` plus hashes of
    the exact inspected bytes; only the database is applied by the response.
    """
    if type(historical_run) is not int or historical_run not in (1321, 1324):
        raise ValueError("Historical run must be integer 1321 or 1324")
    directory = Path(data_directory)
    try:
        payload = (directory / "base/data09.base").read_bytes()
        lines = payload.decode("ascii").splitlines()
        if len(lines) < 155:
            raise ValueError("Truncated data09 database")
        scalars = {key: _f15_3(lines[number-1]) for key, number in SCALAR_RECORDS.items()}
        divisor = _f15_3(lines[154])
        if divisor <= 0:
            raise ValueError("Invalid light-speed divisor")
        scalars.update(dedxat=_i5(lines[44]), dlight_cm_s=3.0e10/divisor)
        _validate_scalars(scalars)
        attenuation = _attenuation_rows(lines, scalars["zc3_cm"])
        calibration = read_1998_calibration(directory, historical_run)
        if any(not math.isfinite(gain) or gain <= 0 for gain in calibration["bgo_source_constants"]):
            raise ValueError("BGO source constants must be positive and finite")
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError(f"Invalid legacy09 response for run {historical_run}: {error}") from error

    base = {"path": "base/data09.base", "sha256": hashlib.sha256(payload).hexdigest()}
    inspected = calibration["sources"]
    unity = all(row[1:] == [0., 0., 0.] for row in attenuation)
    return dict(
        schema=1, mode="legacy09_diagnostic", period="1998_uv", legacy_period="09",
        historical_run=historical_run, physics_validation=False,
        detector_geometry_status="unqualified_for_1998", **scalars,
        attenuation=attenuation, sources=[base, *inspected],
        applied_sources=[base], inspected_sources=inspected,
        calibration_role="six_family_structural_read_only; not_applied_to_legacy_simulation",
        control_role=("tuning_candidate" if historical_run == 1321
                      else "validation_candidate_prior_use_unqualified"),
        prior_beam_target_use={
            "known_runs": [1321, 1324],
            "use": "both runs previously used for beam/target conditions and vertex diagnostics",
            "response_tuning_history": "not_fully_established",
            "holdout_scope": "prospective_response_only; not_independent_full_setup_validation",
        },
        control_barrel_tdc_windows=[list(row) for row in calibration["barrel_tdc_windows"]],
        masks=dict(status="unqualified", dead_channel_map=None,
                   zero_pedestal_bgo_channels=[i+1 for i, value in enumerate(
                       calibration["bgo_pedestal_by_readout"]) if value == 0],
                   zero_pedestal_policy="flag_identity_only; not_a_documented_dead_channel_flag"),
        attenuation09=dict(
            law="(x1*exp(x2*(-z))+x3*exp(x4*(-z)))/(x1*exp(x2*zc3)+x3*exp(x4*zc3))",
            z_units="cm", unity_for_loaded_parameters=unity,
            supported_domain="0<X1<=1; X3>=0; finite positive ratio on barrel; X1>1 replacement unsupported",
            policy="GRAAL_09_ratio; do_not_substitute_GRAAL_07_08_single_exponential"),
        electronics_mapping=dict(
            bgo="theta=(n-1)//32+1; phi=(n-1)%32+1; VSN=(n-1)//16; sub=(n-1)%16",
            barrel="copy=bar+100; ADC_VSN=34+(bar-1)//16; TDC_VSN=31+(bar-1)//16; sub=(bar-1)%16",
            sources=["laggen/src/lagcri.F", "laggen/src/lagvrtx.F", "decode/src/detectb.F",
                     "decode/src/ferabank.F"]),
        response_conventions=dict(
            bgo="legacy simulation rounded/saturated ADC; no gain, pedestal or nonlinearity correction",
            barrel="legacy simulation ADC without CBAR; direct simulation TDC, not reversed data TDC",
            light_speed="3.0e10 cm/s divided by data09 refractive-index divisor"),
        limitations=[
            "Diagnostic configuration is not physics, trigger or efficiency validation",
            "Frozen GRAAL_26 detector geometry remains unqualified for 1998",
            "Masks, efficiencies, time-zero/RF and actual historical reconstruction options unresolved",
            "Data-like electronics inversion, CBAR and nonlinear calibration are not implemented",
            "Run1324 has known prior beam/target use; prospective response holdout remains conditional",
        ],
    )


def write_response_config(data_directory, historical_run, output_root):
    """Publish one new ROOT config file with TTrees and JSON TObjString metadata.

    Write and close a same-directory partial, then hard-link it to the final
    name: link creation is atomic and fails if any writer already owns the
    destination. Unlike rename/replace, this cannot clobber a publication race.
    """
    import numpy as np
    import uproot

    destination = Path(output_root)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Refusing to overwrite response config: {destination}")
    response = read_legacy09_response(data_directory, historical_run)
    metadata = json.dumps(response, sort_keys=True, allow_nan=False)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".partial",
                                            dir=destination.parent)
    os.close(descriptor)
    partial = Path(temporary)
    try:
        with uproot.recreate(partial, compression=uproot.ZSTD(5)) as root:
            types = {key: ("int32" if key in ("dedxat", "historical_run") else "float64")
                     for key in SCALAR_KEYS}
            tree = root.mktree("scalars", types)
            tree.extend({key: np.asarray([response[key]], dtype=dtype) for key, dtype in types.items()})
            types = dict(channel="int32", x1="float64", x2="float64", x3="float64", x4="float64")
            tree = root.mktree("attenuation", types)
            rows = np.asarray(response["attenuation"], dtype=np.float64)
            tree.extend(dict(channel=np.arange(1, 33, dtype=np.int32),
                             **{f"x{i+1}": rows[:, i] for i in range(4)}))
            root["metadata"] = uproot.writing.identify.to_TObjString(metadata)
        with partial.open("rb") as stream:
            os.fsync(stream.fileno())
        os.link(partial, destination)
    finally:
        partial.unlink(missing_ok=True)
    return response


NEWPLAN_RECORDS = {
    "xp1_cm": (84, "XP1"), "xp2_cm": (85, "XP2"),
    "zp1_cm": (86, "ZP1"), "zp2_cm": (87, "ZP2"),
    "nf1": (92, "NF1"), "nf2": (93, "NF2"), "angle_deg": (114, "ANG(5)"),
    **{f"efficiency_{i}": (118+i, f"EFFPLA({i+1})") for i in range(4)},
}


def read_selected26_newplan(data_directory):
    """Read only the selected26 NEW_PLAN records, using original field formats."""
    payload = (Path(data_directory) / "base/data26.base").read_bytes()
    lines = payload.decode("ascii").splitlines()
    values = {}
    for key, (record, label) in NEWPLAN_RECORDS.items():
        if len(lines) < record or not re.match(r"\s*" + re.escape(label) + r"(?:\s|$)", lines[record-1].split("!", 1)[-1]):
            raise ValueError(f"Missing selected26 field label {label} at record {record}")
        values[key] = (_i5 if key in ("nf1", "nf2") else _f15_3)(lines[record-1])
    if values["nf1"] != 320 or values["nf2"] != 384 or values["angle_deg"] != -45:
        raise ValueError("Requires selected26 NEW_PLAN 320/384 wires and -45 degree readout")
    if any(values[key] <= 0 for key in ("xp1_cm", "xp2_cm", "zp1_cm", "zp2_cm")) or values["zp2_cm"] <= values["zp1_cm"]:
        raise ValueError("Invalid selected26 positive ordered geometry")
    if any(values[f"efficiency_{i}"] != 1 for i in range(4)):
        raise ValueError("Only source unit plane efficiencies are supported")
    return dict(schema=1, mode="selected26_newplan_diagnostic", **values,
                baseline=["GRAAL_26", "GRAAL_NEW_PLAN", "GRAAL_OLD_CYL"],
                physical_validation=False, physics_validation=False,
                units=dict(length="cm", angle="degree"),
                sources=[dict(path="base/data26.base", sha256=hashlib.sha256(payload).hexdigest())],
                records={key: record for key, (record, _) in NEWPLAN_RECORDS.items()},
                precision="F15.3/I5 source fields; native kernels REAL binary32",
                efficiency_policy="fixed_accept_unit_efficiency; no stochastic stream",
                geometry_certification="selected_configuration_only; input geometry not independently certified")


def write_newplan_config(data_directory, output_root):
    """Atomically publish a new typed ROOT config; never replace an existing file."""
    import numpy as np
    import uproot

    destination = Path(output_root)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Refusing to overwrite NEW_PLAN config: {destination}")
    response = read_selected26_newplan(data_directory)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".partial", dir=destination.parent)
    os.close(descriptor)
    partial = Path(temporary)
    try:
        with uproot.recreate(partial, compression=uproot.ZSTD(5)) as root:
            types = {key: "int32" if key in ("nf1", "nf2") else "float64" for key in NEWPLAN_RECORDS}
            tree = root.mktree("scalars", types)
            tree.extend({key: np.asarray([response[key]], dtype=dtype) for key, dtype in types.items()})
            root["metadata"] = json.dumps(response, sort_keys=True, allow_nan=False)
        os.link(partial, destination)
    finally:
        partial.unlink(missing_ok=True)
    return response
