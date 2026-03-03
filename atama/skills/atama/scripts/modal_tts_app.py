import modal
from pathlib import Path

HF_MODEL_ID = "YUKI66/qwen3-tts-1.7b-finetuned"
MODEL_DIR = "/model"
REF_AUDIO_PATH = "/assets/voice_ref.wav"
SCRIPTS_DIR = Path(__file__).parent

def download_model():
    import json
    from huggingface_hub import snapshot_download
    snapshot_download(repo_id=HF_MODEL_ID, local_dir=MODEL_DIR)
    # Patch config: tts_model_type must be "base" for generate_voice_clone to work
    config_path = f"{MODEL_DIR}/config.json"
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
    .run_function(download_model)  # ビルド時に HF モデルを焼き込み（GPU 不要）
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

@app.local_entrypoint()
def main():
    model = TTSModel()
    result = model.generate.remote("これはテスト音声です。")
    import soundfile as sf, io
    data, sr = sf.read(io.BytesIO(result["wav"]))
    sf.write("/tmp/modal_tts_test.wav", data, sr)
    print(f"OK: {len(result['wav'])} bytes, sr={sr}")
