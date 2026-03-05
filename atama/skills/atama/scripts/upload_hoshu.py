#!/usr/bin/env python3
"""補習プリント＆動画の一括アップロード (Phase 12)

Usage:
  # 新規作成 + 生徒に配信
  python3 upload_hoshu.py \
    --student "鈴木 愛莉" \
    --title "【補習】おうぎ形の応用" \
    --subject "中学数学" \
    --problem /tmp/hoshu_material/問題.pdf \
    --answer  /tmp/hoshu_material/解答.pdf \
    --video   /tmp/hoshu_material/video.mp4

  # 既存プリントの差し替え (print_id指定)
  python3 upload_hoshu.py \
    --replace 9d14b5fb-4d83-4d18-8927-afd76b330820 \
    --problem /tmp/hoshu_material/問題.pdf \
    --answer  /tmp/hoshu_material/解答.pdf \
    --video   /tmp/hoshu_material/video.mp4

  # PDF のみ（動画なし）
  python3 upload_hoshu.py \
    --student "鈴木 愛莉" \
    --title "【補習】おうぎ形の応用" \
    --subject "中学数学" \
    --problem /tmp/hoshu_material/問題.pdf \
    --answer  /tmp/hoshu_material/解答.pdf
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

# ---------------------------------------------------------------------------
# env 読み込み
# ---------------------------------------------------------------------------

ENV_PATH = os.path.expanduser("~/studygram/.env")

def load_env() -> dict:
    env = {}
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v.strip('"').strip("'")
    return env


def require_env(env: dict, *keys) -> None:
    missing = [k for k in keys if not env.get(k)]
    if missing:
        print(f"ERROR: {ENV_PATH} に未設定: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Supabase REST helpers
# ---------------------------------------------------------------------------

class Supabase:
    def __init__(self, url: str, anon_key: str):
        self.url = url.rstrip("/")
        self.anon_key = anon_key

    def _headers(self, extra: dict | None = None) -> dict:
        h = {
            "apikey": self.anon_key,
            "Authorization": f"Bearer {self.anon_key}",
            "Content-Type": "application/json",
        }
        if extra:
            h.update(extra)
        return h

    def _request(self, req: urllib.request.Request):
        try:
            return urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            print(f"ERROR: Supabase {e.code} {e.reason}", file=sys.stderr)
            print(f"  URL: {req.full_url}", file=sys.stderr)
            print(f"  Body: {body[:500]}", file=sys.stderr)
            sys.exit(1)

    def get(self, table: str, params: str) -> list:
        url = f"{self.url}/rest/v1/{table}?{params}"
        req = urllib.request.Request(url, headers=self._headers())
        with self._request(req) as resp:
            return json.loads(resp.read())

    def post(self, table: str, data: dict) -> dict:
        url = f"{self.url}/rest/v1/{table}"
        body = json.dumps(data).encode()
        headers = self._headers({"Prefer": "return=representation"})
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with self._request(req) as resp:
            rows = json.loads(resp.read())
            return rows[0] if rows else {}

    def patch(self, table: str, params: str, data: dict) -> None:
        url = f"{self.url}/rest/v1/{table}?{params}"
        body = json.dumps(data).encode()
        headers = self._headers({"Prefer": "return=minimal"})
        req = urllib.request.Request(url, data=body, headers=headers, method="PATCH")
        with self._request(req) as resp:
            pass  # 204 No Content


# ---------------------------------------------------------------------------
# R2 upload
# ---------------------------------------------------------------------------

def upload_to_r2(env: dict, local_path: str, r2_key: str, content_type: str) -> int:
    import boto3
    s3 = boto3.client(
        "s3",
        endpoint_url=env["R2_ENDPOINT"],
        aws_access_key_id=env["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )
    size = os.path.getsize(local_path)
    s3.upload_file(local_path, env["R2_BUCKET_NAME"], r2_key,
                   ExtraArgs={"ContentType": content_type})
    return size


# ---------------------------------------------------------------------------
# student lookup
# ---------------------------------------------------------------------------

def find_student(sb: Supabase, name: str) -> dict | None:
    """名前で生徒を検索（name, atama_student_name の両方を試す）"""
    # まず name で完全一致
    rows = sb.get("app_users", f"name=eq.{urllib.parse.quote(name)}&role=eq.student&select=id,name")
    if rows:
        return rows[0]
    # スペースなし版で atama_student_name を試す
    compact = name.replace(" ", "").replace("　", "")
    rows = sb.get("app_users", f"atama_student_name=eq.{urllib.parse.quote(compact)}&role=eq.student&select=id,name,atama_student_name")
    if rows:
        return rows[0]
    # スペースあり版
    rows = sb.get("app_users", f"atama_student_name=eq.{urllib.parse.quote(name)}&role=eq.student&select=id,name,atama_student_name")
    if rows:
        return rows[0]
    # 部分一致 (ilike) — スペースあり・なし両方試す
    for q in [name, compact]:
        rows = sb.get("app_users", f"name=ilike.*{urllib.parse.quote(q)}*&role=eq.student&select=id,name")
        if rows:
            return rows[0]
    # 姓名分割で前方一致
    parts = name.replace("　", " ").split()
    if len(parts) >= 2:
        rows = sb.get("app_users", f"name=ilike.{urllib.parse.quote(parts[0])}*&role=eq.student&select=id,name")
        if rows:
            return rows[0]
    # スペースなし入力 → 各位置にスペースを挿入して試す（例: "鎮守杏" → "鎮守 杏"）
    if " " not in name and "　" not in name and len(name) >= 2:
        for i in range(1, len(name)):
            spaced = name[:i] + " " + name[i:]
            rows = sb.get("app_users", f"name=eq.{urllib.parse.quote(spaced)}&role=eq.student&select=id,name")
            if rows:
                return rows[0]
    return None


def find_admin(sb: Supabase) -> str:
    rows = sb.get("app_users", "role=eq.admin&select=id&limit=1")
    if not rows:
        print("ERROR: admin ユーザーが見つかりません", file=sys.stderr)
        sys.exit(1)
    return rows[0]["id"]


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="補習プリント＆動画をR2+Supabaseにアップロード")
    parser.add_argument("--student", help="生徒名（新規作成時に必須）")
    parser.add_argument("--title", help="プリントタイトル（新規作成時に必須）")
    parser.add_argument("--subject", help="教科名（新規作成時に必須）")
    parser.add_argument("--replace", metavar="PRINT_ID", help="既存プリントを差し替える場合のprint_id")
    parser.add_argument("--problem", required=True, help="問題PDFのパス")
    parser.add_argument("--answer", required=True, help="解答PDFのパス")
    parser.add_argument("--video", help="動画MP4のパス（省略可）")
    args = parser.parse_args()

    # バリデーション
    if not args.replace and not (args.student and args.title and args.subject):
        parser.error("新規作成時は --student, --title, --subject が必須です")

    for path in [args.problem, args.answer] + ([args.video] if args.video else []):
        if not os.path.exists(path):
            print(f"ERROR: ファイルが見つかりません: {path}", file=sys.stderr)
            sys.exit(1)

    # env
    env = load_env()
    require_env(env, "VITE_SUPABASE_URL", "VITE_SUPABASE_ANON_KEY",
                "R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME")

    sb = Supabase(env["VITE_SUPABASE_URL"], env["VITE_SUPABASE_ANON_KEY"])

    # --- 差し替えモード ---
    if args.replace:
        print_id = args.replace
        print(f"差し替えモード: print_id={print_id}")

        # 存在確認
        rows = sb.get("hoshu_prints", f"id=eq.{print_id}&select=id,title")
        if not rows:
            print(f"ERROR: print_id={print_id} が見つかりません", file=sys.stderr)
            sys.exit(1)
        print(f"  対象: {rows[0]['title']}")

    # --- 新規作成モード ---
    else:
        # 生徒検索
        student = find_student(sb, args.student)
        if not student:
            print(f"ERROR: 生徒 '{args.student}' が見つかりません", file=sys.stderr)
            # 全生徒一覧
            all_students = sb.get("app_users", "role=eq.student&select=id,name&order=name")
            print("  登録済み生徒一覧:", file=sys.stderr)
            for s in all_students:
                print(f"    - {s['name']}", file=sys.stderr)
            sys.exit(1)
        print(f"生徒: {student['name']} (id={student['id']})")

        admin_id = find_admin(sb)
        print_id = None  # insert で自動生成

    # --- R2 アップロード ---
    prefix = f"prints/{args.replace}" if args.replace else None

    if not args.replace:
        import uuid
        print_id = str(uuid.uuid4())
        prefix = f"prints/{print_id}"

    print(f"\nR2 アップロード中...")

    problem_key = f"{prefix}/problem.pdf"
    problem_size = upload_to_r2(env, args.problem, problem_key, "application/pdf")
    print(f"  ✓ problem.pdf ({problem_size:,} bytes)")

    answer_key = f"{prefix}/answer.pdf"
    answer_size = upload_to_r2(env, args.answer, answer_key, "application/pdf")
    print(f"  ✓ answer.pdf ({answer_size:,} bytes)")

    video_size = None
    video_key = None
    if args.video:
        video_key = f"{prefix}/video.mp4"
        video_size = upload_to_r2(env, args.video, video_key, "video/mp4")
        print(f"  ✓ video.mp4 ({video_size:,} bytes)")

    # --- DB 更新 ---
    print(f"\nDB 更新中...")

    if args.replace:
        patch_data = {
            "problem_pdf_r2_key": problem_key,
            "answer_pdf_r2_key": answer_key,
            "problem_pdf_size": problem_size,
            "answer_pdf_size": answer_size,
        }
        if video_key:
            patch_data["video_r2_key"] = video_key
            patch_data["video_size"] = video_size
        sb.patch("hoshu_prints", f"id=eq.{print_id}", patch_data)
        print(f"  ✓ hoshu_prints 更新完了")

    else:
        insert_data = {
            "id": print_id,
            "title": args.title,
            "subject": args.subject,
            "problem_pdf_r2_key": problem_key,
            "answer_pdf_r2_key": answer_key,
            "problem_pdf_size": problem_size,
            "answer_pdf_size": answer_size,
            "created_by": admin_id,
        }
        if video_key:
            insert_data["video_r2_key"] = video_key
            insert_data["video_size"] = video_size
        record = sb.post("hoshu_prints", insert_data)
        print(f"  ✓ hoshu_prints 作成: {record.get('id', print_id)}")

        # 生徒に配信
        sb.post("hoshu_print_assignments", {
            "print_id": print_id,
            "student_id": student["id"],
            "assigned_by": admin_id,
        })
        print(f"  ✓ {student['name']} に配信完了")

    # --- 完了 ---
    print(f"\n完了! print_id={print_id}")


if __name__ == "__main__":
    main()
