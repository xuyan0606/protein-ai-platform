import json
from pathlib import Path
from probe_frozen_plm_readiness import main

def test_probe_fails_closed_without_weights(tmp_path, monkeypatch):
    inp = tmp_path / 'input.jsonl'; inp.write_text('{"sequence":"ACDE"}\n')
    out = tmp_path / 'report.json'
    monkeypatch.setattr('sys.argv', ['x', '--input', str(inp), '--output', str(out)])
    main(); report = json.loads(out.read_text())
    assert report['embedding_written'] is False
    assert report['training_run_started'] is False
    assert report['status'] == 'blocked_missing_local_runtime_or_weights'
