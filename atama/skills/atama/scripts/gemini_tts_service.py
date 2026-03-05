"""Gemini 2.5 Pro Preview TTS service for manim-voiceover."""

import os
import sys
import wave
from pathlib import Path

from manim_voiceover.helper import remove_bookmarks
from manim_voiceover.services.base import SpeechService

from google import genai
from google.genai import types


class GeminiTTSService(SpeechService):
    def __init__(
        self,
        voice_name="Kore",
        prompt_prefix="優しく教える数学の先生として、自然に読んでください: ",
        **kwargs,
    ):
        SpeechService.__init__(self, **kwargs)
        self.voice_name = voice_name
        self.prompt_prefix = prompt_prefix

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
            print(f"ERROR: {env_path} が見つかりません", file=sys.stderr)
            sys.exit(1)

        api_key = env_vars.get("GEMINI_API_KEY")
        self.tts_model = env_vars.get("GEMINI_TTS_MODEL")
        if not api_key:
            print("ERROR: GEMINI_API_KEY が未設定", file=sys.stderr)
            sys.exit(1)
        if not self.tts_model:
            print("ERROR: GEMINI_TTS_MODEL が未設定", file=sys.stderr)
            sys.exit(1)

        self.client = genai.Client(api_key=api_key)

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

        cached_result = self.get_cached_result(input_data, cache_dir)
        if cached_result is not None:
            return cached_result

        if path is None:
            audio_path = self.get_audio_basename(input_data) + ".wav"
        else:
            audio_path = os.path.basename(path)

        output_file = str(Path(cache_dir) / audio_path)

        # Gemini TTS API 呼び出し
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

        json_dict = {
            "input_text": text,
            "input_data": input_data,
            "original_audio": audio_path,
        }

        return json_dict
