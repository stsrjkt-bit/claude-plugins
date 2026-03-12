"""共通ハッシュモジュール — TTS 音声キャッシュのキー生成。

ローカル (gemini_tts_service.py) と Modal (modal_manim_app.py) の両方で使い、
同一ハッシュ関数を保証する。
"""

import hashlib

from manim_voiceover.helper import remove_bookmarks


def normalize_voice_text(text: str) -> str:
    """ブックマークタグを除去してプレーンテキストにする。"""
    return remove_bookmarks(text)


def voice_cache_key(text: str, *, voice: str, version: str = "v1") -> str:
    """ナレーションテキスト + voice 名からキャッシュキーを生成する。

    Returns:
        SHA256 先頭32文字の hex 文字列
    """
    normalized = normalize_voice_text(text)
    seed = f"{version}|{voice}|{normalized}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]
