from sqlalchemy.orm import Session
from app.services.member_service import get_members

_HEADERS = [
    "会員番号", "事業所名", "事業所名フリガナ", "役職名", "氏名", "氏名フリガナ", "会議所役職",
    "メール1アドレス", "メール1ラベル",
    "メール2アドレス", "メール2ラベル",
    "メール3アドレス", "メール3ラベル",
    "メール4アドレス", "メール4ラベル",
    "メール5アドレス", "メール5ラベル",
]


def _build_row(member) -> list:
    emails = {ea.sort_order: ea for ea in member.email_addresses}
    row = [
        member.member_number,
        member.organization_name,
        member.organization_kana or "",
        member.title or "",
        member.name,
        member.name_kana or "",
        member.position.name if member.position else "",
    ]
    for n in range(1, 6):
        ea = emails.get(n)
        row.append(ea.address if ea else "")
        row.append(ea.label if ea else "")
    return row


def export_members_xlsx(session: Session, filepath: str) -> int:
    import openpyxl
    members = get_members(session, active_only=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "名簿"
    ws.append(_HEADERS)
    for m in members:
        ws.append(_build_row(m))
    wb.save(filepath)
    return len(members)


def export_members_csv(session: Session, filepath: str) -> int:
    import csv
    members = get_members(session, active_only=True)
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(_HEADERS)
        for m in members:
            writer.writerow(_build_row(m))
    return len(members)
