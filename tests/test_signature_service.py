from app.services.signature_service import (
    create_signature, update_signature, delete_signature,
    get_signatures, get_default_signature, set_default
)


def test_create_signature(db_session):
    sig = create_signature(db_session, "標準署名", "商工会議所")
    assert sig.id is not None
    assert not sig.is_default


def test_set_default_clears_others(db_session):
    sig1 = create_signature(db_session, "署名A", "本文A", is_default=True)
    sig2 = create_signature(db_session, "署名B", "本文B")
    set_default(db_session, sig2.id)
    default = get_default_signature(db_session)
    assert default.id == sig2.id
    db_session.refresh(sig1)
    assert not sig1.is_default


def test_get_default_returns_none_when_no_default(db_session):
    create_signature(db_session, "署名A", "本文A")
    assert get_default_signature(db_session) is None
