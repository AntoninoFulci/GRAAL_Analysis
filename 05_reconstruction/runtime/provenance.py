"""Reconstruction selection provenance shared by downstream readers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


KEY = "reconstruction_provenance"


def stage1_domain(gate):
    """Carry the model's declared coverage through ROOT reconstruction outputs."""
    if gate is None:
        return None
    domain = {"beam_profile": getattr(gate, "beam_profile", None),
              "energy_range_gev": getattr(gate, "energy_range_gev", None)}
    supported = getattr(gate, "supported_profiles", None)
    if supported is not None:
        domain["supported_profiles"] = supported
    return domain


def file_identities(paths):
    """Hash input bytes, keeping canonical paths and sizes for reproducibility."""
    identities = []
    for path in sorted(map(Path, paths)):
        with path.open("rb") as stream:
            hasher = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(chunk)
            digest = hasher.hexdigest()
        identities.append({"path": str(path.resolve()), "size": path.stat().st_size,
                           "sha256": digest})
    return identities


def validate_no_fit(source, tree) -> dict:
    """Reject historical raw branches whose event selection may include 6C."""
    record = source.Get(KEY)
    if not record:
        raise ValueError("no-fit baseline requires reconstruction provenance; rebuild from selected h85/h80")
    try:
        metadata = json.loads(record.GetTitle())
    except (TypeError, ValueError) as error:
        raise ValueError("invalid reconstruction provenance") from error
    if not isinstance(metadata, dict) or metadata.get("do_fit") is not False:
        raise ValueError("no-fit baseline requires provenance do_fit=false")
    if any("fit" in branch.GetName() for branch in tree.GetListOfBranches()):
        raise ValueError("no-fit baseline cannot reuse historical fit-selected raw branches")
    return metadata


def validate_energy_domain(metadata, profile, energy_range, *, requires_bdt, allow_legacy=False):
    """An expanded analysis cannot recover events discarded upstream."""
    from graal_common.physics.beam_profiles import get_beam_profile
    from graal_common.physics.energy_binning import EnergyBinning

    beam = get_beam_profile(profile)
    requested = EnergyBinning(energy_range).validate_profile(beam).energy_range_gev
    bounds = metadata.get("selection", {}).get("energy_range_gev")
    if bounds is None:
        if allow_legacy and metadata.get("beam_profile") is None:
            # Standalone reconstruction historically allowed no profile and
            # no energy cut. Preserve its nominal compatibility, not expansion.
            bounds = beam.energy_range_gev
        else:
            raise ValueError("reconstruction energy range missing; rebuild for requested grid")
    domain = EnergyBinning(bounds).validate_profile(beam).energy_range_gev
    if domain[0] > requested[0] or domain[1] < requested[1]:
        raise ValueError("reconstruction energy range does not cover requested grid")
    stored_profile = metadata.get("beam_profile")
    if stored_profile != profile and not (allow_legacy and stored_profile is None):
        raise ValueError("reconstruction beam profile missing or mismatched; rebuild")
    if requires_bdt:
        model = metadata.get("bdt_domain") or {}
        if "supported_profiles" in model:
            profiles = model["supported_profiles"]
            if not isinstance(profiles, dict) or profile not in profiles:
                raise ValueError("shared BDT does not cover requested profile")
            bounds = EnergyBinning(profiles[profile]).validate_profile(beam).energy_range_gev
            if bounds[0] > requested[0] or bounds[1] < requested[1]:
                raise ValueError("shared BDT energy range does not cover requested grid")
            return
        if allow_legacy and model.get("beam_profile") is None and model.get("energy_range_gev") is None:
            return
        if model.get("beam_profile") != profile or model.get("energy_range_gev") is None:
            raise ValueError("BDT energy domain missing or mismatched; rebuild with validated model")
        bounds = EnergyBinning(model["energy_range_gev"]).validate_profile(beam).energy_range_gev
        if bounds[0] > requested[0] or bounds[1] < requested[1]:
            raise ValueError("BDT energy range does not cover requested grid")
