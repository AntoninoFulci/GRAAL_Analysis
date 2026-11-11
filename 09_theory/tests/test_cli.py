"""Explicit input inspection works outside checkout; no prediction is implied."""
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PARAMS=ROOT/'data/theory/fix2010/parameters_solution_i.json'
RATIO=ROOT/'data/theory/fix2010/helicity_ratio_fig6_solution_i.json'


def run(tmp_path,*args):
    return subprocess.run([sys.executable,'-B','-m','graal_theory',*map(str,args)],cwd=tmp_path,capture_output=True,text=True)


def test_inspect_explicit_inputs_reports_incomplete(tmp_path):
    result=run(tmp_path,'inspect','--parameters',PARAMS,'--helicity',RATIO)
    assert result.returncode==0,result.stderr
    d=json.loads(result.stdout)
    assert d['dynamic_gate_G0']=='incomplete'
    assert d['prediction_available'] is False
    assert d['helicity_support_lab_gev'][1]<1.4
    assert len(d['input_sha256']['parameters'])==64
    assert len(d['gaps'])==6


def test_missing_file_is_actionable(tmp_path):
    result=run(tmp_path,'inspect','--parameters',tmp_path/'missing','--helicity',RATIO)
    assert result.returncode==2
    assert 'missing' in result.stderr
    assert 'Traceback' not in result.stderr


def test_no_predict_command_until_gates_close(tmp_path):
    result=run(tmp_path,'predict')
    assert result.returncode==2
    assert 'invalid choice' in result.stderr
