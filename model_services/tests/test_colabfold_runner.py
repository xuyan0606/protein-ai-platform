import pytest
from model_services.thermostability.colabfold_runner import validate_local_msa, normalize_pdb


def test_local_policy_prevents_public_sequence_disclosure():
    for p in ({'msa_policy': 'public', 'allow_public_msa': True}, {'msa_policy':'local','allow_public_msa':True}):
        with pytest.raises(ValueError, match='local'):
            validate_local_msa({'sequence':'AC', 'alignment':'>q\nAC\n', **p})


def test_local_a3m_query_and_insertions():
    p = {'sequence':'AC', 'alignment':'>q\nAC\n>hit\nAaC\n', 'msa_policy':'local','allow_public_msa':False}
    assert validate_local_msa(p) == '>query\nAC\n>hit_1\nAC\n'
    with pytest.raises(ValueError):
        validate_local_msa({**p, 'alignment':'>q\nAA\n'})


def test_pdb_mapping_and_confidence_are_derived_from_same_ca():
    def atom(i, name, res, pos, b):
        return f'ATOM  {i:5d} {name:^4} {res:3s} B{pos:4d}    {0.:8.3f}{0.:8.3f}{0.:8.3f}{1.:6.2f}{b:6.2f}          C '
    pdb='\n'.join([atom(1,'CA','ALA',5,81.23),atom(2,'CA','CYS',7,72.11)])
    normalized, confidence = normalize_pdb(pdb, 'AC')
    assert confidence == [81.23,72.11]
    assert [int(l[22:26]) for l in normalized.splitlines() if l.startswith('ATOM')] == [1,2]
    assert normalized.splitlines()[0][21] == 'A'
    with pytest.raises(ValueError):
        normalize_pdb(pdb,'AA')
