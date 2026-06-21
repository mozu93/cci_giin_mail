import csv
import json
from datetime import date
from sqlalchemy.orm import Session
from app.database.models import Meeting, AttendanceRecord
from app.services.member_service import get_members

STATUS_OPTIONS = ["未回答", "出席", "代理", "委任", "欠席"]


def create_meeting(session: Session, name: str, meeting_date: date,
                   target_position_ids: list[int] | None = None) -> Meeting:
    ids_json = json.dumps(target_position_ids) if target_position_ids else None
    m = Meeting(name=name, date=meeting_date, target_position_ids=ids_json)
    session.add(m)
    session.commit()
    return m


def get_meetings(session: Session) -> list[Meeting]:
    return session.query(Meeting).order_by(Meeting.date.desc(), Meeting.id.desc()).all()


def delete_meeting(session: Session, meeting_id: int) -> None:
    m = session.get(Meeting, meeting_id)
    if m:
        session.delete(m)
        session.commit()


def upsert_attendance(session: Session, meeting_id: int, member_id: int,
                      status: str, proxy_title: str = "",
                      proxy_name: str = "") -> AttendanceRecord:
    r = (session.query(AttendanceRecord)
         .filter_by(meeting_id=meeting_id, member_id=member_id)
         .first())
    if r is None:
        r = AttendanceRecord(meeting_id=meeting_id, member_id=member_id)
        session.add(r)
    r.status = status
    r.proxy_title = proxy_title
    r.proxy_name = proxy_name
    session.commit()
    return r


def get_attendance_data(session: Session, meeting_id: int) -> list[dict]:
    """対象会員の出欠データをdictリストで返す（レコード未作成は未回答）"""
    meeting = session.get(Meeting, meeting_id)
    members = get_members(session, active_only=True)
    if meeting and meeting.target_position_ids:
        target_ids = set(json.loads(meeting.target_position_ids))
        members = [m for m in members if m.position_id in target_ids]
    records = {
        r.member_id: r
        for r in session.query(AttendanceRecord)
        .filter_by(meeting_id=meeting_id).all()
    }
    result = []
    for m in members:
        r = records.get(m.id)
        result.append({
            "member_id":    m.id,
            "member_number": m.member_number,
            "org_name":     m.organization_name,
            "org_kana":     m.organization_kana or "",
            "title":        m.title or "",
            "name":         m.name,
            "position":     m.position.name if m.position else "",
            "status":       r.status if r else "未回答",
            "proxy_title":  r.proxy_title if r else "",
            "proxy_name":   r.proxy_name if r else "",
        })
    return result


def get_summary(session: Session, meeting_id: int) -> dict:
    data = get_attendance_data(session, meeting_id)
    counts: dict[str, int] = {"出席": 0, "代理": 0, "委任": 0, "欠席": 0, "未回答": 0}
    for d in data:
        s = d["status"]
        counts[s] = counts.get(s, 0) + 1
    counts["合計"] = counts["出席"] + counts["代理"] + counts["委任"]
    return counts


def get_member_ids_by_status(session: Session, meeting_id: int,
                             statuses: list[str]) -> set[int]:
    """指定した会議・ステータスに該当する会員IDのセットを返す。
    ステータス未登録の会員は「未回答」として扱う。"""
    meeting = session.get(Meeting, meeting_id)
    if not meeting:
        return set()
    members = get_members(session, active_only=True)
    if meeting.target_position_ids:
        target_ids = set(json.loads(meeting.target_position_ids))
        members = [m for m in members if m.position_id in target_ids]
    records = {
        r.member_id: r.status
        for r in session.query(AttendanceRecord)
        .filter_by(meeting_id=meeting_id).all()
    }
    return {
        m.id for m in members
        if records.get(m.id, "未回答") in statuses
    }


def export_csv(session: Session, meeting_id: int, filepath: str) -> None:
    meeting = session.get(Meeting, meeting_id)
    data = get_attendance_data(session, meeting_id)
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["会議名", meeting.name if meeting else ""])
        writer.writerow(["会員番号", "事業所名", "会議所役職", "氏名",
                         "ステータス", "代理役職名", "代理氏名"])
        for d in data:
            writer.writerow([
                d["member_number"], d["org_name"], d["position"], d["name"],
                d["status"], d["proxy_title"], d["proxy_name"],
            ])
