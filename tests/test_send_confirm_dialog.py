from app.ui.dialogs.send_confirm_dialog import format_recipient_details


def test_format_recipient_details_lists_every_recipient():
    text = format_recipient_details([{
        "org_name": "A社",
        "to_address": "to@example.com",
        "cc_addresses": ["cc1@example.com", "cc2@example.com"],
        "bcc_addresses": ["bcc@example.com"],
        "attachments": ["C:/files/A001_請求書.pdf"],
    }])

    assert "【A社】" in text
    assert "To: to@example.com" in text
    assert "CC: cc1@example.com, cc2@example.com" in text
    assert "BCC: bcc@example.com" in text
    assert "添付: A001_請求書.pdf" in text


def test_format_recipient_details_lists_originals_in_test_mode():
    text = format_recipient_details([{
        "org_name": "A社",
        "to_address": "tester@example.com",
        "cc_addresses": [],
        "bcc_addresses": [],
        "original_to_address": "real@example.com",
        "original_cc_addresses": ["real-cc@example.com"],
        "original_bcc_addresses": ["real-bcc@example.com"],
    }])

    assert "To: tester@example.com" in text
    assert "本来のTo: real@example.com" in text
    assert "本来のCC: real-cc@example.com" in text
    assert "本来のBCC: real-bcc@example.com" in text
