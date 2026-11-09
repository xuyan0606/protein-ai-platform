import hashlib
import json
import httpx
import pytest
from app.tools.esm2_predict import esm2_predict


def digest(value):
    if not isinstance(value, str):
        value = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(value.encode()).hexdigest()


@pytest.mark.parametrize('fault', ['', 'sequence', 'missing_score', 'nan', 'wrong_wt', 'wrong_model'])
def test_configured_esm_scoring_uses_input_bound_service_receipt(monkeypatch, fault):
    monkeypatch.setenv('ESM_SERVICE_URL', 'http://model.test')
    monkeypatch.setenv('ESM_SERVICE_TOKEN', 'test-only-token')
    requests = []
    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        rows = [{'mutation': 'A1V', 'position': 1, 'wild_type': 'A', 'mutant': 'V', 'score': -0.25}]
        if fault == 'missing_score': rows = []
        if fault == 'wrong_wt': rows[0]['wild_type'] = 'G'
        raw = {'mutations': rows}
        result = {'status': 'completed', 'model': 'ESM-2', 'model_version': 'esm2_t33_650M_UR50D; weights_sha256:' + 'b' * 64,
                  'database_version': 'not_used:single_sequence', 'algorithm_commit': 'a' * 40,
                  'sequence_sha256': digest(payload['sequence']), 'input_sha256': digest(payload),
                  'is_real_inference': True, 'scoring_strategy': 'wild_type_marginal',
                  'context': 'unmasked_wild_type_sequence', 'mutations': rows,
                  'evidence': {'raw_result': raw, 'raw_result_sha256': digest(raw)}}
        if fault == 'sequence': result['sequence_sha256'] = '0' * 64
        if fault == 'wrong_model': result['model_version'] = 'esm2_t6_8M_UR50D'
        if fault == 'nan':
            # Deliberately invalid JSON numeric response; adapter must reject it.
            return httpx.Response(200, content=json.dumps(result).replace('-0.25', 'NaN'))
        return httpx.Response(200, json=result)
    client = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: client(transport=httpx.MockTransport(respond)))
    result = esm2_predict('ACDEF', ['A1V'])
    assert requests == [{'sequence': 'ACDEF', 'mutations': ['A1V'], 'mode': 'mutations'}]
    if fault:
        assert result.get('is_real_inference') is False
        assert result.get('status') == 'blocked'
    else:
        assert result['is_real_inference'] is True
        assert result['mutations'][0]['score'] == -0.25
        assert result['sequence_sha256'] == digest('ACDEF')
        assert result['is_thermostability_prediction'] is False
