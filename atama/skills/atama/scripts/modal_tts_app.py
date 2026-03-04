import modal
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent

app = modal.App("manim-render")

# --- Manim レンダリング (CPU) + Edge TTS (オンザフライ) ---

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
    .pip_install("manim", "manim-voiceover", "edge-tts")
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

# edge_service.py をスタブとしてそのまま使う（二重管理防止）
_STUB_EDGE_SERVICE = (SCRIPTS_DIR / "edge_service.py").read_text()


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
    scene_name: str = "",
) -> bytes:
    """Manim スクリプトを Modal CPU でレンダリングし、MP4 を返す。

    Args:
        script_content: Manim .py スクリプトの中身（文字列）
        scene_name: レンダリングするシーンクラス名。省略時はスクリプトから自動検出

    Returns:
        MP4 ファイルのバイト列
    """
    import re
    import subprocess
    from pathlib import Path

    work = Path("/work")
    work.mkdir(exist_ok=True)

    # 1. Edge TTS スタブを配置
    (work / "edge_service.py").write_text(_STUB_EDGE_SERVICE)

    # 2. スクリプトの sys.path.insert 行を書き換え
    script = re.sub(
        r"sys\.path\.insert\(\s*0\s*,\s*['\"].*?['\"]\s*\)",
        "sys.path.insert(0, '/work')",
        script_content,
    )
    script_path = work / "scene.py"
    script_path.write_text(script)

    # 3. シーンクラス名を検出
    if not scene_name:
        match = re.search(
            r"class\s+(\w+)\s*\(\s*(?:VoiceoverScene|Scene|ThreeDScene|MovingCameraScene)",
            script,
        )
        if not match:
            match = re.search(r"class\s+(\w+)\s*\(", script)
        scene_name = match.group(1) if match else "HoshuVideo"

    # 4. manim render
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

    # 5. 生成 MP4 を探す
    mp4_files = list(work.rglob("*.mp4"))
    if not mp4_files:
        raise RuntimeError(
            f"No MP4 found after render.\n"
            f"STDOUT:\n{result.stdout[-2000:]}\n"
            f"STDERR:\n{result.stderr[-2000:]}"
        )
    mp4 = max(mp4_files, key=lambda p: p.stat().st_mtime)
    return mp4.read_bytes()
