"""ESM-2 650M CPU scoring; fixed local weights, no runtime downloads."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re


def validate(payload):
    sequence = payload.get('sequence')
    if not isinstance(sequence, str) or not 5 <= len(sequence) <= 1022 or set(sequence) - set('ACDEFGHIKLMNPQRSTVWY'):
        raise ValueError('ESM requires 5–1022 canonical amino acids.')
    codes = payload.get('mutations')
    if payload.get('mode') != 'mutations' or not isinstance(codes, list) or not 1 <= len(codes) <= 500:
        raise ValueError('ESM requires 1–500 explicit substitutions.')
    seen = set()
    for code in codes:
        match = re.fullmatch(r'([ACDEFGHIKLMNPQRSTVWY])([1-9][0-9]{0,3})([ACDEFGHIKLMNPQRSTVWY])', code) if isinstance(code, str) else None
        if not match or int(match[2]) > len(sequence) or sequence[int(match[2])-1] != match[1] or match[1] == match[3] or code in seen:
            raise ValueError('Invalid or duplicate WT substitution.')
        seen.add(code)
    return sequence, codes


def run_esm(payload, workdir):
    sequence, codes = validate(payload)
    weights = Path(os.environ['ESM_WEIGHTS_PATH'])
    if weights.name != 'esm2_t33_650M_UR50D.pt' or not weights.is_file():
        raise RuntimeError('Fixed ESM-2 650M weights are not installed.')
    digest = hashlib.sha256()
    with weights.open('rb') as handle:
        while chunk := handle.read(1024*1024):
            digest.update(chunk)
    expected = os.environ['ESM_WEIGHTS_SHA256']
    if digest.hexdigest() != expected:
        raise RuntimeError('ESM weight digest mismatch.')
    commit = os.environ['ESM_ALGORITHM_COMMIT']
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise RuntimeError('ESM runner source must have a frozen commit.')
    import torch
    import esm
    torch.set_num_threads(2)
    model, alphabet = esm.pretrained.load_model_and_alphabet_local(str(weights))
    model.eval()
    _, _, tokens = alphabet.get_batch_converter()([('query', sequence)])
    with torch.inference_mode():
        logits = model(tokens, return_contacts=False)['logits']
    rows = []
    for code in codes:
        position = int(code[1:-1])
        score = float(logits[0, position, alphabet.get_idx(code[-1])] - logits[0, position, alphabet.get_idx(code[0])])
        rows.append({'mutation': code, 'position': position, 'wild_type': code[0], 'mutant': code[-1],
                     'score': round(score, 4), 'scoring_strategy': 'wild_type_marginal'})
    result = {'mutations': rows, 'is_real_inference': True, 'is_thermostability_prediction': False,
              'scoring_strategy': 'wild_type_marginal', 'context': 'unmasked_wild_type_sequence'}
    return {'result': result, 'raw_result': {'mutations': rows, 'torch_version': torch.__version__,
            'weights_sha256': expected, 'sequence_length': len(sequence)},
            'model_version': 'esm2_t33_650M_UR50D; weights_sha256:' + expected,
            'algorithm_commit': commit, 'database_version': 'not_used:single_sequence_pretrained_model'}
