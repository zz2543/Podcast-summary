from podsum.services.audio_digest_script import _language_instruction


def test_audio_digest_language_follows_video() -> None:
    assert "Chinese" in _language_instruction("zh")
    assert "English" in _language_instruction("en")
    assert "original language mix" in _language_instruction("mixed")
