import pytest
from model_services.thermostability.evcouplings_runner import prepare_alignment, parse_couplings, verify_quality


def test_msa_is_normalized_and_caller_quality_cannot_supply_neff():
    p={'sequence':'ACD','alignment':'>original/25-27\nACD\n>x\nAc-D\n','msa_quality':{'neff':9999}}
    text, rows=prepare_alignment(p)
    assert text.startswith('>query/1-3\nACD\n')
    assert rows == ['ACD','A-D']
    with pytest.raises(ValueError,match='Neff'):
        verify_quality(rows, 1.0, 3)


def test_plmc_pairs_use_real_apc_score_and_validate_positions():
    rows=parse_couplings('1 A 3 D 2.5 1.75\n',3)
    assert rows == [{'position_i':1,'position_j':3,'score':1.75}]
    for text in ('1 A 4 D 1 2\n','1 A 3 D 1 nan\n','1 A 3 D 1 2\n1 A 3 D 1 3\n'):
        with pytest.raises(ValueError): parse_couplings(text,3)
