from src.services import crypto


def test_encrypt_roundtrip():
    ct = crypto.encrypt("super-secret-token")
    assert ct is not None
    assert b"super-secret-token" not in ct  # not stored in plaintext
    assert crypto.decrypt(ct) == "super-secret-token"


def test_encrypt_none_passthrough():
    assert crypto.encrypt(None) is None
    assert crypto.decrypt(None) is None
