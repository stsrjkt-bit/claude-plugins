---
name: card-builder
description: さとう数理塾「お悩み解決カード」制作ワークフロー（リサーチ → 生成 → リファイン → プレビュー → エクスポート）
user_invocable: true
---

# /card-builder — お悩み解決カード制作スキル

さとう数理塾のホームページ掲載用「お悩み解決カード」を、リサーチからエクスポートまで一貫して制作するスキルです。

## データディレクトリ

```
~/sato-card-builder/
├── schema/types.ts          # CardData 型定義（参照用）
├── context/profile.md       # さとう数理塾プロフィール
├── context/competitors.md   # 競合塾データ
├── templates/preview.html   # HTMLプレビューテンプレート
└── output/                  # 生成物出力先
```

---

## ワークフロー（8フェーズ）

以下のフェーズを順番に実行してください。各フェーズの完了後、ユーザーに結果を提示して確認を取ってから次のフェーズに進むこと。

---

### Phase 0: ギャップ分析（既存カード棚卸し）

**まず最初に**、本番サイトに掲載中の既存カードを読み込み、指定期間のカバレッジを分析する。

**手順:**
1. `~/stsrjk-web-netlify/src/data/problemSolverCards.ts` を読み込む
2. 全カードの `displayPeriod` を解析し、指定期間（ユーザーが未指定なら現在月〜+1月）に表示されるカードを抽出
3. 以下の学年セグメントごとにカバレッジを集計:
   - 小6 / 新中1
   - 中1 / 新中2
   - 中2 / 新中3
   - 中3（公立入試組）
   - 中3→新高1（内部進学組）
   - 高1
   - 高2 / 新高3
   - 高3
4. 各セグメントについて「カード有/無」と「間もなく期限切れ」を判定

**表示期間の判定ロジック:**
- `start <= end` の場合: `currentMonth >= start && currentMonth <= end`
- `start > end` の場合（年またぎ）: `currentMonth >= start || currentMonth <= end`

**出力形式:**
ユーザーに以下の表を提示:

```
| 学年セグメント | 既存カード数 | 期限切れ予定 | 状況 |
|--------------|:-----------:|:-----------:|------|
| 小6/新中1     | 2           | 0           | OK   |
| 中1/新中2     | 0           | -           | 空白 |
| ...          | ...         | ...         | ...  |
```

さらに、**穴のあるセグメント**について:
- なぜこの時期にそのセグメントの悩みが顕在化するか（2〜3行の仮説）
- カード化の優先度（高/中/低）
- 推奨カードの方向性（1行）

ユーザーに「どのセグメント向けのカードを作るか」を選んでもらう。
複数選択も可。選択結果を Phase 1 以降に引き継ぐ。

**注意:**
- `git pull` は実行しない（ユーザーが事前に済ませている前提）
- ファイルが見つからない場合はユーザーに確認する

---

### Phase 1: ヒアリング

Phase 0 で選択されたセグメントを前提に、以下を確認する（AskUserQuestion を使用）:

1. **対象学年**: Phase 0 の選択結果をデフォルト提示
2. **表示期間**: 開始月〜終了月（Phase 0 の分析期間をデフォルト提示）
3. **目標**: 例: 上位公立高校受験、大学受験理系、定期テスト対策
4. **補足メモ**: 任意（特定のターゲット像、既存データの有無など）
5. **既存リサーチデータ**: あれば受け取る

---

### Phase 2: マーケティングリサーチ

WebSearch を使い、沼津・三島エリアの塾市場を調査する。

**調査項目:**
- 競合塾の評判・料金・口コミ
- 対象時期の保護者・生徒の悩み（テスト日程、受験スケジュール、学校行事等）
- 地域特有の事情（静岡県学力調査、内申制度等）

**出力形式:** 3〜6セグメントの構造化リサーチ（S1〜S6）

各セグメントに含めるもの:
1. セグメント名（短い一文）
2. 想定gradeTags（例: 中2, 中3）
3. 想定target（例: 上位公立高校受験）
4. 想定tags（3〜6個）
5. 属性・状況（家庭/学力帯/学校/部活/塾利用状況）
6. なぜ「その期間」に悩みが強くなるか
7. 悩みの構造
8. 保護者が実際に言いそうな一言（2〜4個）
9. 生徒本人が実際に言いそうな一言（2〜4個）

**制約:**
- 漠然とした一般論禁止 → 具体的な地域・競合名・場面を記載
- カードのコピー（title, solution_summary）はこのフェーズで生成しない
- 最後に「最優先でカード化すべきセグメント」を1つ選び、理由を3点で記載

---

### Phase 3: 商圏分析

WebSearch を使い、沼津市沢田町1-3 周辺を調査する。

**調査項目:**
- 半径1km / 3km以内の中学校・高校
- 最寄駅からの距離・通学経路
- 地理的障壁（川、線路等）
- 通塾パターンの推測（徒歩 / 自転車 / 送迎）

**出力形式:**
- A. 1km商圏まとめ
- B. 3km商圏まとめ
- C. 通塾導線パターン（3つ）
- D. カード化できる「地域フック」10個

---

### Phase 4: カード生成

リサーチ結果を基に CardData JSON を生成する。

**学年別の指導方針（強みカタログから選択）:**

#### 小中学生向け（C1〜C9）
- **C1**: 数学から立て直す専門塾
- **C2**: "できる子たち"との差を放置しない
- **C3**: AI教材が新単元に必要な復習単元を自動提案 × 短い解説 × 確認テスト
- **C4**: 家でも塾でも同じ流れで進められる
- **C5**: 平日夜3時間の"半こもり空間" × 自由通塾制
- **C6**: 定期テストも高校入試も整理
- **C7**: 5教科サポート
- **C8**: 塾長一貫担当
- **C9**: 公立トップ校への土台

#### 高校生向け（H1〜H9）
- **H1**: 数学から立て直す理系専門塾
- **H2**: 高校数学の"壁"を前提にした指導
- **H3**: AI教材が新単元に必要な復習単元を自動提案し土台完成
- **H4**: AI質問チャット × 講師
- **H5**: 平日夜3時間の"半こもり空間" × 自由通塾制
- **H6**: 理系3科目＋英語トータルサポート
- **H7**: 共通テスト〜個別試験の設計
- **H8**: 塾長一貫担当
- **H9**: 理系の選択肢を"守る"

**生成ルール:**

| 項目 | ルール |
|------|--------|
| `quickAnswers` | **必ず3つ**（原因 / 対策 / 目標 or 現状分析 / 対策 / 未来） |
| `actions.guide.content.text` | **80〜100文字、2〜3文** |
| `actions.faq` | **必ず2つ**。カードのテーマに直結する質問にする（汎用的な「いつから？」「いくら？」等は避ける） |
| `actions.recommendPoints` | **必ず3つ**（具体的な価値提案） |
| `voice.parent` | 保護者のリアルな不安の声 |
| `voice.child` | 生徒のリアルな悩みの声 |
| `title` | 共感を呼ぶ呼びかけ（命令調でない） |
| `gradeTags` | 必須。対象学年を明記（下記「新学年タグ」ルール参照） |
| `tags` | 3〜6個の短いキーワード |
| `solution_summary` | headは要約、bodyは詳細説明 |

**新学年タグのルール:**

年度切り替え期（2〜4月頃）に表示するカードでは、通常の学年タグに加えて「新○○」タグを追加する。
各タグに `displayPeriod` を設定し、フロントが月に応じて出し分ける。

例: 現中1 → 新中2 への切り替え
```json
"gradeTags": [
  { "id": "...__gt_1", "label": "中1", "displayPeriod": { "start": 4, "end": 1 } },
  { "id": "...__gt_2", "label": "新中2", "displayPeriod": { "start": 2, "end": 3 } }
]
```

マッピング表（`displayPeriod` は `{ "start": 2, "end": 3 }` を基本とする）:
| 通常タグ | 新タグ |
|---------|--------|
| 小6 | 新中1 |
| 中1 | 新中2 |
| 中2 | 新中3 |
| 中3 | 新高1 |
| 高1 | 新高2 |
| 高2 | 新高3 |

- `displayPeriod` を省略した gradeTag はカード全体の表示期間に従う（従来互換）
- 通年カード（例: start=4, end=3）でも、2〜3月は「新」タグで表示される
- 「新」タグの期間はデフォルト 2〜3月だが、カードの性質に応じて調整可

**トーン＆マナー:**
- 上から目線にならず、寄り添うトーン
- 「絶対」「必ず」は使わない
- 地域フック（学校名、地名等）を自然に含める

**禁止表現:**
- 「通い放題」「毎日通える」 → 「自由通塾制」「曜日固定なし」「回数制限なし」等で表現
- 「短期利用」「春休みだけ」 → さとう数理塾は短期利用を受け付けていない
- 事実と異なるサービス内容を書かない（profile.md に記載のない制度を勝手に作らない）

**ID体系:**
```
batchId = gen_YYYYMMDDHHmmssSSS
cardId = {batchId}-{XX}  (XX = 01, 02, ...)
fieldId = {cardId}__{prefix}_{seqNum}
```

例:
- `gen_20260219120530123-01__gt_1` (gradeTag)
- `gen_20260219120530123-01__tag_1` (tag)
- `gen_20260219120530123-01__voice_p` (parent voice)
- `gen_20260219120530123-01__qa_1` (quickAnswer)
- `gen_20260219120530123-01__rp_1` (recommendPoint)
- `gen_20260219120530123-01__faq_q_1` (FAQ question)

**CardData JSON スキーマ:**

```typescript
interface CardData {
  id: string;
  category: string;
  displayPeriod: { start: number; end: number };  // 1 to 12
  gradeTags: { id: string; label: string; displayPeriod?: { start: number; end: number } }[];
  target: { id: string; label: string };
  tags: { id: string; label: string }[];
  title: { id: string; text: string };
  voice: {
    parent: { id: string; text: string };
    child: { id: string; text: string };
  };
  solution_summary: {
    head: { id: string; text: string };
    body: { id: string; text: string };
  };
  quickAnswers: { id: string; label: string; text: string }[];
  actions: {
    guide: {
      title: { id: string; text: string };
      content: { id: string; text: string };
    };
    faq: { q: { id: string; text: string }; a: { id: string; text: string } }[];
    recommendPoints: { id: string; text: string }[];
    linkUrl?: { id: string; url: string };
    linkLabel?: { id: string; text: string };
  };
}
```

**出力:** `~/sato-card-builder/output/{batchId}.json`

---

### Phase 5: リファイン（競合ギャップ分析 → recommendPoints 最適化）

#### Step 5a: 競合ギャップ分析

1. `~/sato-card-builder/context/profile.md` を読み込む
2. `~/sato-card-builder/context/competitors.md` を読み込む
3. WebSearch で競合の最新情報を補完（料金、評判、振替規定、講師の質、質問対応）

**出力構造:**
- **保護者の不満**（3〜6件）: 各項目に【競合】【対象】【場面】【不満】【根拠】【確度】を記載
- **生徒の不満**（3〜6件）: 同上
- **運営ギャップ**（2〜5件）: 振替不可、テスト前休み等のシステム的問題
- **トリガー**（2〜4件）: 転塾を決意する瞬間の短い一言（例: 「また自習室埋まってた...」）
- **強み対応表**: 各ギャップに対してさとう数理塾がどう解決するかの {gap, strength} ペア

**禁止事項:**
- キャッチコピーや集客施策の提案は禁止（別フェーズ）
- 「一般論」禁止 → 「個別指導塾は〜」ではなく具体的競合名で記述
- 推測のみ禁止 → 根拠を明記し、確度を記載

#### Step 5b: recommendPoints 最適化（決め打ち）

競合ギャップ分析の結果を踏まえ、カードの内容・ターゲットに最も刺さる `recommendPoints` を **1案のみ** 生成する。
3案を出してユーザーに選ばせる必要はない。以下の3軸をバランスよくミックスすること:

- **戦略・成績**: カードの悩みに直結する具体的な解決力（AI教材が新単元に必要な復習単元を自動提案、プラン設計等）
- **信頼・安心**: 塾長一貫担当、教員免許、質問しやすさ
- **コスパ・柔軟性**: 定額制、自由通塾、追加費用なし

**ルール:**
- 3ポイント（必ず3つ）
- 各ポイントは上記3軸のいずれかに対応（1軸に偏らない）
- 具体的かつ短文
- 競合名は出さない
- profile.md に記載のある事実のみ使用

---

### Phase 6: プレビュー & テキスト調整

選択された案を反映した CardData で HTMLプレビューを生成し、ユーザーと対話的にテキストを調整する。

**手順:**
1. `~/sato-card-builder/templates/preview.html` を読み込む
2. **Node.js** でテンプレート内の `__CARD_DATA__` を `JSON.stringify([cardData])` で置換（`sed` は JSON の特殊文字で壊れるため使用禁止）
3. `~/sato-card-builder/output/{batchId}_preview.html` に書き出す
4. chrome-devtools MCP で `file:///...` に navigate して表示

**テンプレート置換の注意:**
- テンプレートの JS コメント内に `__CARD_DATA__` という文字列を**絶対に書かない**こと（置換で JS 構文エラーになる）
- 置換は `node -e` ワンライナーで実行:
  ```bash
  node -e "const fs=require('fs'); const tpl=fs.readFileSync('template.html','utf8'); const data=JSON.parse(fs.readFileSync('data.json','utf8')); fs.writeFileSync('output.html', tpl.replace('__CARD_DATA__', JSON.stringify(data,null,2)));"
  ```

**マーク機能付きプレビュー:**
- 各テキスト要素に番号バッジ（1〜18）が表示される
- ユーザーがテキストをクリックすると赤くハイライト（マーク）される
- 画面下部にマーク済みリストが表示される
- `evaluate_script` でマーク状態を取得可能: `document.querySelectorAll('.marked')` → `dataset.mark` でフィールド名取得
- ユーザーがターミナルで修正指示 → JSON を Edit → プレビュー再生成 → リロード
- IME が効かない環境（Crostini等）でも、マーク＋ターミナル指示で編集可能

**テンプレート仕様:**
- Tailwind CSS CDN で自己完結
- Lucide Icons CDN
- カード開閉トグル付き（デフォルト展開）
- カラーパレット: #009DE0（シアン）、#2DD4BF（ティール）、#D6DE26（イエロー）

**プレビュー更新の繰り返し:**
JSON 修正 → プレビュー HTML 再生成（CARDS 配列を正規表現で置換）→ リロード → 確認、を修正がなくなるまで繰り返す。

---

### Phase 7: 承認 & 本番デプロイ

ユーザーの GO サイン後:

#### 7a: 最終 JSON 保存
`~/sato-card-builder/output/{batchId}_final.json` に保存

#### 7b: 本番サイトに設置

1. `~/stsrjk-web-netlify/src/data/problemSolverCards.ts` の `ALL_CARDS` 配列末尾にカードを追加
2. **IIFE パターン**で記述すること（既存カードと一貫性を保つ）:
   ```typescript
   // {表示期間}向け ({ターゲット概要})
   (() => {
     const id = "{cardId}";
     return {
       id,
       category: "...",
       displayPeriod: { start: N, end: N },
       gradeTags: [
         { id: `${id}__gt_1`, label: "...", displayPeriod: { start: N, end: N } },
       ],
       // ... 以下すべて `${id}__xxx` テンプレートリテラルで ID を記述
     };
   })()
   ```
3. `displayPeriod` の `start`/`end` は**必ず number 型**（string ではない）
4. フィーチャーブランチを作成: `feat/add-card-{簡潔な説明}`
5. コミット＆プッシュ
6. `gh pr create` で PR 作成
7. コードレビュー（Gemini Code Assist）が来たら対応してプッシュ
8. ユーザーにマージを依頼

---

## 注意事項

- 各フェーズの間でユーザーに確認を取ること
- Phase 0 は必ず最初に実行し、既存カードとの重複を防ぐ
- リサーチは WebSearch を使用し、Gemini API は不要
- HTMLプレビューはスタンドアロン（ネットワーク接続のみ CDN 取得に必要）
- 生成物はすべて `~/sato-card-builder/output/` に保存
- 既存カードデータ: `~/stsrjk-web-netlify/src/data/problemSolverCards.ts`
- Phase 0 でリポジトリの最新化（git pull）が必要な場合はユーザーに確認する
- テンプレートの `__CARD_DATA__` 置換は必ず **Node.js** で行う（sed/awk 禁止）
- `displayPeriod` の値は JSON では number 型にする（string にしない）
- profile.md に記載のない事実を勝手に書かない（FAQの回答も含む）
- ブラウザ操作は **chrome-devtools MCP** を使う（claude-in-chrome は非推奨）
