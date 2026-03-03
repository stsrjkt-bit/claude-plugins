import modal
from pathlib import Path

HF_MODEL_ID = "YUKI66/qwen3-tts-1.7b-finetuned"
MODEL_DIR = "/model"
REF_AUDIO_PATH = "/assets/voice_ref.wav"
SCRIPTS_DIR = Path(__file__).parent

def download_model():
    import json
    from pathlib import Path
    from huggingface_hub import snapshot_download
    snapshot_download(repo_id=HF_MODEL_ID, local_dir=MODEL_DIR)
    # Patch config: tts_model_type must be "base" for generate_voice_clone to work
    config_path = Path(MODEL_DIR) / "config.json"
    with open(config_path) as f:
        config = json.load(f)
    config["tts_model_type"] = "base"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("sox", "libsox-fmt-all")
    .pip_install("qwen_tts", "soundfile", "torch", "huggingface_hub", "hf_transfer")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
    .add_local_file(str(SCRIPTS_DIR / "voice_ref.wav"), remote_path=REF_AUDIO_PATH, copy=True)
    .run_function(
        download_model,
        secrets=[modal.Secret.from_name("huggingface")],  # private repo アクセス用
    )
)

app = modal.App("qwen3-tts", image=image)

@app.cls(gpu="T4", scaledown_window=300, min_containers=0)
class TTSModel:
    @modal.enter()
    def load_model(self):
        import torch
        from qwen_tts import Qwen3TTSModel
        self.model = Qwen3TTSModel.from_pretrained(
            MODEL_DIR, device_map="cuda:0", dtype=torch.bfloat16, attn_implementation="sdpa",
        )

    @modal.method()
    def generate(self, text: str) -> dict:
        import io, soundfile as sf
        wavs, sr = self.model.generate_voice_clone(
            text=text, language="Japanese", ref_audio=REF_AUDIO_PATH,
            x_vector_only_mode=True, max_new_tokens=2048,
        )
        buf = io.BytesIO()
        sf.write(buf, wavs[0], sr, format="WAV")
        return {"wav": buf.getvalue(), "sr": sr}

# --- Manim レンダリング (CPU) ---

manim_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install(
        "ffmpeg", "sox", "libsox-fmt-all",
        "texlive-latex-base", "texlive-latex-extra",
        "texlive-fonts-recommended",
        "texlive-lang-japanese", "texlive-lang-cjk",
        "fonts-noto-cjk",
        "libcairo2-dev", "libpango1.0-dev",
    )
    .pip_install("manim", "manim-voiceover")
    .run_commands(
        "pip install 'setuptools<75' && python -c 'import pkg_resources'",
        # manim-voiceover の get_duration() が MP3 をハードコードしており WAV で壊れるのをパッチ
        "python -c \""
        "import site; p = site.getsitepackages()[0] + '/manim_voiceover/modify_audio.py';"
        "t = open(p).read();"
        "t = t.replace('from mutagen.mp3 import MP3', 'import sox');"
        "t = t.replace('audio = MP3(path)\\n    return audio.info.length', 'return sox.file_info.duration(path)');"
        "open(p,'w').write(t);"
        "print('Patched modify_audio.py: get_duration now uses sox')"
        "\"",
        # パッチ適用の検証
        "python -c \"from manim_voiceover.modify_audio import get_duration; "
        "import inspect; assert 'sox' in inspect.getsource(get_duration), 'patch failed'\"",
    )
)

# 簡易 qwen3_tts_service.py — キャッシュ参照のみ（Modal/HF 呼び出しなし）
# NOTE: qwen3_tts_service.py の generate_from_text() と同期を保つこと
_STUB_TTS_SERVICE = '''\
import hashlib, os, shutil
from pathlib import Path
from manim_voiceover.helper import remove_bookmarks
from manim_voiceover.services.base import SpeechService

AUDIO_CACHE_DIR = "/work/voice_cache"

def _text_hash(text):
    return hashlib.md5(text.encode()).hexdigest()[:16]

class Qwen3TTSService(SpeechService):
    def __init__(self, cache_audio_dir=AUDIO_CACHE_DIR, **kwargs):
        SpeechService.__init__(self, **kwargs)
        self.cache_audio_dir = cache_audio_dir

    def generate_from_text(self, text, cache_dir=None, path=None, **kwargs):
        if cache_dir is None:
            cache_dir = self.cache_dir
        input_text = remove_bookmarks(text)
        input_data = {"input_text": input_text, "service": "qwen3_tts_finetuned"}
        cached_result = self.get_cached_result(input_data, cache_dir)
        if cached_result is not None:
            return cached_result
        if path is None:
            audio_path = self.get_audio_basename(input_data) + ".wav"
        else:
            audio_path = os.path.basename(path)
        output_file = str(Path(cache_dir) / audio_path)
        h = _text_hash(input_text)
        pregenerated = os.path.join(self.cache_audio_dir, f"{h}.wav")
        if not os.path.exists(pregenerated):
            raise RuntimeError(
                f"Audio not found for: {input_text[:50]}...\\n"
                f"Expected: {pregenerated}\\n"
                "voice_cache に該当ファイルがありません。"
            )
        shutil.copy(pregenerated, output_file)
        return {"input_text": text, "input_data": input_data, "original_audio": audio_path}
'''


@app.function(
    image=manim_image,
    cpu=8,
    memory=8192,
    timeout=600,
    scaledown_window=120,
    min_containers=0,
)
def render_video(
    script_content: str,
    voice_files: dict[str, bytes],
    scene_name: str = "",
) -> bytes:
    """Manim スクリプトを Modal CPU でレンダリングし、MP4 を返す。

    Args:
        script_content: Manim .py スクリプトの中身（文字列）
        voice_files: {"<hash>.wav": bytes, ...} 音声ファイル群
        scene_name: レンダリングするシーンクラス名。省略時はスクリプトから自動検出

    Returns:
        MP4 ファイルのバイト列
    """
    import re
    import subprocess
    from pathlib import Path

    work = Path("/work")
    work.mkdir(exist_ok=True)

    # 1. voice_cache を展開
    cache_dir = work / "voice_cache"
    cache_dir.mkdir(exist_ok=True)
    for name, data in voice_files.items():
        safe_name = Path(name).name  # path traversal 防止
        (cache_dir / safe_name).write_bytes(data)

    # 2. スタブ qwen3_tts_service.py を配置
    (work / "qwen3_tts_service.py").write_text(_STUB_TTS_SERVICE)

    # 3. スクリプトの sys.path.insert 行を書き換え
    script = re.sub(
        r"sys\.path\.insert\(\s*0\s*,\s*['\"].*?['\"]\s*\)",
        "sys.path.insert(0, '/work')",
        script_content,
    )
    script_path = work / "scene.py"
    script_path.write_text(script)

    # 4. シーンクラス名を検出（明示指定がなければ Scene/VoiceoverScene 継承クラスを探す）
    if not scene_name:
        match = re.search(
            r"class\s+(\w+)\s*\(\s*(?:VoiceoverScene|Scene|ThreeDScene|MovingCameraScene)",
            script,
        )
        if not match:
            match = re.search(r"class\s+(\w+)\s*\(", script)
        scene_name = match.group(1) if match else "HoshuVideo"

    # 5. manim render
    result = subprocess.run(
        [
            "manim", "render", "-qm", "--format", "mp4",
            str(script_path), scene_name,
        ],
        cwd=str(work),
        capture_output=True,
        text=True,
        timeout=540,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"manim render failed (exit {result.returncode}):\n"
            f"STDOUT:\n{result.stdout[-2000:]}\n"
            f"STDERR:\n{result.stderr[-2000:]}"
        )

    # 6. 生成 MP4 を探す
    mp4_files = list(work.rglob("*.mp4"))
    if not mp4_files:
        raise RuntimeError(
            f"No MP4 found after render.\n"
            f"STDOUT:\n{result.stdout[-2000:]}\n"
            f"STDERR:\n{result.stderr[-2000:]}"
        )
    # 最新のものを返す
    mp4 = max(mp4_files, key=lambda p: p.stat().st_mtime)
    return mp4.read_bytes()


@app.local_entrypoint()
def main():
    model = TTSModel()
    result = model.generate.remote("これはテスト音声です。")
    import soundfile as sf, io
    data, sr = sf.read(io.BytesIO(result["wav"]))
    sf.write("/tmp/modal_tts_test.wav", data, sr)
    print(f"OK: {len(result['wav'])} bytes, sr={sr}")
