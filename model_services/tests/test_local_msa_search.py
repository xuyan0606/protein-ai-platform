from pathlib import Path
import pytest
from model_services.thermostability import colabfold_runner as runner


def test_missing_alignment_can_use_bounded_local_database_search(tmp_path, monkeypatch):
    database = tmp_path / 'uniprot20'
    Path(str(database) + '_hhm.ffindex').write_text('fixture')
    monkeypatch.setenv('COLABFOLD_HHBLITS_DATABASE', str(database))
    monkeypatch.setenv('COLABFOLD_HHBLITS_BINARY', '/fixture/hhblits')
    calls = []
    def execute(command, **kwargs):
        calls.append((command, kwargs))
        Path(command[command.index('-oa3m')+1]).write_text('>query\nACDE\n>homolog\nAC-E\n')
    monkeypatch.setattr(runner.subprocess, 'run', execute)
    alignment, metadata = runner.resolve_alignment({'sequence': 'ACDE', 'alignment': '',
        'msa_source': 'service_local_search', 'msa_policy': 'local', 'allow_public_msa': False}, tmp_path/'work')
    assert alignment == '>query\nACDE\n>hit_1\nAC-E\n'
    assert metadata['msa_source'] == 'service_local_search' and metadata['msa_depth'] == 2
    command, kwargs = calls[0]
    assert command[command.index('-d')+1] == str(database)
    assert '-cpu' in command and '-maxmem' in command and kwargs['timeout'] <= 300


def test_local_search_never_overrides_public_policy_or_discloses_sequence(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Policy validation must happen before subprocess or network')
    monkeypatch.setattr(runner.subprocess, 'run', forbidden)
    with pytest.raises(ValueError, match='local'):
        runner.resolve_alignment({'sequence':'ACDE', 'alignment':'', 'msa_source':'service_local_search',
            'msa_policy':'public','allow_public_msa':True}, tmp_path)
