from datetime import date, datetime, timedelta
from app.database.models import Member
from app.services.meeting_service import (
    create_meeting, upsert_attendance, update_actual_status,
    get_member_ids_by_status,
)


def _add_member(session, member_number, name="テスト太郎"):
    # created_atを固定の過去日にし、会議日をまたぐ「入会日フィルタ」の
    # 影響を受けずにステータス判定ロジックだけを検証できるようにする
    m = Member(member_number=member_number, organization_name="テスト会社", name=name,
              created_at=datetime(2000, 1, 1))
    session.add(m)
    session.commit()
    return m


def test_status_filter_unanswered_uses_pre_entry_status(db_session):
    """「未回答」は当日受付結果に関わらず、事前登録のステータスを参照する。"""
    m1 = _add_member(db_session, "A-001")  # 事前登録は出席済み
    m2 = _add_member(db_session, "A-002")  # 事前未登録（当日受付のみ入力済み）
    meeting = create_meeting(db_session, "定例会", date.today() + timedelta(days=7))

    upsert_attendance(db_session, meeting.id, m1.id, "出席")
    update_actual_status(db_session, meeting.id, m2.id, "出席")

    result = get_member_ids_by_status(db_session, meeting.id, ["未回答"])
    assert result == {m2.id}


def test_status_filter_attendance_statuses_use_actual_status(db_session):
    """出席・代理・委任・欠席は、事前登録に関わらず当日受付結果を参照する。"""
    m1 = _add_member(db_session, "A-001")  # 事前は出席だが当日受付は未処理
    m2 = _add_member(db_session, "A-002")  # 当日受付で出席と記録
    meeting = create_meeting(db_session, "定例会", date.today() + timedelta(days=7))

    upsert_attendance(db_session, meeting.id, m1.id, "出席")
    update_actual_status(db_session, meeting.id, m2.id, "出席")

    result = get_member_ids_by_status(db_session, meeting.id, ["出席"])
    assert result == {m2.id}


def test_status_filter_source_ignores_meeting_past_or_future(db_session):
    """未回答→事前登録、それ以外→当日受付という参照ルールは
    会議日が過去でも同じであること。"""
    m1 = _add_member(db_session, "A-001")  # 事前は出席だが当日受付は未処理
    m2 = _add_member(db_session, "A-002")  # 当日受付で欠席と記録
    meeting = create_meeting(db_session, "定例会", date.today() - timedelta(days=1))

    upsert_attendance(db_session, meeting.id, m1.id, "出席")
    update_actual_status(db_session, meeting.id, m2.id, "欠席")

    assert get_member_ids_by_status(db_session, meeting.id, ["未回答"]) == {m2.id}
    assert get_member_ids_by_status(db_session, meeting.id, ["欠席"]) == {m2.id}
    assert get_member_ids_by_status(db_session, meeting.id, ["出席"]) == set()


def test_status_filter_combines_unanswered_and_actual_statuses(db_session):
    """複数ステータスを同時に選択した場合、それぞれ対応するデータ源で判定される。"""
    m1 = _add_member(db_session, "A-001")  # 未回答のまま
    m2 = _add_member(db_session, "A-002")  # 当日受付で欠席と記録
    meeting = create_meeting(db_session, "定例会", date.today() + timedelta(days=7))

    update_actual_status(db_session, meeting.id, m2.id, "欠席")

    result = get_member_ids_by_status(db_session, meeting.id, ["未回答", "欠席"])
    assert result == {m1.id, m2.id}
