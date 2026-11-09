"""Durable user-confirmed names; these records are not curated functional proof."""
import re
import uuid

from sqlalchemy import select

from app.models.identity_consistency import IdentityConsistencyRecord
from app.services.identity_consistency import sequence_hash

VERSION = 'user_confirmed_name_v1'


def confirmation_label(message: str) -> str | None:
    match = re.fullmatch(r'(?:确认身份|更正身份|确认酶身份)\s*[:：]\s*([^\n\r;；。！？!?<>\[\]{}]{1,120})[。]?\s*', str(message or ''))
    label = match[1].strip() if match else ''
    if not label or label in {'未知', '不确定', '待确认', 'unknown'}:
        return None
    return label


async def save_confirmed_identity(session, *, user_id: int, sequence: str, identity: str) -> dict:
    if not 10 <= len(sequence) <= 4000 or set(sequence) - set('ACDEFGHIKLMNPQRSTVWY'):
        raise ValueError('A verified current input sequence is required.')
    row = IdentityConsistencyRecord(user_id=user_id, sequence_hash=sequence_hash(sequence),
        model_version=VERSION, evidence_version=uuid.uuid4().hex, identity=identity, status='USER_CONFIRMED')
    session.add(row)
    await session.flush()
    return _public(row)


def _public(row):
    return {'record_id': row.id, 'sequence_hash': row.sequence_hash, 'identity': row.identity,
            'status': 'USER_CONFIRMED', 'source': 'explicit_user_confirmation',
            'is_curated_functional_evidence': False}


async def get_confirmed_identity(session, *, user_id: int, sequence: str) -> dict | None:
    row = (await session.execute(select(IdentityConsistencyRecord).where(
        IdentityConsistencyRecord.user_id == user_id,
        IdentityConsistencyRecord.sequence_hash == sequence_hash(sequence),
        IdentityConsistencyRecord.model_version == VERSION,
        IdentityConsistencyRecord.status == 'USER_CONFIRMED',
    ).order_by(IdentityConsistencyRecord.id.desc()).limit(1))).scalar_one_or_none()
    return _public(row) if row else None
