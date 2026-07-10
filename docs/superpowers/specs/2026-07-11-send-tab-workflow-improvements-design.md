# 送信タブ ワークフロー改善 設計書

**作成日：** 2026-07-11
**ステータス：** 承認済み

---

## 1. 概要

送信タブ（`app/ui/send_tab.py`）の使い勝手を改善する。対象は以下の7点。

1. Step1「宛先条件」に「名簿から選択」モードを追加し、デフォルトにする
2. Step2「テンプレート・署名選択」にプレースホルダー挿入ボタンと「テンプレートとして保存」ボタンを追加する
3. Step3「差し込みデータ」を通常運用では非表示にする（仕組みは温存し、開発者フラグで復活可能にする）
4. Step4「添付ファイル」を使用時のみ展開表示にし、個別添付ファイルのファイル名マッチングをワイルドカード対応にする
5. Step5「最終確認・送信」のテスト送信ボタンに設定済みテスト送信先アドレスを表示する
6. 上記2・3の結果、表示されるセクションの構成が変わるため、ステップ番号を動的に採番する
7. テンプレートタブ（`app/ui/template_tab.py`）のプレースホルダーを送信タブと統一する

サービス層・DBスキーマの変更は行わない。UI層（`send_tab.py`、`template_tab.py`、`app/ui/dialogs/attach_confirm_dialog.py`）への局所的な変更に限定する。既存の実装パターン（`_SignatureWidget`のプレースホルダー実装、`settings_tab.py`の開発者フラグ`CCI_MAIL_DEV_TOOLS`、`inline_status.show_inline_message`によるインライン保存通知）を踏襲する。

---

## 2. Step1：「名簿から選択」モードの追加

### 2.1 UI変更

`_build_step1()`に4つ目の`QRadioButton`「名簿から選択」（`_rb_by_list`）を追加し、既存の`QButtonGroup`に加える。

- チェック時：`_pos_panel` / `_committee_panel` / `_attend_panel`をすべて非表示にする。自動フィルタは行わず、右側の`RecipientPanel`から手動でチェックする（既存の「表示中を全選択/全解除」ボタンを利用）。
- デフォルトのチェック状態を`_rb_by_pos.setChecked(True)`から`_rb_by_list.setChecked(True)`に変更する。

### 2.2 `_on_mode_change`の変更

既存の3モードと同様に扱う。モード切替時は常に`self._recipient.clear_checks()`を呼ぶ既存の統一動作を維持する（「名簿から選択」への切替時も例外にしない）。

---

## 3. Step2：プレースホルダー挿入とテンプレート登録

### 3.1 プレースホルダー挿入ボタン

`template_tab.py`の`_PLACEHOLDERS`と同じ仕組みを`send_tab.py`にも導入する。

```python
_BASE_PLACEHOLDERS = ["{事業所名}", "{役職名}", "{氏名}", "{会議所役職名}"]
_MERGE_PLACEHOLDERS = ["{col1}", "{col2}", "{col3}", "{col4}", "{col5}"]


def _dev_tools_enabled() -> bool:
    return os.environ.get("CCI_MAIL_DEV_TOOLS") == "1"
```

`_build_step2()`にプレースホルダー行を追加する。`_dev_tools_enabled()`が`True`の場合のみ`_MERGE_PLACEHOLDERS`も表示する（Step3の表示可否と連動）。クリック時は`_body_edit`のカーソル位置に挿入する（`template_tab._insert_placeholder`と同じ実装）。

### 3.2 「テンプレートとして保存」ボタン

`_build_step2()`に「テンプレートとして保存」ボタンと、保存完了を示す`self._step2_status_label`（`QLabel`）を追加する。

挙動：

- `self._template_combo.currentData()`が既存テンプレートID（Noneでない）の場合：確認ダイアログ「テンプレート「{name}」を上書き保存しますか？」を表示（`QMessageBox.question`、既定ボタンNo）。Yesなら`update_template(session, tmpl_id, name=name, subject=subject, body=body, signature_id=sig_id)`で上書き。
- 選択なし（None）の場合：`QInputDialog.getText`でテンプレート名を入力させ、入力があれば`create_template(session, name, subject, body, signature_id=sig_id)`で新規作成。
- 件名・本文が空の場合は`QMessageBox.warning`で保存を中止する（`template_tab._save`と同じバリデーション）。
- 保存後、`_load_combos()`でテンプレート一覧を再読込し、保存したテンプレートを`_template_combo`で選択状態にする。保存完了は`show_inline_message(self._step2_status_label, "テンプレートを保存しました")`で通知する。

---

## 4. Step3：差し込みデータの非表示化（仕組みは温存）

### 4.1 方針

`_build_step3()`（差し込みデータ）のGroupBox自体・`_import_merge()`・`MergePreviewDialog`・`_merge_data` / `_col_labels`属性・`compile_send_targets()`への`merge_data` / `col_labels`引数・`email_service.py`の`{col1}`〜`{col5}`置換ロジックは一切変更しない。

`_build_left_column()`で、`_dev_tools_enabled()`が`True`の場合のみStep3のGroupBoxをレイアウトに追加する。`False`の場合は`_build_step3()`自体を呼ばない（`_merge_data` / `_col_labels`は初期値の空のまま`_build_targets()`に渡され、既存の空データ時の挙動——col1〜5が空文字になる——がそのまま適用される）。

### 4.2 ステップ番号の動的採番

各セクション構築メソッドは、番号を含まないタイトルでGroupBoxを返すよう変更する。

- `_build_step1() -> "宛先条件"`
- `_build_step2() -> "テンプレート・署名選択"`
- `_build_merge_section() -> "差し込みデータ（任意）"`（旧`_build_step3`をリネーム）
- `_build_attach_section() -> "添付ファイル（任意）"`（旧`_build_step4`をリネーム）
- `_build_final_section() -> "最終確認・送信"`（旧`_build_step5`をリネーム）

`_build_left_column()`で表示するセクションのリストを組み立てた後、先頭から`grp.setTitle(f"Step {i}：{grp.title()}")`で番号を振り直してから`layout.addWidget(grp)`する。

```python
def _build_left_column(self) -> QScrollArea:
    ...
    sections = [self._build_step1(), self._build_step2()]
    if self._dev_tools_enabled():
        sections.append(self._build_merge_section())
    sections.append(self._build_attach_section())
    sections.append(self._build_final_section())
    for i, grp in enumerate(sections, 1):
        grp.setTitle(f"Step {i}：{grp.title()}")
        layout.addWidget(grp)
    ...
```

結果：通常運用ではStep1〜4（差し込みデータなし）、`CCI_MAIL_DEV_TOOLS=1`時はStep1〜5（差し込みデータがStep3として復活）。

---

## 5. Step4：添付ファイルの展開表示とワイルドカードマッチング

### 5.1 使用時のみ展開

`_build_attach_section()`（旧`_build_step4`）の先頭にチェックボックス「添付ファイルを使用する」（`self._chk_use_attach`）を追加する。

- 未チェック時：既存の添付ファイル関連ウィジェット一式を内包する`QWidget`（`self._attach_body`）を非表示にする。
- チェック時：`self._attach_body`を表示する。
- チェックを外しても、読み込み済みの共通添付ファイル・個別フォルダ設定・突合結果（`_common_attachments` / `_individual_folder` / `_attach_list`）は破棄しない（再度チェックすれば設定内容がそのまま表示される）。
- `_clear_all()`で`self._chk_use_attach.setChecked(False)`も追加する。

### 5.2 ワイルドカードマッチング

`_check_matching()`のファイル突合ロジックを、`os.path.exists(fpath)`による完全一致チェックから、`glob.glob()`によるパターン検索に変更する。

```python
import glob

def _check_matching(self):
    ...
    rule = self._rule_edit.text().strip()
    attach_list = []
    for m in members:
        to_addr = ...
        pattern = os.path.join(
            self._individual_folder,
            rule.replace("{会員番号}", glob.escape(m.member_number)))
        matched = sorted(glob.glob(pattern))
        attach_list.append({
            "member_number": m.member_number,
            "org_name":      m.organization_name,
            "to_address":    to_addr,
            "filepaths":     matched,
            "found":         len(matched) > 0,
        })
    ...
```

- `{会員番号}`部分のみ`glob.escape()`でエスケープし、ルール文字列中の`*` / `?`はワイルドカードとして機能させる。
- デフォルトのファイル名ルールを`{会員番号}.pdf`から`{会員番号}_*.pdf`に変更する（`self._rule_edit = QLineEdit("{会員番号}_*.pdf")`）。ツールチップも「{会員番号}の直後にアンダースコアを挟んだ命名を推奨。例：A001_請求書.pdf、A001_確認書_○○商事.pdf」に更新する。
- 1件のパターンに複数ファイルが一致した場合は全てまとめて添付する。

### 5.3 データ構造の変更

`attach_list`の各要素を`filepath`（単数）から`filepaths`（リスト）に変更する。影響箇所：

- `_build_targets()`の`attach_map`構築：
  ```python
  attach_map: dict[str, list[str]] = {
      r["member_number"]: r["filepaths"]
      for r in self._attach_list if r["found"]
  }
  ```
  （`email_service.py`の`compile_send_targets`は既に`attach_map.get(m.member_number, [])`という会員番号ごとの複数ファイルリストを前提とした作りのため、サービス層の変更は不要）
- `app/ui/dialogs/attach_confirm_dialog.py`：一覧表示を`filepath`単数列から`filepaths`（複数ファイルは改行またはカンマ区切りで列挙）に変更する。

---

## 6. Step5：テスト送信ボタンへのアドレス表示

`_build_final_section()`（旧`_build_step5`）で、テスト送信ボタンのラベルを動的にする。

```python
def _update_test_button_label(self):
    graph_config = get_graph_config()
    addr = graph_config.get("test_address")
    self._btn_test.setText(f"{addr} にテスト送信" if addr else "テスト送信（未設定）")
```

- 初回構築時と、`refresh()`（タブ切替時に`MainWindow`から呼ばれる既存メソッド）の両方で`_update_test_button_label()`を呼び、設定タブでの変更を反映する。
- 未設定時にボタンを押した場合の挙動（`QMessageBox.warning`で設定タブへの誘導）は変更しない。

---

## 7. テンプレートタブの修正

`app/ui/template_tab.py`の`_PLACEHOLDERS`定義を、送信タブと同じ開発者フラグで制御する。

```python
_BASE_PLACEHOLDERS = ["{事業所名}", "{役職名}", "{氏名}", "{会議所役職名}"]
_MERGE_PLACEHOLDERS = ["{col1}", "{col2}", "{col3}", "{col4}", "{col5}"]

_PLACEHOLDERS = _BASE_PLACEHOLDERS + (
    _MERGE_PLACEHOLDERS if os.environ.get("CCI_MAIL_DEV_TOOLS") == "1" else [])
```

通常運用では差し込みデータの仕組み自体が使われないため、テンプレート編集時に`{col1}`〜`{col5}`のボタンを表示しない。既存テンプレートの本文に`{col1}`等が含まれていても動作・表示に影響はない（あくまで挿入ボタンの表示可否のみの変更）。

---

## 8. テスト方針

既存パターン（pytest + pytest-qt、`monkeypatch`でサービス関数を差し替え）に従う。

- `tests/test_send_tab_list_mode.py`（新規）：「名簿から選択」モードがデフォルトでチェックされていること、選択時に自動フィルタパネルが非表示になること
- `tests/test_send_tab_placeholder.py`（新規）：Step2のプレースホルダー挿入ボタンで本文にテキストが挿入されること、開発者フラグOFF時は`{col1}`等のボタンが存在しないこと
- `tests/test_send_tab_save_template.py`（新規）：新規保存・上書き保存の分岐（`monkeypatch`で`create_template` / `update_template`を差し替えて呼び出し引数を検証）
- `tests/test_send_tab_step_numbering.py`（新規）：開発者フラグOFF/ON時のGroupBoxタイトルの採番が期待通りであること
- `tests/test_send_tab_attach_toggle.py`（新規）：チェックボックスでの添付セクションの表示/非表示切り替え
- `tests/test_send_tab_wildcard_match.py`（新規）：`tmp_path`にダミーファイル（`A001_請求書.pdf`、`A001_確認書_org.pdf`、`A002.pdf`等）を作成し、`_check_matching`相当のロジックが会員番号ごとに正しくファイルを突合すること（複数一致・0件一致の両方を検証）
- `tests/test_send_tab_test_button_label.py`（新規）：`get_graph_config`の`test_address`有無でボタンラベルが切り替わること
- `tests/test_template_tab_placeholder_flag.py`（新規）：開発者フラグOFF/ONで`_PLACEHOLDERS`に`{col1}`等が含まれるかどうか

---

## 9. スコープ外

- Step3（差し込みデータ）自体の機能改善・UI変更（今回は非表示化のみ。仕組みは既存のまま）
- 添付ファイルの個別プレビュー（ワイルドカードマッチングは一覧確認ダイアログでの表示改善に留める）
- テスト送信先アドレス自体の複数登録・履歴管理（設定タブの既存の単一`test_address`のまま）
- `CCI_MAIL_DEV_TOOLS`フラグのON/OFFをUIから切り替える機能（環境変数のままとする）
