from build_sequence_ip_review_packets import packet_row
from validate_sequence_ip_review_packets import validate


def base_source_row():
    return {
        "record_id": "candidate-001",
        "uniprot_id": "P12345",
        "mutation": "A1V",
        "packet_id": "source-packet-001",
    }


def test_uniprot_id_is_not_fabricated_into_sequence_hash():
    packet = packet_row(base_source_row())
    assert packet["parent_sequence_hash"] is None
    assert packet["parent_sequence_path"] is None
    assert packet["parent_sequence_hash_source"] is None
    assert packet["sequence_material_available"] is False
    assert validate(packet) == []


def test_real_parent_sequence_receipt_is_bound_to_live_file(tmp_path, monkeypatch):
    sequence = tmp_path / "parent_sequence.txt"
    sequence.write_text("MAV", encoding="utf-8")
    import hashlib

    digest = hashlib.sha256(sequence.read_bytes()).hexdigest()
    row = base_source_row()
    row["source_receipts"] = {"parent_sequence": {"path": sequence.name, "sha256": digest}}
    packet = packet_row(row)

    import validate_sequence_ip_review_packets as validator

    monkeypatch.setattr(validator, "AI_ROOT", tmp_path)
    assert packet["parent_sequence_hash"] == digest
    assert packet["parent_sequence_hash_source"] == "source_receipts.parent_sequence.sha256"
    assert packet["sequence_material_available"] is True
    assert validator.validate(packet) == []


def test_hash_without_receipt_source_is_rejected():
    packet = packet_row(base_source_row())
    packet["parent_sequence_hash"] = "a" * 64
    assert "invalid_parent_sequence_hash_source" in validate(packet)


def test_malformed_hash_is_rejected():
    packet = packet_row(base_source_row())
    packet.update({
        "parent_sequence_hash": "not-a-sha",
        "parent_sequence_path": "missing.txt",
        "parent_sequence_hash_source": "source_receipts.parent_sequence.sha256",
        "sequence_material_available": True,
    })
    assert "invalid_parent_sequence_hash" in validate(packet)
