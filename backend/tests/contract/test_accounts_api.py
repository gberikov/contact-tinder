def test_connect_returns_authorization_url(client):
    resp = client.post("/api/accounts/connect")
    assert resp.status_code == 200
    assert resp.json()["authorizationUrl"].startswith("https://accounts.google.com/")


def test_callback_creates_account_and_redirects(client):
    resp = client.get(
        "/api/accounts/callback", params={"code": "auth-code", "state": "s"},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    listed = client.get("/api/accounts").json()
    assert len(listed) == 1
    assert listed[0]["email"] == "user1@example.com"
    assert listed[0]["status"] == "connected"
    assert listed[0]["grantedScopes"] == [
        "https://www.googleapis.com/auth/contacts.readonly"
    ]


def test_disconnect_account(client):
    client.get("/api/accounts/callback", params={"code": "c", "state": "s"},
               follow_redirects=False)
    account_id = client.get("/api/accounts").json()[0]["id"]
    assert client.delete(f"/api/accounts/{account_id}").status_code == 204
    assert client.get("/api/accounts").json() == []
