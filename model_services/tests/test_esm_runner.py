import pytest
from model_services.thermostability.esm_runner import validate, run_esm


@pytest.mark.parametrize('payload', [
    {'sequence': 'ACD', 'mode': 'mutations', 'mutations': ['A1V']},
    {'sequence': 'ACDEX', 'mode': 'mutations', 'mutations': ['A1V']},
    {'sequence': 'ACDEF', 'mode': 'mutations', 'mutations': ['G1V']},
    {'sequence': 'ACDEF', 'mode': 'mutations', 'mutations': ['A1A']},
    {'sequence': 'ACDEF', 'mode': 'mutations', 'mutations': ['A1V', 'A1V']},
    {'sequence': 'ACDEF', 'mode': 'embedding', 'mutations': ['A1V']},
])
def test_invalid_input_is_rejected_before_loading_a_model(payload, tmp_path):
    with pytest.raises(ValueError):
        run_esm(payload, tmp_path)


def test_valid_mutations_preserve_exact_wt_positions():
    assert validate({'sequence': 'ACDEF', 'mode': 'mutations', 'mutations': ['A1V', 'F5Y']}) == ('ACDEF', ['A1V', 'F5Y'])
