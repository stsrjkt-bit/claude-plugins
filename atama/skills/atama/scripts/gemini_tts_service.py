"""Gemini TTS service for manim-voiceover.

2つのモードで動作:
- API モード (デフォルト): Gemini TTS API で音声生成
- Lookup モード (lookup_dir指定): 事前生成された WAV をファイル名で検索するだけ（Modal側で使用）
"""

import os
import sys
import wave
from pathlib import Path

from manim_voiceover.helper import remove_bookmarks
from manim_voiceover.services.base import SpeechService

from voice_hash import voice_cache_key


class GeminiTTSService(SpeechService):
    def __init__(
        self,
        voice_name="Kore",
        prompt_prefix="優しく教える数学の先生として、自然に読んでください: ",
        lookup_dir: str | None = None,
        allow_api: bool = True,
        **kwargs,
    ):
        SpeechService.__init__(self, **kwargs)
        self.voice_name = voice_name
        self.prompt_prefix = prompt_prefix
        self.lookup_dir = lookup_dir
        self.allow_api = allow_api

        # lookup-only モード: API 初期化不要
        if lookup_dir and not allow_api:
            self.client = None
            self.tts_model = None
            return

        # env から API キー + TTS モデル名読み込み
        env_path = os.path.expanduser("~/studygram/.env")
        env_vars = {}
        try:
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env_vars[k] = v.strip('"').strip("'")
        except FileNotFoundError:
            raise RuntimeError(f"{env_path} が見つかりません")

        from google import genai

        api_key = env_vars.get("GEMINI_API_KEY")
        self.tts_model = env_vars.get("GEMINI_TTS_MODEL")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY が未設定です")
        if not self.tts_model:
            raise RuntimeError("GEMINI_TTS_MODEL が未設定です")

        self.client = genai.Client(api_key=api_key)

    def _lookup_wav(self, text: str) -> str | None:
        """lookup_dir 内でキャッシュキーに一致する WAV を探す。"""
        if not self.lookup_dir:
            return None
        key = voice_cache_key(text, voice=self.voice_name)
        wav_path = Path(self.lookup_dir) / f"{key}.wav"
        if wav_path.exists():
            return str(wav_path)
        return None

    def generate_from_text(
        self, text: str, cache_dir: str = None, path: str = None, **kwargs
    ) -> dict:
        if cache_dir is None:
            cache_dir = self.cache_dir

        input_text = remove_bookmarks(text)
        input_data = {
            "input_text": input_text,
            "service": "gemini_tts",
            "voice": self.voice_name,
        }

        # manim-voiceover 標準キャッシュ
        cached_result = self.get_cached_result(input_data, cache_dir)
        if cached_result is not None:
            return cached_result

        if path is None:
            audio_path = self.get_audio_basename(input_data) + ".wav"
        else:
            audio_path = os.path.basename(path)

        output_file = str(Path(cache_dir) / audio_path)

        # lookup モード: 事前生成 WAV をコピー
        looked_up = self._lookup_wav(input_text)
        if looked_up:
            import shutil
            shutil.copy2(looked_up, output_file)
            return {
                "input_text": text,
                "input_data": input_data,
                "original_audio": audio_path,
            }

        # API 禁止モードで lookup にもなかった場合
        if not self.allow_api:
            raise RuntimeError(
                f"音声ファイルが見つかりません (allow_api=False): "
                f"key={voice_cache_key(input_text, voice=self.voice_name)}, "
                f"text={input_text[:80]!r}"
            )

        # Gemini TTS API 呼び出し
        from google.genai import types

        response = self.client.models.generate_content(
            model=self.tts_model,
            contents=f"{self.prompt_prefix}{input_text}",
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=self.voice_name,
                        )
                    )
                ),
            ),
        )

        pcm_data = response.candidates[0].content.parts[0].inline_data.data

        # WAV として保存
        with wave.open(output_file, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(pcm_data)

        return {
            "input_text": text,
            "input_data": input_data,
            "original_audio": audio_path,
        }

    def pre_generate_all(
        self, narrations: list[str], output_dir: str | None = None
    ) -> dict[str, bytes]:
        """全ナレーションの WAV を事前生成し、dict[cache_key, wav_bytes] を返す。

        Modal に渡すためのバルク生成メソッド。
        既にキャッシュキーが同じ WAV が output_dir にあればスキップする。

        Args:
            narrations: ナレーションテキストのリスト（ブックマーク付きでもOK）
            output_dir: WAV 保存先。None の場合は一時ディレクトリ

        Returns:
            dict[str, bytes]: {cache_key: wav_bytes} — そのまま Modal に渡せる
        """
        import tempfile

        if output_dir is None:
            tmp = tempfile.TemporaryDirectory(prefix="tts_pre_")
            output_dir = tmp.name
        os.makedirs(output_dir, exist_ok=True)

        result: dict[str, bytes] = {}
        seen_keys: set[str] = set()

        for narration in narrations:
            normalized = remove_bookmarks(narration)
            key = voice_cache_key(normalized, voice=self.voice_name)

            # 重複スキップ
            if key in seen_keys:
                continue
            seen_keys.add(key)

            wav_path = Path(output_dir) / f"{key}.wav"

            # 既存ファイルがあればスキップ
            if wav_path.exists():
                result[key] = wav_path.read_bytes()
                continue

            # API で生成
            if not self.allow_api:
                raise RuntimeError(
                    f"音声ファイルが見つかりません (allow_api=False): "
                    f"key={key}, text={normalized[:80]!r}"
                )

            from google.genai import types

            print(f"  TTS 生成中: {normalized[:40]}... (key={key[:8]})")
            response = self.client.models.generate_content(
                model=self.tts_model,
                contents=f"{self.prompt_prefix}{normalized}",
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=self.voice_name,
                            )
                        )
                    ),
                ),
            )

            pcm_data = response.candidates[0].content.parts[0].inline_data.data

            with wave.open(str(wav_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(pcm_data)

            result[key] = wav_path.read_bytes()

        print(f"  TTS 事前生成完了: {len(result)} ファイル")
        return result
