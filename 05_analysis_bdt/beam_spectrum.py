"""Measure the real beam spectrum, and reweight the Monte Carlo onto it.

The generators sample the tagged photon energy as `rng.Uniform(threshold, 1.55)`
— flat between the channel's production threshold and a hard ceiling. GRAAL's
beam is nothing like that. It is laser light Compton-backscattered off the
storage ring, so the spectrum rises to a Compton edge that sits wherever the
laser line puts it, and stops. Measured over data/selected: two superimposed
edges (the green and UV lines used in different run periods), a shoulder near
0.79, and a tail out to 1.72 that the MC's 1.55 ceiling does not cover at all.

`beam_E` is one of the 24 stage-1 features, and the rest of the event kinematics
are correlated with it, so a flat MC beam is not a cosmetic mismatch: the
classifier learns a boundary calibrated to a beam the experiment never had. This
module measures p_data(E) from the real files and hands back per-event weights
p_data(E) / p_mc(E), so the training sample carries the beam the data carries.

Reweighting the beam marginal is enough to move everything downstream with it,
because the generators draw the beam energy first and build the event kinematics
from it: fix the marginal and the correlations follow.

Usage:
    python -m analysis_bdt.beam_spectrum \\
        --selected-dir data/selected \\
        --output 05_analysis_bdt/data/beam_spectrum.npz
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np

try:
    import uproot
except ImportError as exc:
    raise ImportError("uproot required: pip install uproot") from exc

from graal_common import trees

# Wide enough to hold every tagged photon in the data (0.64 to 1.72 measured)
# with room on both sides, so nothing piles into an edge bin unseen.
DEFAULT_RANGE = (0.5, 2.0)
DEFAULT_BINS = 150


@dataclass(frozen=True)
class BeamSpectrum:
    """A normalised histogram of tagged beam-photon energies."""

    edges: np.ndarray      # (nbins+1,)
    density: np.ndarray    # (nbins,), integrates to 1 across the edges

    def pdf(self, E: np.ndarray) -> np.ndarray:
        """Density at each energy. Zero outside the measured range."""
        idx = np.digitize(E, self.edges) - 1
        inside = (idx >= 0) & (idx < len(self.density))
        out = np.zeros(len(E), dtype=np.float64)
        out[inside] = self.density[idx[inside]]
        return out

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, edges=self.edges, density=self.density)

    @classmethod
    def load(cls, path: str | Path) -> "BeamSpectrum":
        d = np.load(path)
        return cls(edges=d["edges"], density=d["density"])


def _density(E: np.ndarray, edges: np.ndarray) -> np.ndarray:
    counts, _ = np.histogram(E, bins=edges)
    total = counts.sum()
    if total == 0:
        raise ValueError("no events inside the spectrum range")
    return counts / (total * np.diff(edges))


def from_energies(
    E: np.ndarray,
    bins: int = DEFAULT_BINS,
    range_: tuple[float, float] = DEFAULT_RANGE,
) -> BeamSpectrum:
    edges = np.linspace(range_[0], range_[1], bins + 1)
    return BeamSpectrum(edges=edges, density=_density(E, edges))


def read_beam_energies(path: str | Path, tree: str = trees.AUTO) -> np.ndarray:
    """Tagged photon energies from one preselected file.

    The detector files store the beam as a ROOT::Math::LorentzVector, whose
    members are fCoordinates.fX/fY/fZ/fT — not the fP/fE of the TLorentzVector
    the MC generators write. Same quantity, different layout on disk.
    """
    with uproot.open(path) as f:
        names = [k.split(";")[0] for k in f.keys()]
        t = f[trees.resolve(names, tree, str(path))]
        if t.num_entries == 0:
            return np.empty(0)
        coords = t["beam"].array(library="ak")["fCoordinates"]
        return np.asarray(coords["fCoordinates.fT"], dtype=np.float64)


def measure(
    selected_dir: str | Path,
    tree: str = trees.AUTO,
    bins: int = DEFAULT_BINS,
    range_: tuple[float, float] = DEFAULT_RANGE,
) -> BeamSpectrum:
    """The beam spectrum of every preselected file in a directory."""
    selected_dir = Path(selected_dir)
    files = sorted(selected_dir.glob("*.root"))
    if not files:
        raise FileNotFoundError(f"no .root files in {selected_dir}")

    chunks = []
    for path in files:
        E = read_beam_energies(path, tree)
        if len(E) == 0:
            print(f"  {path.name}: empty, skipped")
            continue
        chunks.append(E)
        print(f"  {path.name}: {len(E)} events, E up to {E.max():.3f}")

    if not chunks:
        raise ValueError(f"every file in {selected_dir} is empty")

    E = np.concatenate(chunks)
    print(f"Measured {len(E)} tagged photons: "
          f"min {E.min():.3f}, median {np.median(E):.3f}, max {E.max():.3f}")
    return from_energies(E, bins, range_)


# Below this many MC events in a bin, p_mc is not an estimate of anything and
# the ratio against it is noise. See reweight().
MIN_MC_PER_BIN = 200


def reweight(
    mc_beam_E: np.ndarray,
    target: BeamSpectrum,
    min_mc_per_bin: int = MIN_MC_PER_BIN,
) -> np.ndarray:
    """Per-event weights taking an MC sample's beam spectrum onto `target`.

    w = p_data(E) / p_mc(E), with p_mc measured from the sample itself rather
    than assumed: each generator's flat range starts at its own production
    threshold, so no single analytic form covers all six channels.

    Events at energies the data never produced get weight 0 — correctly, since
    the experiment could not have recorded them.

    So do events in bins holding fewer than `min_mc_per_bin` MC events, and that
    part is load-bearing. A generator draws flat from its channel's production
    threshold upwards and then smears by the tagger resolution, so just below
    that threshold the MC holds nothing but a smearing tail — while the data
    there is full of events. Those data events are real, but they cannot be this
    channel: below threshold the reaction does not happen, and they are
    somebody's background. Dividing by that tail asks the ratio a question the
    MC cannot answer and gets an enormous number back. Measured on eta_pi0
    (threshold 0.875): the 0.870-0.880 bin had p_data/p_mc = 1994, 128 events
    across the sample ended up carrying 3.3% of all the training weight, and the
    effective sample size collapsed to 1.2% of the events.

    Declining to reweight where the MC cannot estimate its own density is the
    honest form of that. It drops a sliver of phase space instead of inventing
    signal below threshold.
    """
    counts, _ = np.histogram(mc_beam_E, bins=target.edges)
    reliable = counts >= min_mc_per_bin

    density = np.where(reliable, _density(mc_beam_E, target.edges), 0.0)
    mc = BeamSpectrum(edges=target.edges, density=density)

    numerator = target.pdf(mc_beam_E)
    denominator = mc.pdf(mc_beam_E)
    return np.where(denominator > 0, numerator / np.maximum(denominator, 1e-12), 0.0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selected-dir", default="data/selected",
                        help="folder with the preselected detector files")
    parser.add_argument("--tree", default=trees.AUTO,
                        help="tree inside them; 'auto' takes whichever known "
                             "preselection tree is there")
    parser.add_argument("--bins", type=int, default=DEFAULT_BINS)
    parser.add_argument("--output", default="05_analysis_bdt/data/beam_spectrum.npz")
    args = parser.parse_args()

    spectrum = measure(args.selected_dir, args.tree, args.bins)
    spectrum.save(args.output)
    print(f"Saved beam spectrum → {args.output}")


if __name__ == "__main__":
    main()
