"""Qwen3-TTS fine-tuned voice service for manim-voiceover (Modal GPU backend).

Uses fine-tuned model (YUKI66/qwen3-tts-1.7b-finetuned) with voice cloning
for best quality. Reference audio provides x-vector speaker identity on top
of the fine-tuned weights.

Usage in Manim script:
    from qwen3_tts_service import Qwen3TTSService

    class MyScene(VoiceoverScene):
        def setup(self):
            super().setup()
            self.set_speech_service(Qwen3TTSService())

Before rendering, generate audio via Modal:
    Qwen3TTSService.modal_generate(["text1", "text2", ...])
"""

import hashlib
import os
import shutil
from pathlib import Path

from manim_voiceover.helper import remove_bookmarks
from manim_voiceover.services.base import SpeechService

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_CACHE_DIR = os.path.join(SCRIPTS_DIR, "voice_cache")


def _text_hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:16]


class Qwen3TTSService(SpeechService):
    def __init__(self, cache_audio_dir: str = AUDIO_CACHE_DIR, **kwargs):
        SpeechService.__init__(self, **kwargs)
        self.cache_audio_dir = cache_audio_dir

    def generate_from_text(
        self, text: str, cache_dir: str = None, path: str = None, **kwargs
    ) -> dict:
        if cache_dir is None:
            cache_dir = self.cache_dir

        input_text = remove_bookmarks(text)
        input_data = {
            "input_text": input_text,
            "service": "qwen3_tts_finetuned",
        }

        cached_result = self.get_cached_result(input_data, cache_dir)
        if cached_result is not None:
            return cached_result

        if path is None:
            audio_path = self.get_audio_basename(input_data) + ".wav"
        else:
            audio_path = os.path.basename(path)

        output_file = str(Path(cache_dir) / audio_path)

        # Look up pre-generated audio by text hash
        h = _text_hash(input_text)
        pregenerated = os.path.join(self.cache_audio_dir, f"{h}.wav")
        if not os.path.exists(pregenerated):
            raise RuntimeError(
                f"Audio not found for: {input_text[:50]}...\n"
                f"Expected: {pregenerated}\n"
                "Run Qwen3TTSService.modal_generate(texts) first."
            )

        shutil.copy(pregenerated, output_file)

        json_dict = {
            "input_text": text,
            "input_data": input_data,
            "original_audio": audio_path,
        }
        return json_dict

    @staticmethod
    def modal_generate(
        texts: list[str],
        output_dir: str = AUDIO_CACHE_DIR,
    ) -> list[str]:
        """Generate audio for all texts via Modal GPU.

        Returns list of output file paths.
        """
        import modal  # lazy import（manim render 時は不要）

        os.makedirs(output_dir, exist_ok=True)

        # Check which texts already have cached audio
        pending = []
        for text in texts:
            h = _text_hash(text)
            if not os.path.exists(os.path.join(output_dir, f"{h}.wav")):
                pending.append(text)

        if not pending:
            print("All audio already cached, skipping Modal.")
            return [
                os.path.join(output_dir, f"{_text_hash(t)}.wav") for t in texts
            ]

        print(f"Generating {len(pending)} audio clips via Modal GPU...")

        TTSModel = modal.Cls.from_name("qwen3-tts", "TTSModel")
        model = TTSModel()

        results = list(model.generate.map(
            pending, return_exceptions=True, wrap_returned_exceptions=False,
        ))

        failed = []
        for i, (text, result) in enumerate(zip(pending, results)):
            h = _text_hash(text)
            if isinstance(result, Exception):
                print(f"  [{i+1}/{len(pending)}] {h} FAILED: {result}")
                failed.append(text)
                continue
            dst = os.path.join(output_dir, f"{h}.wav")
            with open(dst, "wb") as f:
                f.write(result["wav"])
            print(f"  [{i+1}/{len(pending)}] {h} done ({len(result['wav'])} bytes)")

        if failed:
            raise RuntimeError(f"{len(failed)}/{len(pending)} clips failed to generate")

        return [
            os.path.join(output_dir, f"{_text_hash(t)}.wav") for t in texts
        ]

    kaggle_generate = modal_generate  # 後方互換エイリアス
