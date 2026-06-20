"""Contract of the PeopleClient seam (pagination + sync token on last page only).

The live GooglePeopleClient error mapping (429->RateLimited, 401/403->Auth, 5xx->Transient) is
exercised by the import_runner integration tests via injected errors; this verifies the page
contract the worker relies on so CI never needs live Google (Principle IV).
"""
from src.integrations.people_client import ConnectionsPage
from tests.fakes.fake_people_client import FakePeopleClient, make_person


def test_pagination_yields_all_and_sync_token_on_last_page():
    people = [make_person(i) for i in range(5)]
    client = FakePeopleClient(people, page_size=2)

    collected: list[dict] = []
    token = None
    pages = 0
    sync_token = None
    while True:
        page = client.list_connections(token)
        assert isinstance(page, ConnectionsPage)
        collected.extend(page.people)
        pages += 1
        if page.next_page_token is None:
            sync_token = page.next_sync_token
            break
        # sync token must only appear on the final page
        assert page.next_sync_token is None
        token = page.next_page_token

    assert [p["resourceName"] for p in collected] == [f"people/c{i}" for i in range(5)]
    assert pages == 3
    assert sync_token == "SYNC123"


def test_total_estimate_exposed():
    client = FakePeopleClient([make_person(i) for i in range(4)], page_size=2)
    page = client.list_connections(None)
    assert page.total_estimate == 4
