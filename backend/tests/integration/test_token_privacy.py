from sqlalchemy import select

from src.models.account import Credential
from tests.helpers import seed_account


def test_tokens_encrypted_at_rest(db):
    seed_account(db)
    cred = db.scalars(select(Credential)).first()
    assert cred.enc_refresh_token is not None
    assert b"refresh-token" not in cred.enc_refresh_token  # ciphertext, not plaintext


def test_tokens_absent_from_account_api(client, oauth_provider):
    client.get("/api/accounts/callback", params={"code": "x", "state": "s"},
               follow_redirects=False)
    resp = client.get("/api/accounts")
    assert resp.status_code == 200
    body = resp.text.lower()
    assert "refresh" not in body
    assert "token" not in body
    assert "credential" not in body
