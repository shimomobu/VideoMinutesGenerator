# CLAUDE.md

## 1. プロジェクト概要

- プロジェクト名: `VideoMinutesGenerator`
- 目的: 会議動画から議事録を自動生成する
- 主な出力:
  - 会議要約
  - 議題
  - 決定事項
  - 保留事項
  - ToDo
  - Markdown 議事録
  - JSON 出力
- 入力:
  - 会議動画ファイル（mp4 / mov / mkv）
- 基本方針:
  - 音声・動画はローカル処理
  - すべてのデータをローカル処理（Gemma 4 + Ollama）。外部送信なし
  - MVPを小さく順番に実装する

---

## 2. 現在の基準文書

以下の文書を常に優先して参照すること。

- `docs/requirements.md`
- `docs/architecture.md`
- `docs/task-breakdown.md`
- `docs/test-plan.md`

実装時は、上記文書に反する独自判断をしないこと。  
不明点があれば、まず既存文書との整合を確認すること。

---

## 3. 開発原則

### 3.1 実装方針
- TDD で進める
- 1回の作業は **1タスクのみ**
- 最小差分で実装する
- 他タスクの先回り実装をしない
- 必要以上の抽象化をしない
- 文書で合意した責務分割を崩さない

### 3.2 品質方針
- 先に失敗テストを書く
- テストを通してから完了報告する
- 既存テストを壊さない
- 回帰があれば原因を特定してから修正する
- 単体テストでは外部依存を必ずモック化する

### 3.3 文書整合方針
- 実装が文書とズレる場合は、勝手に実装を優先しない
- ズレを見つけたら、差分を明示して確認を促す
- 文書修正が必要なら最小差分で反映する

---

## 4. 現在のアーキテクチャ前提

### 4.1 処理フロー
`ingest -> preprocess -> asr -> analysis -> formatter -> export -> pipeline`

### 4.2 analysis の責務分割
- `input_builder`
- `extractor`
- `validator`
- `postprocess`

### 4.3 セキュリティ前提
- 音声ファイルは外部送信しない
- 動画ファイルは外部送信しない
- transcript テキストを含む全データを外部送信しない（Gemma 4 + Ollama 完全ローカル）
- 匿名化・マスキング機能は将来拡張として設計上は維持する

### 4.4 ToDo の扱い
- `owner_candidate`
- `due_date_candidate`

上記は候補値であり、確定値ではない。  
曖昧表現はそのまま保持する。  
人手レビュー前提で扱う。

---

## 5. 命名・配置ルール

### 5.1 ルート名
- 正式なプロジェクト / フォルダ名は `VideoMinutesGenerator`

### 5.2 Python パッケージ
- 実装パスは `src/vmg/...` を使用する

### 5.3 主要パス
- `src/vmg/common/`
- `src/vmg/ingest/`
- `src/vmg/preprocess/`
- `src/vmg/asr/`
- `src/vmg/analysis/`
- `src/vmg/formatter/`
- `src/vmg/export/`
- `src/vmg/pipeline/`

### 5.4 データ出力先
- 中間生成物: `data/work/{job_id}/`
- 最終生成物: `data/output/{job_id}/`
- ログ: `logs/{job_id}.jsonl`

---

## 6. 外部依存の扱い

### 6.1 単体テストでは実呼び出ししないもの
- Ollama（httpx.post）
- FFmpeg
- Whisper

### 6.2 モック方針
- Ollama: `httpx.post` をモック
- FFmpeg: `subprocess.run` をモック
- Whisper: `load_model` / `transcribe` をモック
- ファイル書き込み: `tmp_path` を優先利用

### 6.3 import 方針
- 外部ライブラリ未インストール環境でも、可能な限りモジュール import 自体は壊さない
- 必要ならレイジーインポートを使う

---

## 7. 現在の進め方

### 7.1 実装順序
常に `docs/task-breakdown.md` の順で進めること。

### 7.2 タスク実行ルール
各タスクでは以下を守る。

1. 先に失敗テストを作る
2. 最小差分で実装する
3. テストを通す
4. 完了条件を確認する
5. 必要なら文書差分を確認する
6. 次タスクへ勝手に進まない

### 7.3 完了報告ルール
完了報告には最低限以下を含めること。

- 追加 / 修正したファイル
- テスト件数
- カバレッジ
- 完了条件の達成状況
- 回帰有無

---

## 8. コンテキスト節約運用

### 8.1 基本方針
会話に長文を保持しすぎない。  
重要事項は文書へ残し、会話側は短く保つ。

### 8.2 タスク完了ごとの運用
- タスク完了内容を短く要約する
- 必要なら `CLAUDE.md` に反映する
- 長くなったら `/compact` を使う
- 次タスクへ進む前に、前提を短く整理する

### 8.3 優先して文書に残すべきもの
- 方針
- 責務分割
- 命名ルール
- セキュリティ前提
- 実装順序
- 例外的な設計判断

---

## 9. 実装時の禁止事項

- 複数タスクをまとめて実装すること
- 文書未定義の大きな設計変更
- テストなしでの実装完了宣言
- 単体テストで外部APIやWhisperやFFmpegを実行すること
- セキュリティ前提に反する外部送信
- task-breakdown.md を無視した順序変更

---

## 10. 現時点の実装状況メモ

以下はタスク進捗の短縮メモ。必要に応じて更新する。

### 完了済み（MVP 全タスク）

**task-breakdown.md 定義タスク（TASK-00-01〜TASK-07-04）**
- TASK-00-01 プロジェクト初期セットアップ
- TASK-00-02 共通型定義
- TASK-00-03 設定管理
- TASK-00-04 構造化ロガー
- TASK-00-05 インターフェース定義
- TASK-01-01 動画ファイルバリデーション
- TASK-01-02 ジョブID発行・job_meta 作成
- TASK-02-01 音声抽出（FFmpeg）
- TASK-02-02 音声前処理バリデーション
- TASK-03-01 WhisperLocalProvider 実装
- TASK-03-02 transcript.json 出力
- TASK-04-01 input_builder 実装
- TASK-04-02 extractor 実装（Ollama/httpx）
- TASK-04-03 validator 実装
- TASK-04-04 postprocess 実装
- TASK-05-01 標準議事録テンプレート作成
- TASK-05-02 StandardFormatter 実装
- TASK-06-01 Markdown 出力
- TASK-06-02 JSON 出力
- TASK-06-03 manifest.json 出力
- TASK-07-01 Pipeline Runner 実装
- TASK-07-02 ステージスキップ機構
- TASK-07-03 CLI エントリポイント実装
- TASK-07-04 E2E 統合テスト（CASE-01 run-6 PASS 確認済み）

**追加実装（安定化対応）**
- AnalysisResult 差分解消（agenda / decisions / pending_items / notes 追加、Topic 定義統一）
- timeout 安全化（LLMTimeoutError 即失敗、timeout_seconds: 900 に整合）
- max_retries を config → AppConfig → cli → extract まで接続
- extractor 実行ログ強化（model / timeout_seconds / elapsed_ms / attempt 等の extra 出力）
- Whisper lazy load 化 + `device="cpu"` 固定（ISSUE-03 GPU競合解消）
- `asr.initial_prompt` の config 制御化（AppConfig.whisper_initial_prompt → WhisperLocalProvider → transcribe に連携。null/空文字は無視）

### 残課題（ISSUE）

- **ISSUE-01** (medium): extractor 応答時間の変動（238〜556 秒）。timeout=900 秒で運用回避済みだが根本解決ではない
- **ISSUE-02** (low): 無音動画で Whisper ハルシネーション（eval 用途のみ影響）
- timeout 値の完全一元化（yaml と関数デフォルトの二重管理が残存）
- `asr.device` の config 化（現在 `device="cpu"` をコード内にハードコード）
- Whisper CPU 実行警告の抑制（低優先）

### 次フェーズ候補

| 候補 | 種別 | 優先度 |
|------|------|--------|
| 実音声付きケースでの評価（evaluation-plan.md 参照）— CASE-02 run-3（initial_prompt 有効）完了 | 品質確認 | High |
| ISSUE-01: extractor 高速化（小型モデル検討・warm-up） | 技術的負債 | Medium |
| E2E テストの自動化整備 | 品質向上 | Medium |
| timeout 値の完全一元化 | 技術的負債 | Low |
| `asr.device` の config 化 | 技術的負債 | Low |
| 話者分離・DOCX/PDF 出力等（task-breakdown.md §5） | 将来拡張 | Later |

---

## 11. Claude Code への基本指示

作業時は以下の前提で振る舞うこと。

- このプロジェクトでは docs を正とする
- 1回の依頼では 1タスクだけ扱う
- まずテスト、次に実装
- 完了条件を満たしたかを必ず確認する
- 不要なリファクタや横展開はしない
- 不明点があれば、推測で広げず差分を示す
