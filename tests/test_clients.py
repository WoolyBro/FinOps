from app.database import connect, next_counter, normalise_name
from app.tools.clients import create_client, find_client, list_clients, update_client


def call(t, **kw):
    """Invoke a Strands @tool directly, without going through an agent."""
    return t(**kw)


def test_normalise_name_collapses_case_and_whitespace():
    assert normalise_name("  Rahul   Sharma ") == "rahul sharma"
    assert normalise_name("RAHUL SHARMA") == "rahul sharma"


def test_create_then_find():
    created = call(create_client, name="Rahul Sharma", email="rahul@example.com")
    assert created["status"] == "created"
    assert created["client"]["name"] == "Rahul Sharma"

    found = call(find_client, name="Rahul Sharma")
    assert found["status"] == "found"
    assert found["client"]["client_id"] == created["client"]["client_id"]


def test_find_is_case_insensitive_and_partial():
    call(create_client, name="Rahul Sharma")
    assert call(find_client, name="rahul sharma")["status"] == "found"
    assert call(find_client, name="rahul")["status"] == "found"


def test_missing_client_is_reported_not_invented():
    result = call(find_client, name="Nobody")
    assert result["status"] == "not_found"
    assert "client" not in result


def test_duplicate_client_is_not_created_twice():
    first = call(create_client, name="ABC Studios")
    second = call(create_client, name="  abc   studios ")
    assert second["status"] == "already_exists"
    assert second["client"]["client_id"] == first["client"]["client_id"]
    assert call(list_clients)["count"] == 1


def test_ambiguous_match_asks_instead_of_guessing():
    call(create_client, name="Rahul Sharma")
    call(create_client, name="Rahul Verma")
    result = call(find_client, name="Rahul")
    assert result["status"] == "ambiguous"
    assert len(result["matches"]) == 2


def test_update_client_field():
    cid = call(create_client, name="Priya")["client"]["client_id"]
    updated = call(update_client, client_id=cid, field="email", value="p@example.com")
    assert updated["status"] == "updated"
    assert updated["client"]["email"] == "p@example.com"


def test_update_rejects_unknown_field():
    cid = call(create_client, name="Priya")["client"]["client_id"]
    result = call(update_client, client_id=cid, field="amount_owed", value="99999")
    assert result["status"] == "error"


def test_update_name_cannot_collide():
    call(create_client, name="Studio X")
    cid = call(create_client, name="Studio Y")["client"]["client_id"]
    result = call(update_client, client_id=cid, field="name", value="studio x")
    assert result["status"] == "error"


def test_empty_name_is_rejected():
    assert call(create_client, name="   ")["status"] == "error"
    assert call(find_client, name="")["status"] == "error"


def test_counter_increments_atomically(temp_db):
    conn = connect(temp_db)
    assert next_counter(conn, "invoice") == 1
    assert next_counter(conn, "invoice") == 2
    assert next_counter(conn, "receipt") == 1
    conn.commit()
    conn.close()
