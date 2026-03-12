#!/usr/bin/env python3
"""動画レビュアーモジュール — Gemini Flash で動画品質を検証する"""

import argparse
import json
import os
import shutil
import sys
import tempfile
import time

from google import genai


def _load_env():
    env_vars = {}
    with open(os.path.expanduser("~/studygram/.env")) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = map(str.strip, line.split("=", 1))
                env_vars[k] = v.strip("'\"")
    return env_vars


def review_video(video_path: str, scene_spec: str) -> dict:
    """動画ファイルとシーン仕様書を Gemini Flash に投げてレビューを取得する。

    Args:
        video_path: MP4ファイルのパス
        scene_spec: 各シーンで画面上に表示されるべき内容の詳細仕様（テキスト）

    Returns:
        dict: {"issues": [...], "overall_assessment": "..."}
    """
    env_vars = _load_env()
    api_key = env_vars.get("GEMINI_API_KEY")
    flash_model = env_vars.get("VITE_GEMINI_FLASH_MODEL")
    if not api_key or not flash_model:
        raise RuntimeError("GEMINI_API_KEY or VITE_GEMINI_FLASH_MODEL not set in ~/studygram/.env")

    client = genai.Client(api_key=api_key)

    # 日本語ファイル名は Gemini API (httpx) の ASCII ヘッダで UnicodeEncodeError になる
    # → 一時的に ASCII ファイル名でコピーしてアップロード
    upload_path = video_path
    tmp_copy = None
    try:
        video_path.encode("ascii")
    except UnicodeEncodeError:
        tmp_copy = os.path.join(tempfile.gettempdir(), f"hoshu_video_review_{os.getpid()}.mp4")
        shutil.copy2(video_path, tmp_copy)
        upload_path = tmp_copy

    try:
        # 動画アップロード
        print(f"動画アップロード中: {video_path}")
        video_file = client.files.upload(file=upload_path)
        print(f"  アップロード完了: {video_file.name} ({video_file.state})")

        while video_file.state == "PROCESSING":
            print("  処理中...")
            time.sleep(10)
            video_file = client.files.get(name=video_file.name)

        if video_file.state != "ACTIVE":
            raise RuntimeError(f"動画の処理に失敗 (state={video_file.state})")

        prompt = f"""あなたは教育動画のQAレビュアーです。添付の動画を厳しくレビューしてください。

以下に各シーンで**画面上に表示されるべき内容**を記載します。
動画を最初から最後まで注意深く視聴し、**実際の画面がこの仕様と合っているか**を1シーンずつ検証してください。

---

{scene_spec}

---

上記仕様と実際の動画を照合し、**不一致・欠陥・改善点**をすべて洗い出してください。
特に以下の観点を重視してください:
- 図形の塗りつぶし・色が意図通りか（半透明で見えるか、塗られるべき場所が塗られているか）
- アニメーションが「解説」として機能しているか（ただ表示されるだけでなく、概念の理解を助けているか）
- ナレーションのタイミングと画面表示のタイミングが合っているか

## 出力形式（JSON）
```json
{{
  "issues": [
    {{
      "timestamp": "1:03",
      "scene": "Scene 4",
      "severity": "high|medium|low",
      "description": "何が問題か",
      "suggestion": "どう直すべきか"
    }}
  ],
  "overall_assessment": "動画全体の評価（率直に）"
}}
```

JSON以外のテキストは一切出力しないこと。
"""

        print(f"Gemini レビュー中... (model: {flash_model})")
        response = client.models.generate_content(
            model=flash_model,
            contents=[video_file, prompt],
            config={"temperature": 0.3},
        )

        raw = response.text
        if "```json" in raw:
            raw = raw.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in raw:
            raw = raw.split("```", 1)[1].split("```", 1)[0]

        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"WARNING: Gemini JSON パース失敗: {e}", file=sys.stderr)
            print(f"  Raw output: {response.text[:300]}", file=sys.stderr)
            return {"issues": [], "overall_assessment": f"[JSONパース失敗] {response.text[:500]}"}
    finally:
        if tmp_copy and os.path.exists(tmp_copy):
            os.remove(tmp_copy)


def print_review(review: dict):
    """レビュー結果を見やすく表示する"""
    issues = review.get("issues", [])
    print(f"\n=== 指摘事項 ({len(issues)}件) ===")
    for issue in issues:
        sev = issue.get("severity", "?").upper()
        ts = issue.get("timestamp", "?")
        scene = issue.get("scene", "?")
        print(f"  [{sev}] @{ts} ({scene}) {issue['description']}")
        print(f"    → {issue.get('suggestion', '')}")

    print(f"\n=== 総評 ===")
    print(f"  {review.get('overall_assessment', '')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="動画品質レビュー（Gemini Flash）")
    parser.add_argument("video", help="レビューする動画ファイル (MP4)")
    parser.add_argument("spec", help="シーン仕様書 (テキストファイル)")
    args = parser.parse_args()

    with open(args.spec, "r") as f:
        scene_spec = f.read()

    review = review_video(args.video, scene_spec)

    # 保存
    out_path = args.video.rsplit(".", 1)[0] + "_review.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(review, f, ensure_ascii=False, indent=2)
    print(f"レビュー保存: {out_path}")

    print_review(review)
