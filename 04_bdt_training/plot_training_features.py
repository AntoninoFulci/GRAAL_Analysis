"""Export existing Stage-1 NPZ distributions without retraining a model."""
from __future__ import annotations

import argparse

from bdt_training.training.feature_reporting import export_training_features


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--features', nargs='+', required=True,
                        help='Validated NPZs; at most one per profile, common hypothesis')
    parser.add_argument('--out-dir', required=True, help='New diagnostic directory, outside model bundle')
    args = parser.parse_args(argv)
    metadata = export_training_features(args.features, args.out_dir)
    for item in metadata['inputs']:
        print(f"{item['beam_profile'] or 'unknown'}: {item['shape'][0]} rows; {item['sha256']}")
    print(f'Saved training_features.root, .pdf and .json to {args.out_dir}')


if __name__ == '__main__':
    main()
