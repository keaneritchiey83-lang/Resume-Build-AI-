from app.phase11_services import (
    _decode_raw_bitstring,
    _empty_bitstring,
    _encode_raw_bitstring,
    compressed_status_list,
    quantum_risk_for_algorithm,
    status_bit_get,
    status_bit_set,
)


def test_bitstring_default_minimum_and_roundtrip() -> None:
    raw = _empty_bitstring(131072)
    assert len(raw) == 16384
    status_bit_set(raw, 0, True)
    status_bit_set(raw, 131071, True)
    assert status_bit_get(raw, 0)
    assert status_bit_get(raw, 131071)
    encoded = _encode_raw_bitstring(raw)
    restored = _decode_raw_bitstring(encoded, 131072)
    assert restored == raw
    assert compressed_status_list(raw).startswith("u")


def test_status_bit_can_be_cleared() -> None:
    raw = _empty_bitstring(131072)
    status_bit_set(raw, 9, True)
    assert status_bit_get(raw, 9)
    status_bit_set(raw, 9, False)
    assert not status_bit_get(raw, 9)


def test_pqc_inventory_flags_classical_public_key_algorithms() -> None:
    risk, _ = quantum_risk_for_algorithm("ECDSA P-256")
    assert risk == "high"

    risk, _ = quantum_risk_for_algorithm("ML-DSA")
    assert risk == "pqc"
