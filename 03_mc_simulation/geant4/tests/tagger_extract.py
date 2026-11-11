"""Convert HGIVE/HUNPAK export to a ROOT response archive, never fit a shape.

The text export is a disposable technical intermediate from tagger_hbook_export.F.
Only the ROOT archive is needed by the response. Original HBOOK remains immutable.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import uproot

from mc_simulation.geant4.digitize import sha256
from mc_simulation.geant4.tagger import histogram_payload_sha256


def convert(export, source, output, image_inspect):
    export, source, output = map(Path, (export, source, output))
    lines = iter(export.read_text().splitlines())
    histograms, flows = {}, {}
    for expected in range(101, 118):
        fields = next(lines).split()
        ident, size = map(int, fields[:2])
        low, high = map(float, fields[2:])
        if ident != expected or size <= 0 or not np.isfinite([low, high]).all() or low >= high:
            raise ValueError("Invalid HGIVE histogram axis")
        flow_values = list(map(float, next(lines).split()))
        if len(flow_values) != 2 or not np.isfinite(flow_values).all() or min(flow_values) < 0:
            raise ValueError("Invalid original flow bins")
        flows[str(ident)] = dict(zip(("underflow", "overflow"), flow_values))
        values = []
        for index in range(1, size + 1):
            bin_index, value = next(lines).split()
            if int(bin_index) != index:
                raise ValueError("HUNPAK bin order mismatch")
            values.append(float(value))
        values = np.asarray(values, dtype=np.float64)
        if not np.isfinite(values).all() or np.any(values < 0) or values.sum() <= 0:
            raise ValueError("Invalid response bin content")
        histograms[ident] = values, np.linspace(low, high, size + 1)
    if list(lines):
        raise ValueError("Unexpected export trailing records")
    module = Path(__file__).resolve().parent
    manifest = json.loads((module.parent / "reference/manifest.json").read_text())
    inspected = json.loads(Path(image_inspect).read_text())[0]
    if manifest["legacy"]["image"] not in inspected["RepoDigests"]:
        raise ValueError("Executed legacy image digest does not match pinned image")
    metadata = dict(schema=1, mode="exact_hbook_tagger_response",
                    source_path=str(source.resolve()), source_sha256=sha256(source),
                    extraction="HRGET/HGIVE/HUNPAK; bin contents are original REAL values",
                    source_histogram_ids=list(histograms), displacement_unit="mm",
                    flow_bins=flows, sampling="regular bins only; original flow bins retained in metadata",
                    export_sha256=sha256(export), legacy=manifest["legacy"],
                    executed_image_id=inspected["Id"], executed_image_digests=inspected["RepoDigests"],
                    payload_sha256=histogram_payload_sha256(histograms),
                    code_sha256={str(p): sha256(p) for p in
                                 (module / "tagger_hbook_export.F", Path(__file__).resolve(),
                                  module.parent / "tagger.py", module.parent / "digitize.py")})
    with uproot.create(output, compression=uproot.ZSTD(5)) as root:
        root["metadata"] = json.dumps(metadata, sort_keys=True)
        for ident, histogram in histograms.items():
            root[f"response_{ident}"] = histogram
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export")
    parser.add_argument("source")
    parser.add_argument("output")
    parser.add_argument("image_inspect")
    args = parser.parse_args()
    convert(args.export, args.source, args.output, args.image_inspect)
