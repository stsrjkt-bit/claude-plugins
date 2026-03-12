"""Modal Manim レンダリングアプリ。

ローカルで事前生成された TTS WAV ファイルを受け取り、
Manim レンダリング + ffmpeg 圧縮を Modal CPU で実行して MP4 を返す。

Gemini API キーは不要（TTS はローカルで完結済み）。
"""

import modal
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent

app = modal.App("manim-render")

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
    .pip_install("manim==0.20.1", "manim-voiceover==0.3.7")
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

# --- インラインスタブ ---
# Modal コンテナ内には gemini_tts_service.py と voice_hash.py がないため、
# ソースを読み込んでジョブ実行時に書き出す。

_STUB_VOICE_HASH = (SCRIPTS_DIR / "voice_hash.py").read_text(encoding="utf-8")
_STUB_GEMINI_TTS = (SCRIPTS_DIR / "gemini_tts_service.py").read_text(encoding="utf-8")


@app.function(
    image=manim_image,
    cpu=8,
    memory=8192,
    timeout=1200,
    scaledown_window=120,
    min_containers=0,
)
def render_video(
    script_content: str,
    voice_files: dict[str, bytes],
    scene_name: str = "",
) -> bytes:
    """Manim スクリプトを Modal CPU でレンダリングし、圧縮 MP4 を返す。

    Args:
        script_content: Manim .py スクリプトの中身（文字列）
        voice_files: {cache_key: wav_bytes} — ローカルで事前生成した TTS 音声
        scene_name: レンダリングするシーンクラス名。省略時はスクリプトから自動検出

    Returns:
        圧縮済み MP4 ファイルのバイト列
    """
    import re
    import subprocess
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory(prefix="manim_job_") as job_dir:
        job = Path(job_dir)

        # 1. voice_hash.py スタブを配置
        (job / "voice_hash.py").write_text(_STUB_VOICE_HASH, encoding="utf-8")

        # 2. gemini_tts_service.py スタブを配置
        (job / "gemini_tts_service.py").write_text(_STUB_GEMINI_TTS, encoding="utf-8")

        # 3. WAV ファイルを voice_cache/ に展開
        voice_dir = job / "voice_cache"
        voice_dir.mkdir()
        for cache_key, wav_bytes in voice_files.items():
            if not re.match(r'^[a-f0-9]{32}$', cache_key):
                raise ValueError(f"Invalid cache_key format: {cache_key!r}")
            (voice_dir / f"{cache_key}.wav").write_bytes(wav_bytes)
        print(f"Voice files deployed: {len(voice_files)} files in {voice_dir}")

        # 4. スクリプトの sys.path.insert 行を job_dir に書き換え
        script = re.sub(
            r"sys\.path\.insert\(\s*0\s*,\s*['\"].*?['\"]\s*\)",
            f"sys.path.insert(0, {str(job)!r})",
            script_content,
        )

        # 5. GeminiTTSService の初期化を lookup モードに書き換え
        #    voice_name は維持し、lookup_dir と allow_api を追加
        patched_script, n_subs = re.subn(
            r"GeminiTTSService\(([^)]*)\)",
            lambda m: _patch_tts_init(m.group(1), str(voice_dir)),
            script,
        )
        if n_subs == 0:
            raise RuntimeError(
                "GeminiTTSService(...) がスクリプト内に見つかりません。"
                "スクリプトの TTS 初期化を確認してください。"
            )
        script = patched_script

        script_path = job / "scene.py"
        script_path.write_text(script, encoding="utf-8")

        # 6. シーンクラス名を検出
        if not scene_name:
            match = re.search(
                r"class\s+(\w+)\s*\(\s*(?:VoiceoverScene|Scene|ThreeDScene|MovingCameraScene)",
                script,
            )
            if not match:
                match = re.search(r"class\s+(\w+)\s*\(", script)
            scene_name = match.group(1) if match else "HoshuVideo"

        # 7. manim render
        print(f"Rendering scene: {scene_name}")
        result = subprocess.run(
            [
                "manim", "render", "-qm", "--format", "mp4",
                str(script_path), scene_name,
            ],
            cwd=str(job),
            capture_output=True,
            text=True,
            timeout=900,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"manim render failed (exit {result.returncode}):\n"
                f"STDOUT:\n{result.stdout[-2000:]}\n"
                f"STDERR:\n{result.stderr[-2000:]}"
            )

        # 8. 生成 MP4 を探す
        mp4_files = list(job.rglob("*.mp4"))
        if not mp4_files:
            raise RuntimeError(
                f"No MP4 found after render.\n"
                f"STDOUT:\n{result.stdout[-2000:]}\n"
                f"STDERR:\n{result.stderr[-2000:]}"
            )
        raw_mp4 = max(mp4_files, key=lambda p: p.stat().st_mtime)

        # 9. ffmpeg 圧縮
        compressed = job / "output_compressed.mp4"
        compress_result = subprocess.run(
            [
                "ffmpeg", "-i", str(raw_mp4),
                "-vcodec", "libx264", "-crf", "28", "-preset", "fast",
                "-movflags", "+faststart",
                "-acodec", "aac", "-b:a", "96k",
                str(compressed), "-y",
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if compress_result.returncode != 0:
            print(f"ffmpeg compression failed, returning raw MP4: {compress_result.stderr[-500:]}")
            return raw_mp4.read_bytes()

        raw_size = raw_mp4.stat().st_size
        comp_size = compressed.stat().st_size
        print(f"Compression: {raw_size:,} -> {comp_size:,} bytes ({comp_size/raw_size*100:.0f}%)")

        return compressed.read_bytes()


def _patch_tts_init(original_args: str, voice_dir: str) -> str:
    """GeminiTTSService(...) の引数を lookup モードに書き換える。

    voice_name="Puck" などの既存引数は維持し、
    lookup_dir と allow_api=False を追加する。
    """
    # 既存引数をパース（簡易: voice_name="..." のパターン）
    args = original_args.strip()
    if args:
        return f'GeminiTTSService({args}, lookup_dir={voice_dir!r}, allow_api=False)'
    else:
        return f'GeminiTTSService(lookup_dir={voice_dir!r}, allow_api=False)'
