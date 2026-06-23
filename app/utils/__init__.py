import unicodedata


def to_katakana(text: str) -> str:
    """ひらがな・半角カタカナを全角カタカナに統一して返す"""
    text = unicodedata.normalize("NFKC", text)
    return "".join(
        chr(ord(ch) + 0x60) if 0x3041 <= ord(ch) <= 0x3096 else ch
        for ch in text
    )
