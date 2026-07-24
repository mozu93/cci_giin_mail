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
                      proxy_name: str = "", notes: str = "") -> AttendanceRecord:
    r = (session.query(AttendanceRecord)
         .filter_by(meeting_id=meeting_id, member_id=member_id)
         .first())
    if r is None:
        r = AttendanceRecord(meeting_id=meeting_id, member_id=member_id)
        session.add(r)
    r.status = status
    r.proxy_title = proxy_title
    r.proxy_name = proxy_name
    r.notes = notes
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
            "member_id":     m.id,
            "member_number": m.member_number,
            "org_name":      m.organization_name,
            "org_kana":      m.organization_kana or "",
            "title":         m.title or "",
            "name":          m.name,
            "position":      m.position.name if m.position else "",
            "status":        r.status if r else "未回答",
            "actual_status": (r.actual_status or "") if r else "",
            "proxy_title":   r.proxy_title if r else "",
            "proxy_name":    r.proxy_name if r else "",
        })
    return result


def update_actual_status(session: Session, meeting_id: int,
                         member_id: int, actual_status: str) -> None:
    """当日受付ステータスを更新する"""
    r = (session.query(AttendanceRecord)
         .filter_by(meeting_id=meeting_id, member_id=member_id)
         .first())
    if r is None:
        r = AttendanceRecord(meeting_id=meeting_id, member_id=member_id)
        session.add(r)
    r.actual_status = actual_status
    session.commit()


def get_reception_summary(session: Session, meeting_id: int) -> dict:
    """当日受付ステータス（actual_status）による集計"""
    data = get_attendance_data(session, meeting_id)
    counts: dict[str, int] = {"出席": 0, "代理": 0, "委任": 0, "欠席": 0, "未受付": 0}
    for d in data:
        s = d.get("actual_status") or ""
        if s in ("出席", "代理", "委任", "欠席"):
            counts[s] += 1
        else:
            counts["未受付"] += 1
    counts["合計"] = counts["出席"] + counts["代理"] + counts["委任"]
    return counts


def get_summary(session: Session, meeting_id: int) -> dict:
    data = get_attendance_data(session, meeting_id)
    counts: dict[str, int] = {"出席": 0, "代理": 0, "委任": 0, "欠席": 0, "未回答": 0}
    for d in data:
        s = d["status"]
        counts[s] = counts.get(s, 0) + 1
    counts["合計"] = counts["出席"] + counts["代理"] + counts["委任"]
    return counts


def is_meeting_past(meeting: Meeting) -> bool:
    """会議日を過ぎている（開催済み）かどうかを返す"""
    return date.today() > meeting.date


def get_member_ids_by_status(session: Session, meeting_id: int,
                             statuses: list[str]) -> set[int]:
    """指定した会議・ステータスに該当する会員IDのセットを返す。
    会議日より前は事前登録（status）、会議日を過ぎたら当日受付結果
    （actual_status）で判定する。ステータス未登録の会員は「未回答」として扱う。"""
    meeting = session.get(Meeting, meeting_id)
    if not meeting:
        return set()
    members = get_members(session, active_only=True)
    if meeting.target_position_ids:
        target_ids = set(json.loads(meeting.target_position_ids))
        members = [m for m in members if m.position_id in target_ids]
    records = {
        r.member_id: r
        for r in session.query(AttendanceRecord)
        .filter_by(meeting_id=meeting_id).all()
    }
    if is_meeting_past(meeting):
        return {
            m.id for m in members
            if (records[m.id].actual_status if m.id in records
                and records[m.id].actual_status else "未回答") in statuses
        }
    return {
        m.id for m in members
        if (records[m.id].status if m.id in records else "未回答") in statuses
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


_XLSX_HEADERS = ["No.", "役職", "事業所名", "所属役職", "氏名", "事前", "代理"]
_XLSX_FONT_SIZE = 10
# 列幅（ピクセル指定）。Excelの列幅（文字単位）へは (px - 5) / 7 で換算する
# （既定フォントCalibri 11・既定列幅8.43文字=64pxを基準とした変換式）。
_XLSX_COLUMN_WIDTHS_PX = [30, 45, 235, 129, 93, 45, 141]


def _px_to_excel_width(px: int) -> float:
    return round((px - 5) / 7, 2)


def export_xlsx(session: Session, meeting_id: int, filepath: str) -> None:
    """会議の出欠一覧をA4縦向き印刷向けに整形したExcelファイルに書き出す。
    行順は会員一覧の並び順（会議所役職順）に従う。行数が多い場合は
    自動的に複数ページに分かれて印刷される。"""
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter

    meeting = session.get(Meeting, meeting_id)
    data = get_attendance_data(session, meeting_id)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "出欠一覧"

    ws.append([meeting.name if meeting else ""])
    ws.cell(row=1, column=1).font = Font(bold=True, size=14)
    ws.append([meeting.date.strftime("%Y/%m/%d") if meeting else ""])
    ws.cell(row=2, column=1).font = Font(size=11, color="666666")
    ws.append([])

    header_row = 4
    ws.append(_XLSX_HEADERS)
    header_fill = PatternFill("solid", fgColor="1E40AF")
    header_font = Font(bold=True, color="FFFFFF", size=_XLSX_FONT_SIZE)
    thin = Side(style="thin", color="CCCCCC")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for col in range(1, len(_XLSX_HEADERS) + 1):
        c = ws.cell(row=header_row, column=col)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = border

    for i, d in enumerate(data, start=1):
        proxy_info = " ".join(p for p in [d["proxy_title"], d["proxy_name"]] if p)
        ws.append([
            i, d["position"], d["org_name"], d["title"], d["name"],
            d["status"], proxy_info,
        ])

    data_font = Font(size=_XLSX_FONT_SIZE)
    for row in ws.iter_rows(min_row=header_row + 1, max_row=ws.max_row,
                            max_col=len(_XLSX_HEADERS)):
        for cell in row:
            cell.border = border
            cell.font = data_font
            cell.alignment = Alignment(vertical="center", shrink_to_fit=True)
    for row_idx in range(header_row + 1, ws.max_row + 1):
        ws.cell(row=row_idx, column=1).alignment = Alignment(
            horizontal="center", vertical="center", shrink_to_fit=True)

    # 列幅は指定ピクセル値で固定し、はみ出す分はセル書式の
    # 「縮小して全体を表示」でフォントサイズを自動調整させる。
    for col, px in enumerate(_XLSX_COLUMN_WIDTHS_PX, start=1):
        ws.column_dimensions[get_column_letter(col)].width = _px_to_excel_width(px)

    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)

    # A4縦向き印刷設定：横幅は1ページに収め、行数が多い場合は縦方向に複数ページへ分割
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = f"{header_row}:{header_row}"
    ws.print_area = f"A1:{get_column_letter(len(_XLSX_HEADERS))}{ws.max_row}"
    ws.page_margins.left = 0.5
    ws.page_margins.right = 0.5
    ws.page_margins.top = 0.6
    ws.page_margins.bottom = 0.6
    ws.print_options.horizontalCentered = True

    wb.save(filepath)
