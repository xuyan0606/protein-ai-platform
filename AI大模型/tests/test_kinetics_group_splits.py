import json
from pathlib import Path
from build_kinetics_group_splits import main
from run_kinetics_baselines import parse_numeric

def test_parse_numeric_conditions():
    assert parse_numeric('25°C') == 25.0
    assert parse_numeric('21-23°C') == 22.0
    assert parse_numeric('not reported') is None
    assert parse_numeric(None) is None

def test_group_split_keeps_sequence_together(tmp_path, monkeypatch):
    inp=tmp_path/'r.jsonl'; inp.write_text('\n'.join(json.dumps({'record_id':str(i),'sequence_hash':'same' if i<2 else 'other','metric':'km'}) for i in range(3))+'\n')
    out=tmp_path/'s.json'; monkeypatch.setattr('sys.argv',['x','--input',str(inp),'--output',str(out),'--folds','2']); main(); data=json.loads(out.read_text()); assert data['assignments']['same'] == data['assignments']['same']
