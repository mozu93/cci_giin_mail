from app.services.template_service import (
    create_template, update_template, delete_template,
    get_templates, get_template
)
from app.services.signature_service import create_signature
from app.services.staff_service import create_staff


def test_create_and_get_template(db_session):
    t = create_template(db_session, "総会案内", "総会のご案内", "本文テスト")
    assert t.id is not None
    fetched = get_template(db_session, t.id)
    assert fetched.name == "総会案内"


def test_create_template_with_signature(db_session):
    staff = create_staff(db_session, "水谷")
    sig = create_signature(db_session, "標準署名", "商工会議所\n担当：田中", staff.id)
    t = create_template(db_session, "総会案内", "件名", "本文", signature_id=sig.id)
    fetched = get_template(db_session, t.id)
    assert fetched.signature.name == "標準署名"


def test_update_template(db_session):
    t = create_template(db_session, "案内", "件名", "本文")
    update_template(db_session, t.id, subject="新件名")
    fetched = get_template(db_session, t.id)
    assert fetched.subject == "新件名"


def test_delete_template(db_session):
    t = create_template(db_session, "案内", "件名", "本文")
    delete_template(db_session, t.id)
    assert get_template(db_session, t.id) is None


def test_get_templates_returns_all(db_session):
    create_template(db_session, "案内1", "件名1", "本文1")
    create_template(db_session, "案内2", "件名2", "本文2")
    templates = get_templates(db_session)
    assert len(templates) == 2
