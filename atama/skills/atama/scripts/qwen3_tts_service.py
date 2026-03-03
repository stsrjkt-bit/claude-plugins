"""Qwen3-TTS fine-tuned voice service for manim-voiceover (Kaggle GPU backend).

Uses fine-tuned model (YUKI66/qwen3-tts-1.7b-finetuned) with voice cloning
for best quality. Reference audio provides x-vector speaker identity on top
of the fine-tuned weights.

Usage in Manim script:
    from qwen3_tts_service import Qwen3TTSService

    class MyScene(VoiceoverScene):
        def setup(self):
            super().setup()
            self.set_speech_service(Qwen3TTSService())

Before rendering, generate audio via Kaggle:
    Qwen3TTSService.kaggle_generate(["text1", "text2", ...])
"""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from manim_voiceover.helper import remove_bookmarks
from manim_voiceover.services.base import SpeechService

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
VOICE_REF_PATH = os.path.join(SCRIPTS_DIR, "voice_ref.wav")
KAGGLE_KERNEL_ID = "satosuri/xtts-voice-clone"
KAGGLE_DATASET = "satosuri/voice-ref-clip"
AUDIO_CACHE_DIR = os.path.join(SCRIPTS_DIR, "voice_cache")

HF_MODEL_ID = "YUKI66/qwen3-tts-1.7b-finetuned"


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
                "Run Qwen3TTSService.kaggle_generate(texts) first."
            )

        shutil.copy(pregenerated, output_file)

        json_dict = {
            "input_text": text,
            "input_data": input_data,
            "original_audio": audio_path,
        }
        return json_dict

    @staticmethod
    def kaggle_generate(
        texts: list[str],
        output_dir: str = AUDIO_CACHE_DIR,
        timeout_minutes: int = 20,
    ) -> list[str]:
        """Generate audio for all texts via Kaggle GPU.

        Returns list of output file paths.
        """
        os.makedirs(output_dir, exist_ok=True)

        # Check which texts already have cached audio
        pending = []
        for text in texts:
            h = _text_hash(text)
            if not os.path.exists(os.path.join(output_dir, f"{h}.wav")):
                pending.append(text)

        if not pending:
            print("All audio already cached, skipping Kaggle.")
            return [
                os.path.join(output_dir, f"{_text_hash(t)}.wav") for t in texts
            ]

        print(f"Generating {len(pending)} audio clips via Kaggle...")

        # Build text list with hashes for the kernel
        text_entries = []
        for text in pending:
            h = _text_hash(text)
            text_entries.append({"hash": h, "text": text})

        # Write Kaggle kernel script
        kernel_dir = tempfile.mkdtemp(prefix="kaggle_tts_")
        _write_kernel_script(kernel_dir, text_entries)
        _write_kernel_metadata(kernel_dir)

        # Push to Kaggle
        env = {**os.environ, "KAGGLE_API_TOKEN": os.environ["KAGGLE_API_TOKEN"]}
        subprocess.run(
            ["kaggle", "kernels", "push", "-p", kernel_dir],
            check=True, env=env,
        )
        print("Kernel pushed. Polling for completion...")

        # Poll until complete
        start = time.time()
        while time.time() - start < timeout_minutes * 60:
            time.sleep(30)
            result = subprocess.run(
                ["kaggle", "kernels", "status", KAGGLE_KERNEL_ID],
                capture_output=True, text=True, env=env,
            )
            status = result.stdout.strip()
            print(f"  {status}")
            if "COMPLETE" in status.upper():
                break
            if "ERROR" in status.upper() or "CANCEL" in status.upper():
                raise RuntimeError(f"Kaggle kernel failed: {status}")
        else:
            raise RuntimeError(f"Kaggle kernel timed out after {timeout_minutes}m")

        # Download output
        dl_dir = os.path.join(kernel_dir, "output")
        os.makedirs(dl_dir, exist_ok=True)
        subprocess.run(
            ["kaggle", "kernels", "output", KAGGLE_KERNEL_ID,
             "-p", dl_dir, "--force"],
            check=True, env=env,
        )

        # Move audio files to cache
        moved = 0
        for entry in text_entries:
            src = os.path.join(dl_dir, f"{entry['hash']}.wav")
            dst = os.path.join(output_dir, f"{entry['hash']}.wav")
            if os.path.exists(src):
                shutil.move(src, dst)
                moved += 1

        print(f"Done! {moved}/{len(pending)} audio files cached to {output_dir}")

        # Clean up temp dir
        shutil.rmtree(kernel_dir, ignore_errors=True)

        return [
            os.path.join(output_dir, f"{_text_hash(t)}.wav") for t in texts
        ]


def _write_kernel_script(kernel_dir: str, text_entries: list[dict]):
    texts_json = json.dumps(text_entries, ensure_ascii=False, indent=2)
    hf_token = os.environ.get("HF_TOKEN", "")
    script = f'''"""Qwen3-TTS Fine-tuned Voice - Batch Generation on Kaggle GPU"""
import subprocess, os, sys, time, json, glob

subprocess.run([sys.executable, "-m", "pip", "install", "-q", "qwen_tts", "soundfile", "huggingface_hub"], check=True)

import torch
import soundfile as sf
from qwen_tts import Qwen3TTSModel
from huggingface_hub import login

print(f"GPU: {{torch.cuda.get_device_name(0)}}, VRAM: {{torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}} GB")

# Login to HF for private model access
login(token="{hf_token}")

print("Loading fine-tuned Qwen3-TTS 1.7B model...")
t0 = time.time()
model = Qwen3TTSModel.from_pretrained(
    "{HF_MODEL_ID}",
    device_map="cuda:0",
    dtype=torch.bfloat16,
)
print(f"Model loaded in {{time.time()-t0:.0f}}s")

ref_candidates = glob.glob("/kaggle/input/**/*.wav", recursive=True)
assert ref_candidates, "No reference audio found!"
ref_path = ref_candidates[0]
print(f"Reference audio: {{ref_path}}")

text_entries = {texts_json}

for i, entry in enumerate(text_entries):
    t0 = time.time()
    wavs, sr = model.generate_voice_clone(
        text=entry["text"],
        language="Japanese",
        ref_audio=ref_path,
        x_vector_only_mode=True,
        max_new_tokens=2048,
    )
    out_path = f"/kaggle/working/{{entry['hash']}}.wav"
    sf.write(out_path, wavs[0], sr)
    elapsed = time.time() - t0
    duration = len(wavs[0]) / sr
    print(f"[{{i}}] {{entry['hash']}} generated in {{elapsed:.1f}}s, duration={{duration:.1f}}s")

print(f"\\nDone! Generated {{len(text_entries)}} files.")
'''
    with open(os.path.join(kernel_dir, "xtts-voice-clone.py"), "w") as f:
        f.write(script)


def _write_kernel_metadata(kernel_dir: str):
    metadata = {
        "id": KAGGLE_KERNEL_ID,
        "title": "xtts-voice-clone",
        "code_file": "xtts-voice-clone.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": True,
        "dataset_sources": [KAGGLE_DATASET],
        "competition_sources": [],
        "kernel_sources": [],
    }
    with open(os.path.join(kernel_dir, "kernel-metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
