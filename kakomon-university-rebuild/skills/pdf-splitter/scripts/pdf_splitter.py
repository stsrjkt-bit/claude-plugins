#!/usr/bin/env python3
"""
pdf_splitter.py - 大学入試 理科PDF 科目自動分割ツール

Gemini FlashにPDFを丸ごと投げて全ページを一括分類し、科目別に自動分割する。
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
import shutil
import subprocess


CLASSIFICATION_PROMPT = """あなたは大学入試の過去問PDF解析の専門家です。
このPDFは大学入試の理科の問題冊子で、複数の科目（物理・化学・生物・地学など）が
1つのPDFにまとめられています。

全ページを1ページずつ確認し、以下のJSON形式で分類結果を返してください。

出力フォーマット（JSONのみ、他のテキストは不要）:
{
  "total_pages": <総ページ数>,
  "pages": [
    {
      "page": <ページ番号（1始まり）>,
      "type": "<分類>",
      "subject": "<科目 or null>",
      "note": "<簡潔な説明>"
    }
  ]
}

分類（type）の種類:
- "cover": 表紙、目次、注意事項
- "problem": 問題ページ
- "answer_sheet": 解答用紙
- "blank": 白紙ページ（何も印刷されていない、または「白紙」と書かれている）
- "other": その他

科目（subject）の値:
- "physics": 物理
- "chemistry": 化学
- "biology": 生物
- "earth_science": 地学
- null: 科目に属さない（表紙・白紙など）

重要な注意事項:
- 全ページを漏れなく記載すること（pagesの要素数 == total_pages であること）
- ページ番号はPDF上の物理的なページ番号（1始まり）を使う（印刷されたフッター番号ではない）
- 白紙ページを見落とさないこと（白紙ページの存在がページオフセットずれの主要原因）
- 解答用紙は問題ページとは別にtypeを"answer_sheet"とすること
- 解答用紙がどの科目のものかも必ずsubjectに記載すること
- noteには、そのページに見える見出し・科目名・問題番号などをそのまま書く
- JSONのみ出力し、```json等のマークダウン記法は使わないこと"""


def classify_pdf_pages(pdf_path: str, model_name: str | None = None) -> dict:
    """
    PDFをGeminiに送り、全ページを分類する。

    この環境では PyPI からの pip install ができないことがあるため、
    PythonのGemini SDKには依存しない。

    代わりに kakomon-collector 側に置いた Node スクリプト
    `scripts/pdf_page_classifier.mjs` を呼び出す。
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("エラー: GEMINI_API_KEY (または GOOGLE_API_KEY) を設定してください", file=sys.stderr)
        sys.exit(1)

    node = shutil.which("node")
    if not node:
        print("エラー: node が見つかりません", file=sys.stderr)
        sys.exit(1)

    classifier = Path("/home/stsrjkt/kakomon-collector/scripts/pdf_page_classifier.mjs")
    if not classifier.exists():
        print(f"エラー: classifier が見つかりません: {classifier}", file=sys.stderr)
        sys.exit(1)

    model = model_name or os.environ.get("GEMINI_MODEL")
    if not model:
        print("エラー: GEMINI_MODEL を設定してください（または --model で指定）", file=sys.stderr)
        sys.exit(1)
    pdf_size_mb = Path(pdf_path).stat().st_size / (1024 * 1024)
    print(f"  Gemini ({model}) にPDF送信中... ({pdf_size_mb:.1f}MB)", file=sys.stderr)

    cmd = [node, str(classifier), pdf_path, "--model", model]
    try:
        proc = subprocess.run(
            cmd,
            cwd="/home/stsrjkt/kakomon-collector",
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print("エラー: Gemini分類に失敗しました", file=sys.stderr)
        if e.stderr:
            print(e.stderr[:4000], file=sys.stderr)
        sys.exit(1)

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        print(f"エラー: classifier 出力のJSONパースに失敗: {e}", file=sys.stderr)
        print(proc.stdout[:2000], file=sys.stderr)
        sys.exit(1)


def summarize_subjects(pages_data: list[dict]) -> dict:
    """ページ分類データから科目別の集計を生成する"""
    subjects = {}
    for p in pages_data:
        subj = p.get("subject")
        if subj is None:
            continue
        if subj not in subjects:
            subjects[subj] = {"problem_pages": [], "answer_pages": []}
        if p["type"] == "problem":
            subjects[subj]["problem_pages"].append(p["page"])
        elif p["type"] == "answer_sheet":
            subjects[subj]["answer_pages"].append(p["page"])
    return subjects


def print_summary(result: dict):
    """分類結果のサマリーを表示"""
    print(f"\n--- サマリー ---", file=sys.stderr)
    print(f"総ページ数: {result.get('total_pages', '不明')}", file=sys.stderr)

    blanks = [p["page"] for p in result.get("pages", []) if p.get("type") == "blank"]
    if blanks:
        print(f"白紙ページ: {blanks}", file=sys.stderr)

    for subj, info in result.get("subjects", {}).items():
        pp = info["problem_pages"]
        ap = info.get("answer_pages", [])
        if pp:
            page_range = f"p.{pp[0]}-{pp[-1]}" if len(pp) > 1 else f"p.{pp[0]}"
            line = f"  {subj}: 問題 {page_range} ({len(pp)}ページ)"
            if ap:
                line += f" + 解答用紙 p.{','.join(str(x) for x in ap)}"
            print(line, file=sys.stderr)


def select_review_pages(pages: list[dict]) -> list[int]:
    """
    Pick a small set of pages that matter for boundary/quality review.

    - First occurrence per subject
    - Subject transition pages (+/-1) within problem/answer_sheet streams
    - All blank pages
    - All answer_sheet pages
    - Always include page 1
    """
    wanted: set[int] = set()
    if not pages:
        return []

    total_pages = max(int(p.get("page", 0)) for p in pages if p.get("page")) or 0
    wanted.add(1)

    first_seen: set[str] = set()
    for p in pages:
        page_no = int(p.get("page"))
        p_type = p.get("type")
        subj = p.get("subject")

        if p_type == "blank":
            wanted.add(page_no)
        if p_type == "answer_sheet":
            wanted.add(page_no)

        if subj and subj not in first_seen and p_type in ("problem", "answer_sheet"):
            first_seen.add(subj)
            wanted.add(page_no)

    # Transition detection: compare consecutive relevant pages
    prev = None
    for p in pages:
        if p.get("type") not in ("problem", "answer_sheet"):
            continue
        if prev is not None:
            prev_subj = prev.get("subject")
            cur_subj = p.get("subject")
            if prev_subj != cur_subj:
                cur_page = int(p.get("page"))
                prev_page = int(prev.get("page"))
                for x in (prev_page - 1, prev_page, prev_page + 1, cur_page - 1, cur_page, cur_page + 1):
                    if 1 <= x <= total_pages:
                        wanted.add(x)
        prev = p

    return sorted(wanted)


def render_review_pack(pdf_path: str, classification: dict, output_dir: str, dpi: int = 144) -> str:
    """Render selected pages into PNGs + a simple index.md for human/Codex review."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    pages = classification.get("pages", [])
    wanted_pages = select_review_pages(pages)

    # Map page -> record for notes
    by_page = {int(p["page"]): p for p in pages if "page" in p}

    md_lines = []
    md_lines.append(f"# Review pack: {Path(pdf_path).name}")
    md_lines.append("")
    md_lines.append(f"- total_pages: {classification.get('total_pages')}")
    md_lines.append(f"- rendered: {len(wanted_pages)} pages (dpi={dpi})")
    md_lines.append("")
    md_lines.append("## Pages")

    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        print("エラー: pdftoppm が見つかりません（reviewに必要）", file=sys.stderr)
        sys.exit(1)

    for page_no in wanted_pages:
        img_name = f"page_{page_no:03d}.png"
        img_path = out / img_name
        prefix = out / f"__tmp_p{page_no:03d}"
        subprocess.run(
            [
                pdftoppm,
                "-f",
                str(page_no),
                "-l",
                str(page_no),
                "-png",
                "-r",
                str(dpi),
                pdf_path,
                str(prefix),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        generated = Path(f"{prefix}-1.png")
        if generated.exists():
            generated.replace(img_path)
        else:
            alt = Path(f"{prefix}.png")
            if alt.exists():
                alt.replace(img_path)

        rec = by_page.get(page_no, {})
        md_lines.append(f"### p.{page_no:03d}")
        md_lines.append(f"- type: {rec.get('type')}")
        md_lines.append(f"- subject: {rec.get('subject')}")
        if rec.get("note"):
            md_lines.append(f"- note: {rec.get('note')}")
        md_lines.append(f"- file: {img_name}")
        md_lines.append("")

    index_path = out / "index.md"
    index_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return str(index_path)


def split_pdf_by_subject(pdf_path: str, classification: dict, output_dir: str) -> list[str]:
    """分類結果に基づいてPDFを科目別に分割する"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    stem = Path(pdf_path).stem
    subjects = summarize_subjects(classification["pages"])
    created_files = []

    qpdf = shutil.which("qpdf")
    if not qpdf:
        print("エラー: qpdf が見つかりません（splitに必要）", file=sys.stderr)
        sys.exit(1)

    def pages_to_spec(pages: list[int]) -> str:
        pages = sorted(set(int(p) for p in pages))
        if not pages:
            return ""
        ranges = []
        start = prev = pages[0]
        for p in pages[1:]:
            if p == prev + 1:
                prev = p
                continue
            ranges.append(f"{start}-{prev}" if start != prev else f"{start}")
            start = prev = p
        ranges.append(f"{start}-{prev}" if start != prev else f"{start}")
        return ",".join(ranges)

    for subject_key, info in subjects.items():
        problem_pages = info["problem_pages"]
        if problem_pages:
            out_name = f"{stem}_{subject_key}.pdf"
            out_path = output_path / out_name
            spec = pages_to_spec(problem_pages)
            subprocess.run(
                [qpdf, pdf_path, "--pages", pdf_path, spec, "--", str(out_path)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            created_files.append(str(out_path))
            print(f"  ✓ {out_name} ({len(problem_pages)}ページ)", file=sys.stderr)

        answer_pages = info.get("answer_pages", [])
        if answer_pages:
            out_name = f"{stem}_{subject_key}_answer.pdf"
            out_path = output_path / out_name
            spec = pages_to_spec(answer_pages)
            subprocess.run(
                [qpdf, pdf_path, "--pages", pdf_path, spec, "--", str(out_path)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            created_files.append(str(out_path))
            print(f"  ✓ {out_name} ({len(answer_pages)}ページ)", file=sys.stderr)

    return created_files


def cmd_analyze(args):
    pdf_path = args.pdf
    if not Path(pdf_path).exists():
        print(f"エラー: ファイルが見つかりません: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    print(f"解析中: {pdf_path}", file=sys.stderr)
    result = classify_pdf_pages(pdf_path, args.model)
    result["file"] = Path(pdf_path).name
    result["subjects"] = summarize_subjects(result.get("pages", []))

    output_json = json.dumps(result, ensure_ascii=False, indent=2)

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(output_json, encoding="utf-8")
        print(f"  → {args.json} に保存しました", file=sys.stderr)
    else:
        print(output_json)

    print_summary(result)


def cmd_split(args):
    pdf_path = args.pdf
    if not Path(pdf_path).exists():
        print(f"エラー: ファイルが見つかりません: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = args.output or str(Path(pdf_path).parent)

    if args.classification:
        print(f"分類JSON読込: {args.classification}", file=sys.stderr)
        result = json.loads(Path(args.classification).read_text(encoding="utf-8"))
    else:
        print(f"解析中: {pdf_path}", file=sys.stderr)
        result = classify_pdf_pages(pdf_path, args.model)

    result["file"] = Path(pdf_path).name
    result["subjects"] = summarize_subjects(result.get("pages", []))

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    json_path = Path(output_dir) / (Path(pdf_path).stem + "_classification.json")
    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  → 分類結果: {json_path}", file=sys.stderr)
    print_summary(result)

    print(f"\n分割中...", file=sys.stderr)
    created = split_pdf_by_subject(pdf_path, result, output_dir)
    print(f"\n完了！ {len(created)}ファイル生成", file=sys.stderr)

def cmd_review(args):
    pdf_path = args.pdf
    if not Path(pdf_path).exists():
        print(f"エラー: ファイルが見つかりません: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    if args.classification:
        classification = json.loads(Path(args.classification).read_text(encoding="utf-8"))
    else:
        print(f"解析中: {pdf_path}", file=sys.stderr)
        classification = classify_pdf_pages(pdf_path, args.model)

    classification["file"] = Path(pdf_path).name
    classification["subjects"] = summarize_subjects(classification.get("pages", []))

    out_dir = args.output or str(Path(pdf_path).parent / (Path(pdf_path).stem + "_review"))
    index_md = render_review_pack(pdf_path, classification, out_dir, dpi=args.dpi)
    print_summary(classification)
    print(f"\n  → review pack: {out_dir}", file=sys.stderr)
    print(f"  → index: {index_md}", file=sys.stderr)


def cmd_batch(args):
    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        print(f"エラー: ディレクトリが見つかりません: {input_dir}", file=sys.stderr)
        sys.exit(1)

    output_dir = args.output or str(input_dir / "split")
    pdf_files = sorted(input_dir.glob("*.pdf"))

    if not pdf_files:
        print(f"PDFファイルが見つかりません: {input_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"{len(pdf_files)}個のPDFを処理します\n", file=sys.stderr)
    success_count = 0
    error_count = 0

    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"[{i}/{len(pdf_files)}] {pdf_path.name}", file=sys.stderr)
        try:
            result = classify_pdf_pages(str(pdf_path), args.model)
            result["file"] = pdf_path.name
            result["subjects"] = summarize_subjects(result.get("pages", []))

            pdf_output_dir = Path(output_dir) / pdf_path.stem
            pdf_output_dir.mkdir(parents=True, exist_ok=True)

            json_path = pdf_output_dir / "classification.json"
            json_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

            split_pdf_by_subject(str(pdf_path), result, str(pdf_output_dir))
            print_summary(result)
            print(f"  → {pdf_output_dir}/\n", file=sys.stderr)
            success_count += 1

        except Exception as e:
            print(f"  エラー: {e}\n", file=sys.stderr)
            error_count += 1
            continue

    print(f"バッチ処理完了！ 成功: {success_count} / エラー: {error_count}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="大学入試 理科PDF 科目自動分割ツール（Gemini Flash使用）"
    )
    parser.add_argument("--model", default=None,
        help="Geminiモデル名（環境変数GEMINI_MODEL or --model で指定必須）")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_analyze = subparsers.add_parser("analyze", help="PDFを解析してページ分類を出力")
    p_analyze.add_argument("pdf", help="入力PDFファイル")
    p_analyze.add_argument("--json", help="結果をJSONファイルに保存")
    p_analyze.set_defaults(func=cmd_analyze)

    p_split = subparsers.add_parser("split", help="PDFを解析して科目別に分割")
    p_split.add_argument("pdf", help="入力PDFファイル")
    p_split.add_argument("-o", "--output", help="出力ディレクトリ")
    p_split.add_argument("--classification", help="analyzeで作った(編集済み)分類JSONを使用（Gemini再実行しない）")
    p_split.set_defaults(func=cmd_split)

    p_review = subparsers.add_parser("review", help="境界確認用のページPNGを出力（人間/Codexの目視確認用）")
    p_review.add_argument("pdf", help="入力PDFファイル")
    p_review.add_argument("-o", "--output", help="出力ディレクトリ（デフォルト: <stem>_review/）")
    p_review.add_argument("--classification", help="analyzeで作った(編集済み)分類JSONを使用（Gemini再実行しない）")
    p_review.add_argument("--dpi", type=int, default=144, help="PNG解像度（デフォルト: 144）")
    p_review.set_defaults(func=cmd_review)

    p_batch = subparsers.add_parser("batch", help="ディレクトリ内の全PDFを一括処理")
    p_batch.add_argument("input_dir", help="入力ディレクトリ")
    p_batch.add_argument("-o", "--output", help="出力ディレクトリ")
    p_batch.set_defaults(func=cmd_batch)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
