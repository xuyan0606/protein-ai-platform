"""Input-bound client for the isolated, fixed 650M ESM scoring service."""
import hashlib
import json
import os
import re
from urllib.parse import urlsplit

import httpx

from app.services.thermostability_limits import service_timeout
from app.tools.thermostability_adapters import _envelope, _number


def score_with_service(sequence: str, mutations: list[str]) -> dict:
    try:
        if not 5 <= len(sequence) <= 1022:
            raise ValueError('ESM-2 supports 5–1022 residues in this deployment.')
        if not isinstance(mutations, list) or not 1 <= len(mutations) <= 500:
            raise ValueError('Supply 1–500 distinct substitutions.')
        codes = []
        for code in mutations:
            if not isinstance(code, str):
                raise ValueError('Invalid mutation code.')
            code = code.strip().upper()
            match = re.fullmatch(r'([ACDEFGHIKLMNPQRSTVWY])([1-9][0-9]{0,3})([ACDEFGHIKLMNPQRSTVWY])', code)
            if not match or int(match[2]) > len(sequence) or sequence[int(match[2])-1] != match[1] or match[1] == match[3]:
                raise ValueError('Mutation must change the matching WT residue at a 1-based sequence position.')
            codes.append(code)
        if len(set(codes)) != len(codes):
            raise ValueError('Duplicate mutations are not allowed.')
        url = os.environ['ESM_SERVICE_URL'].rstrip('/')
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Invalid ESM service base URL.')
        token = os.getenv('ESM_SERVICE_TOKEN', '')
        payload = {'sequence': sequence, 'mutations': codes, 'mode': 'mutations'}
        with httpx.Client(timeout=httpx.Timeout(service_timeout('ESM', 300), connect=10, pool=10),
                          trust_env=False, follow_redirects=False) as client:
            with client.stream('POST', url + '/esm/predict', json=payload,
                               headers={'Authorization': 'Bearer ' + token} if token else {}) as response:
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > 16_000_000:
                        raise ValueError('ESM result exceeds bounds.')
        result = json.loads(data)
        envelope = _envelope(result, 'ESM-2', payload, hashlib.sha256(data).hexdigest())
        if not result['model_version'].startswith('esm2_t33_650M_UR50D; weights_sha256:'):
            raise ValueError('The configured service must use the promised ESM-2 650M model and report its weight hash.')
        if not re.fullmatch(r'[0-9a-f]{64}', result['model_version'].split('weights_sha256:', 1)[-1]):
            raise ValueError('Missing ESM weight hash.')
        if result.get('is_real_inference') is not True or result.get('scoring_strategy') != 'wild_type_marginal' or result.get('context') != 'unmasked_wild_type_sequence':
            raise ValueError('Service must report real wild-type marginal inference.')
        rows = result.get('mutations')
        if not isinstance(rows, list) or len(rows) != len(codes):
            raise ValueError('Incomplete ESM scores.')
        if result['evidence']['raw_result'].get('mutations') != rows:
            raise ValueError('ESM scores differ from retained raw evidence.')
        seen = set()
        for row in rows:
            code = row.get('mutation')
            if code not in codes or code in seen or row.get('error'):
                raise ValueError('ESM mutation identity mismatch.')
            seen.add(code)
            if row.get('wild_type') != code[0] or row.get('mutant') != code[-1] or row.get('position') != int(code[1:-1]):
                raise ValueError('ESM residue identity mismatch.')
            _number(row.get('score'))
        return {**envelope, 'mutations': rows, 'is_real_inference': True,
                'scoring_strategy': 'wild_type_marginal', 'context': 'unmasked_wild_type_sequence',
                'is_thermostability_prediction': False,
                'interpretation': 'Sequence-model preference only; does not establish ΔΔG, ΔTm or activity improvement.'}
    except Exception as exc:
        # URL, authorization and model paths stay in private operator configuration.
        return {'status': 'blocked', 'is_real_inference': False, 'mutations': [],
                'blocked_reason': 'esm_service_unavailable_or_invalid_receipt:' + type(exc).__name__}
