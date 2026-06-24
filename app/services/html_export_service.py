"""出欠状況を自己完結型 HTML に書き出すサービス。"""
from datetime import datetime
from app.database.connection import get_session
from app.services.meeting_service import (
    get_meetings, get_attendance_data,
    get_reception_summary, get_summary,
)

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "Meiryo","Yu Gothic",sans-serif; background:#f8fafc; color:#1e293b; padding:16px; }
.container { max-width: 960px; margin: 0 auto; }
.page-title { font-size:1.4em; font-weight:bold; color:#1e40af;
  border-bottom:3px solid #2563eb; padding-bottom:8px; margin-bottom:16px; }
/* ナビゲーション */
.nav { background:white; border-radius:8px; box-shadow:0 1px 4px rgba(0,0,0,.08);
  padding:12px 16px; margin-bottom:20px; }
.nav-title { font-size:.8em; color:#64748b; font-weight:600; margin-bottom:8px; }
.nav-links { display:flex; flex-wrap:wrap; gap:8px; }
.nav-link { display:inline-block; padding:5px 12px; background:#eff6ff; color:#1e40af;
  border-radius:6px; font-size:.85em; text-decoration:none; border:1px solid #bfdbfe; }
.nav-link:hover { background:#dbeafe; }
.nav-link-past { background:#f8fafc; color:#64748b; border-color:#e2e8f0; }
.nav-link-past:hover { background:#f1f5f9; }
/* 会議ブロック */
.meeting { background:white; border-radius:8px;
  box-shadow:0 1px 4px rgba(0,0,0,.09); margin-bottom:24px; overflow:hidden;
  scroll-margin-top:16px; }
.meeting-header { background:#1e40af; color:white; padding:12px 16px; }
.meeting-name { font-size:1.1em; font-weight:bold; }
.meeting-meta { font-size:.85em; opacity:.85; margin-top:3px; }
.summary-block { padding:10px 16px; background:#f1f5f9; border-bottom:1px solid #e2e8f0; }
.summary-label { font-size:.75em; color:#64748b; margin-bottom:4px; font-weight:600; }
.badges { display:flex; flex-wrap:wrap; gap:6px; }
.badge { padding:3px 10px; border-radius:20px; font-size:.82em; font-weight:bold; }
.ba { background:#dcfce7; color:#166534; }
.bp { background:#dbeafe; color:#1e40af; }
.bd { background:#fef9c3; color:#854d0e; }
.bx { background:#fee2e2; color:#991b1b; }
.bn { background:#f1f5f9; color:#6b7280; border:1px solid #d1d5db; }
.bt { background:#1e40af; color:white; }
table { width:100%; border-collapse:collapse; font-size:.875em; }
th { background:#f8fafc; text-align:left; padding:7px 10px;
  border-bottom:2px solid #e2e8f0; color:#64748b; font-weight:600; white-space:nowrap; }
td { padding:6px 10px; border-bottom:1px solid #f1f5f9; vertical-align:middle; }
tr:last-child td { border-bottom:none; }
.chip { display:inline-block; padding:2px 8px; border-radius:10px;
  font-size:.8em; font-weight:bold; white-space:nowrap; }
.s-出席 { background:#dcfce7; color:#166534; }
.s-代理 { background:#dbeafe; color:#1e40af; }
.s-委任 { background:#fef9c3; color:#854d0e; }
.s-欠席 { background:#fee2e2; color:#991b1b; }
.s-未回答,.s-未受付,.s- { background:#f1f5f9; color:#9ca3af; }
.row-出席 { background:#f0fdf4; }
.row-代理 { background:#eff6ff; }
.row-委任 { background:#fefce8; }
.row-欠席 { background:#fff5f5; }
.proxy-info { color:#6b7280; font-size:.85em; }
.footer { text-align:right; color:#94a3b8; font-size:.78em; margin-top:16px; }
.no-meeting { color:#6b7280; padding:16px; text-align:center; }
@media (max-width:600px) {
  .col-h { display:none; }
  td, th { padding:5px 6px; font-size:.8em; }
}
"""

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>出欠状況</title>
<style>{css}</style>
</head>
<body>
<div class="container">
<h1 class="page-title">出欠状況</h1>
{body}
<p class="footer">更新: {timestamp}</p>
</div>
</body>
</html>
"""


def _esc(text: str) -> str:
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _badge_row(summary: dict) -> str:
    pending = summary.get("未受付", summary.get("未回答", 0))
    return (
        f'<span class="badge ba">出席 {summary["出席"]}</span>'
        f'<span class="badge bp">代理 {summary["代理"]}</span>'
        f'<span class="badge bd">委任 {summary["委任"]}</span>'
        f'<span class="badge bx">欠席 {summary["欠席"]}</span>'
        f'<span class="badge bn">未定 {pending}</span>'
        f'<span class="badge bt">合計 {summary["合計"]}</span>'
    )


def _meeting_html(meeting, attendance: list[dict],
                  pre_summary: dict, rec_summary: dict) -> str:
    scope = "全員" if not meeting.target_position_ids else "役職指定"
    date_str = meeting.date.strftime("%Y/%m/%d")
    anchor = f"meeting-{meeting.id}"

    rows_html = []
    for d in attendance:
        actual = d.get("actual_status") or ""
        effective = actual if actual else d["status"]
        row_cls = f"row-{effective}" if effective in ("出席", "代理", "委任", "欠席") else ""
        proxy_info = ""
        if d["status"] == "代理" or actual == "代理":
            proxy_info = " ".join(
                p for p in [_esc(d["proxy_title"]), _esc(d["proxy_name"])] if p)
        rows_html.append(
            f'<tr class="{row_cls}">'
            f'<td>{_esc(d["org_name"])}</td>'
            f'<td class="col-h">{_esc(d["position"])}</td>'
            f'<td>{_esc(d["name"])}</td>'
            f'<td><span class="chip s-{_esc(d["status"])}">{_esc(d["status"])}</span></td>'
            f'<td><span class="chip s-{_esc(actual)}">{_esc(actual) or "未受付"}</span></td>'
            f'<td class="proxy-info">{proxy_info}</td>'
            f'</tr>'
        )

    table_html = (
        '<table>'
        '<thead><tr>'
        '<th>事業所名</th>'
        '<th class="col-h">会議所役職</th>'
        '<th>氏名</th>'
        '<th>事前</th>'
        '<th>当日受付</th>'
        '<th>代理情報</th>'
        '</tr></thead>'
        f'<tbody>{"".join(rows_html)}</tbody>'
        '</table>'
    )

    return (
        f'<div class="meeting" id="{anchor}">'
        f'<div class="meeting-header">'
        f'<div class="meeting-name">{_esc(meeting.name)}</div>'
        f'<div class="meeting-meta">{date_str}　{scope}</div>'
        f'</div>'
        f'<div class="summary-block">'
        f'<div class="summary-label">事前</div>'
        f'<div class="badges">{_badge_row(pre_summary)}</div>'
        f'</div>'
        f'<div class="summary-block">'
        f'<div class="summary-label">当日受付</div>'
        f'<div class="badges">{_badge_row(rec_summary)}</div>'
        f'</div>'
        f'{table_html}'
        f'</div>'
    )


def _nav_html(upcoming, has_past: bool) -> str:
    if not upcoming and not has_past:
        return ""
    if len(upcoming) <= 1 and not has_past:
        return ""
    links = "".join(
        f'<a class="nav-link" href="#meeting-{m.id}">'
        f'{m.date.strftime("%m/%d")}　{_esc(m.name)}'
        f'</a>'
        for m in upcoming
    )
    if has_past:
        links += '<a class="nav-link nav-link-past" href="#past-meetings">過去の会議</a>'
    return (
        f'<div class="nav">'
        f'<div class="nav-title">会議一覧（クリックでジャンプ）</div>'
        f'<div class="nav-links">{links}</div>'
        f'</div>'
    )


def export_attendance_html(output_path: str) -> None:
    """全会議の出欠状況を HTML ファイルに書き出す。"""
    today = datetime.now().date()

    session = get_session()
    try:
        meetings = get_meetings(session)  # date降順
        upcoming, past = [], []
        for m in meetings:
            (past if m.date < today else upcoming).append(m)

        def _build(m):
            return _meeting_html(
                m,
                get_attendance_data(session, m.id),
                get_summary(session, m.id),
                get_reception_summary(session, m.id),
            )

        upcoming_blocks = [_build(m) for m in upcoming]
        past_blocks = [_build(m) for m in past]
    finally:
        session.close()

    parts = []
    if upcoming_blocks or past_blocks:
        parts.append(_nav_html(upcoming, bool(past_blocks)))
        parts.extend(upcoming_blocks)
        if past_blocks:
            inner = "\n".join(past_blocks)
            parts.append(
                f'<details id="past-meetings" style="margin-bottom:24px;">'
                f'<summary style="cursor:pointer; padding:10px 16px; '
                f'background:white; border-radius:8px; '
                f'box-shadow:0 1px 4px rgba(0,0,0,.08); '
                f'font-weight:bold; color:#64748b; list-style:none; '
                f'display:flex; align-items:center; gap:8px;">'
                f'<span style="font-size:1.1em;">▶</span>'
                f'過去の会議（{len(past_blocks)}件）'
                f'</summary>'
                f'<div style="margin-top:12px;">{inner}</div>'
                f'</details>'
            )
        body = "\n".join(parts)
    else:
        body = '<p class="no-meeting">会議データはありません。</p>'

    timestamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    html = _HTML_TEMPLATE.format(css=_CSS, body=body, timestamp=timestamp)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
