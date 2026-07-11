from app.services.signature_service import (
    create_signature, update_signature, delete_signature,
    get_signatures, get_default_signature, set_default
)
from app.services.staff_service import create_staff


def test_create_signature_requires_staff_id(db_session):
    staff = create_staff(db_session, "水谷")
    sig = create_signature(db_session, "標準署名", "商工会議所", staff.id)
    assert sig.id is not None
    assert sig.staff_id == staff.id
    assert not sig.is_default


def test_get_signatures_only_returns_own_staff(db_session):
    staff_a = create_staff(db_session, "水谷")
    staff_b = create_staff(db_session, "山田")
    create_signature(db_session, "水谷の署名", "本文A", staff_a.id)
    create_signature(db_session, "山田の署名", "本文B", staff_b.id)

    result = get_signatures(db_session, staff_a.id)
    assert [s.name for s in result] == ["水谷の署名"]


def test_set_default_clears_others_within_same_staff_only(db_session):
    staff_a = create_staff(db_session, "水谷")
    staff_b = create_staff(db_session, "山田")
    sig1 = create_signature(db_session, "署名A", "本文A", staff_a.id, is_default=True)
    sig2 = create_signature(db_session, "署名B", "本文B", staff_a.id)
    sig_other = create_signature(db_session, "署名C", "本文C", staff_b.id, is_default=True)

    set_default(db_session, sig2.id, staff_a.id)

    default_a = get_default_signature(db_session, staff_a.id)
    assert default_a.id == sig2.id
    db_session.refresh(sig1)
    assert not sig1.is_default

    db_session.refresh(sig_other)
    assert sig_other.is_default, "他の担当者のデフォルトには影響しないこと"


def test_get_default_returns_none_when_no_default(db_session):
    staff = create_staff(db_session, "水谷")
    create_signature(db_session, "署名A", "本文A", staff.id)
    assert get_default_signature(db_session, staff.id) is None
