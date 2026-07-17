from app.ui.send_tab import _split_oversized_targets
from app.services.email_service import ATTACHMENT_SIZE_LIMIT_BYTES


def test_split_oversized_targets_separates_over_limit(tmp_path):
    small = tmp_path / "small.pdf"
    small.write_bytes(b"x" * 100)
    big = tmp_path / "big.pdf"
    big.write_bytes(b"y" * (ATTACHMENT_SIZE_LIMIT_BYTES + 1))

    targets = [
        {"org_name": "小さい会社", "attachments": [str(small)]},
        {"org_name": "大きい会社", "attachments": [str(big)]},
    ]
    ok, oversized = _split_oversized_targets(targets)
    assert [t["org_name"] for t in ok] == ["小さい会社"]
    assert [t["org_name"] for t in oversized] == ["大きい会社"]


def test_split_oversized_targets_empty_attachments_is_ok():
    targets = [{"org_name": "添付なし", "attachments": []}]
    ok, oversized = _split_oversized_targets(targets)
    assert len(ok) == 1
    assert oversized == []
