## atama+ COACH
- URL: https://coach.atama.plus/
- ログインページ: https://coach.atama.plus/public/login
- ログインID: claude
- 組織ID: 5566
- 認証情報: `~/.env.atama`（ATAMA_ID, ATAMA_PW）

## API参考
- 生徒一覧: `GET /v3/organizations/5566/organization_users/?sort=last_seen&limit=300&include_session_summary=true&include_personal_info=true&include_study_stats=true`
- 認証ヘッダー: `Authorization: ATAMA-SessionToken {token}`

## SPA操作ルール
- **ページ遷移**: `take_snapshot` → `click(uid)` を使う（`evaluate_script` の JS クリックでは SPA 遷移しない）
- **タブ切替・メニュー**: `evaluate_script` で `el.textContent.trim()` マッチ → `el.click()` が使える
- **教科選択メニュー**: `take_snapshot` → `click(uid)` を使う（`evaluate_script` は不安定）
- **Ionicセレクト**: ポップオーバーが開いた後にテキスト要素をクリック
- **モーダル閉じ**: `take_snapshot` → 「閉じる」の uid で `click(uid)`。uid が無効なら `evaluate_script` で `el.textContent.trim() === '閉じる'` を探してクリック
- **スクロール**: `evaluate_script` で `document.querySelector('.inner-scroll').scrollTop = N`
- **snapshot vs screenshot**: snapshot はスクロール位置に関係なく全データ取得。screenshot は表示範囲のみ
- **snapshot filePath必須**: 生徒詳細ページ以降は `take_snapshot(filePath=...)` でファイル保存 → `Grep` で検索

## URL パターン
- ログインページ: `/public/login`
- ホーム: `/user/home`
- 生徒詳細: `/user/home/organization-users/{id}/detail`

## 出力先
- 中間ファイル: `/tmp/hoshu_material/`
- 中学生PDF: `/mnt/c/Users/stsrj/Desktop/補習プリント/`（手渡し配布用）
- 高校生PDF: StudyGram にアップロード（`~/.env.studygram` 必要）
- StudyGram 未設定時: 高校生も `/mnt/c/Users/stsrj/Desktop/補習プリント/` にフォールバック
