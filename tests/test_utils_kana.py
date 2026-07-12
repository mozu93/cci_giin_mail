from app.utils import to_hankaku_kana


def test_to_hankaku_kana_converts_seion():
    assert to_hankaku_kana("ヨッカイチ") == "ﾖｯｶｲﾁ"


def test_to_hankaku_kana_converts_dakuon():
    assert to_hankaku_kana("スズキジロウ") == "ｽｽﾞｷｼﾞﾛｳ"


def test_to_hankaku_kana_converts_handakuon():
    assert to_hankaku_kana("パピプペポ") == "ﾊﾟﾋﾟﾌﾟﾍﾟﾎﾟ"


def test_to_hankaku_kana_converts_fullwidth_space():
    assert to_hankaku_kana("ヤマダ　タロウ") == "ﾔﾏﾀﾞ ﾀﾛｳ"


def test_to_hankaku_kana_converts_hiragana_input():
    assert to_hankaku_kana("よっかいち") == "ﾖｯｶｲﾁ"


def test_to_hankaku_kana_is_idempotent_on_existing_halfwidth():
    assert to_hankaku_kana("ﾖｯｶｲﾁｼｮｳｶｲ") == "ﾖｯｶｲﾁｼｮｳｶｲ"


def test_to_hankaku_kana_leaves_non_kana_untouched():
    assert to_hankaku_kana("ABC-123") == "ABC-123"
