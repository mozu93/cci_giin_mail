"""DB接続エラーをユーザー向けの文字列に整形するユーティリティ。

日本語Windows環境のPostgreSQLは既定でサーバーメッセージがCP932(Shift-JIS)で
返ってくることがあり、UTF-8前提のpsycopg2がそれを取り込む際に
UnicodeDecodeErrorを送出してしまい、本来のエラー内容が握りつぶされることがある。
その場合は生バイト列をCP932としてデコードし直し、実際のメッセージを救出する。
"""


def format_connection_error(e: Exception) -> str:
    if isinstance(e, UnicodeDecodeError):
        try:
            detail = e.object.decode("cp932", errors="replace")
        except Exception:
            detail = str(e)
        return (
            "サーバーからのエラーメッセージの文字コードが不正なため、"
            "詳細を正しく表示できません。\n"
            "（PostgreSQLサーバーのロケール設定が原因の可能性があります）\n\n"
            f"{detail}"
        )
    return str(e)
