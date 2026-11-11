"""Inspect source-verified components. Prediction awaits the scientific gates."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from .helicity import load_ratio
from .parameters import inspect_parameters


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    inspect=sub.add_parser('inspect',help='inspect incomplete inputs; never calculate predictions')
    inspect.add_argument('--parameters',required=True,type=Path)
    inspect.add_argument('--helicity',required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        inventory=inspect_parameters(args.parameters)
        ratio=load_ratio(args.helicity)
        result={
            'model_version':inventory.version,
            'label':'Reconstruction components of Fix2010 solution I; figure-derived helicity ratio',
            'dynamic_gate_G0':'incomplete','prediction_available':False,
            'requested_domain_lab_gev':inventory.domain_lab_gev,
            'helicity_support_lab_gev':[ratio.energy_lab_gev[0],ratio.energy_lab_gev[-1]],
            'gaps':[{'id':g[0],'state':g[1],'consequence':g[2]} for g in inventory.gaps],
            'input_sha256':{name:hashlib.sha256(path.read_bytes()).hexdigest()
                            for name,path in [('parameters',args.parameters),('helicity',args.helicity)]}}
    except (OSError,ValueError) as exc:
        parser.exit(2,f'graal_theory: {exc}\n')
    print(json.dumps(result,indent=2,allow_nan=False))
    return 0
