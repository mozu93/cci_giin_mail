import json
from app.database.models import (
    Position, Member, EmailAddress, MemberHistory,
    Signature, EmailTemplate, Staff, SendJob, SendLog
)


def test_create_position(db_session):
    pos = Position(name="会頭", sort_order=1)
    db_session.add(pos)
    db_session.commit()
    assert pos.id is not None
    assert pos.name == "会頭"


def test_create_member_with_emails(db_session):
    pos = Position(name="議員", sort_order=10)
    db_session.add(pos)
    db_session.flush()
    member = Member(
        member_number="A-001",
        position_id=pos.id,
        organization_name="○○商事",
        organization_kana="マルマルショウジ",
        title="代表取締役",
        name="山田 太郎",
        name_kana="ヤマダ タロウ",
    )
    db_session.add(member)
    db_session.flush()
    email1 = EmailAddress(member_id=member.id, address="yamada@example.com",
                          label="本人", sort_order=1)
    email2 = EmailAddress(member_id=member.id, address="somu@example.com",
                          label="総務", sort_order=2)
    db_session.add_all([email1, email2])
    db_session.commit()
    fetched = db_session.get(Member, member.id)
    assert fetched.organization_name == "○○商事"
    assert len(fetched.email_addresses) == 2
    assert fetched.email_addresses[0].address == "yamada@example.com"


def test_member_history_snapshot(db_session):
    member = Member(member_number="B-001", organization_name="△△産業", name="鈴木 花子")
    db_session.add(member)
    db_session.flush()
    snapshot = json.dumps(
        {"organization_name": "△△産業", "name": "鈴木 花子", "email_addresses": []},
        ensure_ascii=False
    )
    history = MemberHistory(
        member_id=member.id,
        changed_by="田中",
        change_reason="住所変更",
        snapshot=snapshot,
    )
    db_session.add(history)
    db_session.commit()
    fetched = db_session.get(Member, member.id)
    assert len(fetched.history) == 1
    assert fetched.history[0].change_reason == "住所変更"
    loaded = json.loads(fetched.history[0].snapshot)
    assert loaded["organization_name"] == "△△産業"


def test_template_with_signature(db_session):
    sig = Signature(name="標準署名", body="商工会議所\n担当：田中", is_default=True)
    db_session.add(sig)
    db_session.flush()
    tmpl = EmailTemplate(name="総会案内", subject="総会のご案内",
                         body="本文テスト", signature_id=sig.id)
    db_session.add(tmpl)
    db_session.commit()
    fetched = db_session.get(EmailTemplate, tmpl.id)
    assert fetched.signature.name == "標準署名"


def test_send_job_with_logs(db_session):
    staff = Staff(name="田中")
    template = EmailTemplate(name="総会案内", subject="総会のご案内", body="本文")
    db_session.add_all([staff, template])
    db_session.flush()
    job = SendJob(
        name="2026年6月 総会案内",
        template_id=template.id,
        staff_id=staff.id,
        status="done",
        total_count=2,
        success_count=1,
        error_count=1,
    )
    db_session.add(job)
    db_session.flush()
    log1 = SendLog(job_id=job.id, to_address="a@example.com",
                   subject="総会のご案内", status="success")
    log2 = SendLog(job_id=job.id, to_address="b@example.com",
                   subject="総会のご案内", status="error",
                   error_message="接続タイムアウト")
    db_session.add_all([log1, log2])
    db_session.commit()
    fetched = db_session.get(SendJob, job.id)
    assert len(fetched.logs) == 2
    error_logs = [l for l in fetched.logs if l.status == "error"]
    assert error_logs[0].error_message == "接続タイムアウト"


def test_email_address_cascade_delete(db_session):
    member = Member(member_number="C-001", organization_name="□□工業", name="佐藤 次郎")
    db_session.add(member)
    db_session.flush()
    email = EmailAddress(member_id=member.id, address="sato@example.com",
                         label="本人", sort_order=1)
    db_session.add(email)
    db_session.commit()
    db_session.delete(member)
    db_session.commit()
    remaining = db_session.query(EmailAddress).filter_by(member_id=member.id).all()
    assert len(remaining) == 0
