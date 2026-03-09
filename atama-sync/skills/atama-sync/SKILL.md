---
name: atama-sync
description: atama+ COACH → StudyTracker スタンプ同期。「スタンプ押して」で手動実行。
args:
  - name: command
    description: "'run' で全生徒同期実行、引数なしで概要表示"
---

# /atama-sync — atama+ スタンプ同期

## 概要

atama+ COACH の proficiencies API から全生徒のクリア済みユニットを取得し、
StudyTracker の `atama_unit_stamps` テーブルに記録する。

**運用モデル**: ユーザーが「スタンプ押して」と言ったら手動実行（cron なし）。

**核心**: COACH API は「土台科目」のユニットを混ぜて返す（例: 物理を聞いても算数・中学数学が含まれる）。
`atama_units` テーブルで DB逆引きし、正しい教科のユニットだけを記録する。

## 引数判定

- **引数なし** → この SKILL.md の概要を表示
- **`run`** → 全生徒の同期を実行（下記「run 実行手順」に従う）

## アーキテクチャ

```
┌─────────────┐    covered_unit_ids    ┌──────────────┐
│ COACH API   │ ────────────────────→  │ DB逆引き      │
│ proficiencies│   (土台科目混在)       │ atama_units   │
└─────────────┘                        └──────┬───────┘
                                              │ subject_key でフィルタ
                                              ▼
                                       ┌──────────────┐
                                       │ UPSERT into   │
                                       │ unit_stamps   │
                                       └──────┬───────┘
                                              │
                                              ▼
                                       ┌──────────────┐
                                       │ Resend Email  │
                                       │ → 先生に通知   │
                                       └──────────────┘
```

## 同期対象

- **生徒**: DB の `app_users` で `atama_org_user_id IS NOT NULL AND is_active = true` の全員（現在12名）
- **教科**: 全23科目を全生徒に対して照会。未履修（404）は自動スキップ
- 全科目照会する理由: 土台科目経由で他教科のユニットもクリア済みになるため、全科目のデータを整えておく方が正確

### 23科目一覧

高校: math_2022, combined_math_high, english, classics, physics_2022, chemistry_2022, biology_2022, geography, japanese_history, world_history, geography_history, informatics_2022
中学: junior_japanese, junior_math, combined_math_junior, junior_english_v2, junior_science, junior_social_studies
小学: arithmetic, elementary_english, elementary_japanese, elementary_science, elementary_social_studies

## 土台科目問題（なぜ DB逆引きが必要か）

COACH の proficiencies API は、ある教科のクリア済みユニットを返す際に、
学習経路上の **前提科目（土台科目）** のユニットも含めて返す。

例: 杏さんの `physics_2022` を問い合わせた結果:
- `covered_unit_ids`: **225件**
- 内訳:
  - 物理 62件（本命）
  - 算数 65件、中学数学 56件、高校数学 9件、中学理科 16件（土台）
  - 未解決 17件（プレ物理等、DBに未登録）

`atama_units` テーブルには全4,702ユニットが正しい `subject_key` で登録されている。
ここで逆引きすることで、土台科目を確実に除外できる。

### ペア科目の重複

`math_2022` / `combined_math_high` および `junior_math` / `combined_math_junior` は unit_id を共有する。
両方の科目で API がデータを返すが、UNIQUE 制約 `(app_user_id, atama_unit_id)` により二重カウントは発生しない。

## COACH API 認証

```javascript
// ログイン
POST https://api.atama.plus/v3/session_token/
Headers:
  Content-Type: application/json
  x-atamaplus-app: teacher
  x-atamaplus-client: <base64 JSON {web: true, debug: false, git_revision: "..."}>
  x-atamaplus-device-info: <base64 JSON {manufacturer, model, platform, version}>
  Referer: https://coach.atama.plus/
Body: { username: ATAMA_ID, password: ATAMA_PW }
Response: { session_token: "..." }

// API呼び出し
GET https://api.atama.plus/v3/organization_users/{org_user_id}/subject_groups/{sg_id}/proficiencies/
Headers:
  Authorization: ATAMA-SessionToken {session_token}
  x-atamaplus-app: teacher
  （+ client, device-info, Referer）
```

- subject_group ID = DB の `subject_key`（完全一致）

## ファイル構成

| ファイル | 役割 |
|---------|------|
| `studygram/scripts/all-students-sync.mjs` | 全生徒同期スクリプト（メイン） |
| `studygram/scripts/verify-enrolled-subjects.mjs` | 各生徒の教科データ確認ツール |

## 環境変数（全て Doppler `sato-juku/dev_studygram`）

| 変数 | 用途 |
|------|------|
| `ATAMA_ID` | COACH ログインID（.env にもある） |
| `ATAMA_PW` | COACH パスワード（.env にもある） |
| `SUPABASE_ACCESS_TOKEN` | DB操作（Management API） |
| `RESEND_API_KEY` | メール送信 |

## run 実行手順

`/atama-sync run` が呼ばれたら、Claude は以下を順に実行する:

1. **環境変数セット**: studygram ディレクトリで `.env` を読み込み、Doppler からシークレットを取得
2. **スクリプト実行**: `node scripts/all-students-sync.mjs` を実行（約6分）
3. **結果報告**: スクリプト出力の要約をユーザーに報告（メールは自動送信される）

```bash
cd ~/studygram
source .env && export ATAMA_ID ATAMA_PW
export SUPABASE_ACCESS_TOKEN=$(doppler secrets get SUPABASE_ACCESS_TOKEN --project sato-juku --config dev_studygram --plain)
export RESEND_API_KEY=$(doppler secrets get RESEND_API_KEY --project sato-juku --config dev_studygram --plain)
node scripts/all-students-sync.mjs
```

実行時間: 約6分（12生徒 × 23科目 = 276 API呼び出し）

## メール通知

- 送信元: `info@stsrjk.com`（Resend 認証済みドメイン）
- 送信先: `stsrjkt@gmail.com`
- 件名: `[atama+] 全生徒スタンプ更新 +N件 YYYY年M月D日` または `同期完了`（変更なし時）
- 生徒ごとの教科別スタンプ数 + 新規件数をメール本文に記載

## DB テーブル

### app_users（関連カラム）
- `atama_org_user_id` — COACH の organization_user ID（12名に設定済み）
- `atama_username` — COACH のログインユーザー名

### atama_unit_stamps
- `(app_user_id, atama_unit_id)` — UNIQUE 制約
- `subject_key` — `atama_units` からの逆引き結果
- `stamp_source` — `'atama'`（自動同期）or `'manual'`（手動タップ）
- `mastery_achieved` — true
- `last_synced_at` — 同期日時

## トラブルシューティング

| 症状 | 原因 | 対処 |
|------|------|------|
| COACH login failed | パスワード変更 or セッション制限 | `.env` の ATAMA_PW を確認 |
| DB一致が0 | subject_key 不一致 | `atama_units` テーブルの subject_key を確認 |
| Supabase SQL エラー | ACCESS_TOKEN 期限切れ | Doppler で再取得 |
| 新規が常に0 | 生徒が学習していない | 正常動作（変更なしメールが届く） |

## 既知の課題

### 1. 未解決ユニット
プレ物理・プレ中学理科・小学算数のユニットが `atama_units` テーブルに未登録。
`scripts/scrape-atama-units.mjs` を `include_disabled_subjects=true` で再実行すれば解決。
ただしスタンプ記録には影響しない（該当教科を同期対象にしない限り）。

### 2. ペア科目の曖昧ユニット
`junior_math` と `combined_math_junior` の両方に存在するユニットがある。
UNIQUE制約で二重カウントは防止されるが、最初にINSERTした方の subject_key が記録される。
