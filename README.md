# Video Minutes Generator

会議動画ファイル（mp4 / mov / mkv）から議事録を自動生成する CLI ツール。  
音声認識（Whisper）と LLM（Ollama + gemma4）を**すべてローカルで**実行する。音声・テキストを外部に送信しない。

---

## 目次

1. [クイックスタート](#1-クイックスタート)
2. [できること](#2-できること)
3. [制約事項](#3-制約事項)
4. [セットアップ](#4-セットアップ)
5. [実行方法](#5-実行方法)
6. [出力ファイル](#6-出力ファイル)
7. [設定](#7-設定)
8. [既知誤認識・補正](#8-既知誤認識補正)
9. [ディレクトリ構成](#9-ディレクトリ構成)
10. [トラブルシューティング](#10-トラブルシューティング)

---

## 1. クイックスタート

以下の手順で最短 1 回実行できる。詳細は [4. セットアップ](#4-セットアップ) を参照。

```bash
# 1. 前提: FFmpeg・Ollama インストール済み

# 2. gemma4 モデルを取得（初回のみ）
ollama pull gemma4

# 3. Ollama を起動
ollama serve &

# 4. リポジトリをセットアップ
git clone <このリポジトリのURL>
cd VideoMinutesGenerator
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install openai-whisper

# 5. 実行
python3 -m vmg \
  --input meeting.mp4 \
  --title "週次定例会議" \
  --datetime "2026-04-29T10:00:00" \
  --participants 田中 \
  --participants 佐藤
```

実行完了後、以下のように出力される:

```
完了: job_20260429_100000_abcdef
  Markdown : data/output/job_20260429_100000_abcdef/minutes.md
  JSON     : data/output/job_20260429_100000_abcdef/minutes.json
  Manifest : data/output/job_20260429_100000_abcdef/manifest.json
```

出力ファイルを確認する:

```bash
cat data/output/job_20260429_100000_abcdef/minutes.md
```

---

## 2. できること

| 機能 | 詳細 |
|---|---|
| 音声抽出 | FFmpeg で動画から音声（WAV 16kHz）を抽出する |
| 文字起こし | Whisper（ローカル）で日本語音声を文字起こしする |
| ASR 補助（initial_prompt） | Whisper にドメイン文脈を伝えるヒント文を渡し、特定語彙の認識精度を補助できる |
| 辞書ベース補正 | ASR 後・LLM 前にテキストの同音異義語を辞書で置換する |
| 議事録要素の抽出 | gemma4（Ollama）で要約・議題・決定事項・保留事項・ToDo を抽出する |
| Markdown 出力 | 人間が読みやすい議事録を `minutes.md` として出力する |
| JSON 出力 | 機械処理向けの構造化データを `minutes.json` として出力する |
| 構造化ログ出力 | 各ステージの処理時間・エラー情報を JSONL 形式でログに記録する |

---

## 3. 制約事項

| 制約 | 詳細 |
|---|---|
| ASR 精度 | Whisper small の日本語認識精度は音質に強く依存する。ノイズが多い音声や小声は誤認識が増える |
| 話者分離 | **未対応**。誰がどの発言をしたかは区別しない |
| 同音異義語補正 | `correction_dict.yaml` に登録済みの語のみ補正する。未登録の誤認識はそのまま LLM に渡る |
| LLM 抽出精度 | gemma4 による抽出は 100% 正確ではない。`owner_candidate`・`due_date_candidate` は候補値であり確定値ではない |
| 処理時間 | ASR は CPU で音声長と同等〜数倍の時間がかかる。LLM 分析は数分〜十数分かかることがある |
| 現状の位置づけ | ローカル PoC / MVP。本番品質の議事録作成には人手レビューが必須 |
| 対応動画形式 | mp4 / mov / mkv のみ |

---

## 4. セットアップ

### 前提条件

| 依存 | バージョン | 確認コマンド |
|---|---|---|
| Python | 3.11 以上 | `python3 --version` |
| FFmpeg | 任意の安定版 | `ffmpeg -version` |
| Ollama | 任意の安定版 | `ollama --version` |

### 手順

#### Step 1: FFmpeg をインストール

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

#### Step 2: Ollama をインストールして gemma4 を取得

```bash
# Ollama インストール（公式: https://ollama.com）
curl -fsSL https://ollama.com/install.sh | sh

# gemma4 モデルを取得（初回のみ、数 GB のダウンロードが発生する）
ollama pull gemma4
```

#### Step 3: Ollama を起動

```bash
ollama serve &
```

起動確認:

```bash
curl http://localhost:11434/api/tags
```

#### Step 4: このリポジトリをセットアップ

```bash
git clone <このリポジトリのURL>
cd VideoMinutesGenerator

python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -e .
pip install openai-whisper
```

---

## 5. 実行方法

```bash
source .venv/bin/activate

python3 -m vmg \
  --input meeting.mp4 \
  --title "週次定例会議" \
  --datetime "2026-04-29T10:00:00" \
  --participants 田中 \
  --participants 佐藤
```

### オプション一覧

| オプション | 必須 | 説明 |
|---|---|---|
| `--input PATH` | ✅ | 入力動画ファイルパス（mp4 / mov / mkv） |
| `--title TEXT` | ✅ | 会議タイトル |
| `--datetime TEXT` | ✅ | 会議日時（ISO 8601 形式、例: `2026-04-29T10:00:00`） |
| `--participants TEXT` | 推奨 | 参加者名（複数回指定可） |
| `--job-id TEXT` | | ジョブ ID（省略時は自動生成） |
| `--force` | | 中間ファイルを無視して全ステージを強制再実行 |

### job_id を指定する

`--job-id` を指定すると任意の識別子でジョブを管理できる。

```bash
python3 -m vmg \
  --input meeting.mp4 \
  --title "週次定例会議" \
  --datetime "2026-04-29T10:00:00" \
  --participants 田中 \
  --job-id my-meeting-2026-04-29
```

### 途中から再開する

パイプラインが途中で止まった場合、同じ `--job-id` で再実行すると完了済みのステージ（音声抽出・文字起こし・分析）をスキップして再開できる。`--force` を付けると強制的に全ステージを再実行する。

```bash
# 途中再開（中間ファイルがあるステージはスキップ）
python3 -m vmg \
  --input meeting.mp4 \
  --title "週次定例会議" \
  --datetime "2026-04-29T10:00:00" \
  --participants 田中 \
  --job-id job_20260429_100000_abcdef

# 強制全再実行
python3 -m vmg ... --force
```

---

## 6. 出力ファイル

### ファイル一覧

| ファイルパス | 説明 |
|---|---|
| `data/output/{job_id}/minutes.md` | Markdown 形式の議事録 |
| `data/output/{job_id}/minutes.json` | 構造化 JSON |
| `data/output/{job_id}/manifest.json` | 生成メタ情報 |
| `data/work/{job_id}/transcript.json` | 生 ASR 出力（補正前） |
| `data/work/{job_id}/analysis.json` | LLM 抽出結果の中間ファイル |
| `logs/{job_id}.jsonl` | 構造化ログ（各ステージの処理時間・エラー） |

### minutes.md の構成

```
# 議事録
## 1. 会議情報        ← タイトル・日時・参加者・動画ファイル名
## 2. 会議要約        ← LLM が生成した要約文
## 3. 議題            ← 議題の箇条書き
## 4. 議論内容        ← 議題ごとの要点とキーポイント
## 5. 決定事項        ← 確定した事柄
## 6. 保留事項        ← 未解決の課題
## 7. ToDo            ← タスク・担当者候補・期限候補の表
## 8. 参考ログ        ← 文字起こし全文
```

### minutes.json の構造

```json
{
  "meeting_info": {
    "title": "週次定例会議",
    "datetime": "2026-04-29T10:00:00",
    "participants": ["田中", "佐藤"],
    "source_file": "meeting.mp4",
    "duration_seconds": 1800
  },
  "analysis": {
    "summary": "会議の要約文...",
    "agenda": ["議題1", "議題2"],
    "topics": [
      { "title": "議題名", "summary": "要点", "key_points": ["..."] }
    ],
    "decisions": ["決定事項1"],
    "pending_items": ["保留事項1"],
    "todos": [
      {
        "task": "タスク内容",
        "owner_candidate": "田中",
        "due_date_candidate": "来週金曜日",
        "notes": "補足"
      }
    ]
  },
  "transcript": {
    "language": "ja",
    "full_text": "文字起こし全文（辞書補正後）...",
    "segments": [
      { "start": 0.0, "end": 7.0, "text": "発話テキスト", "speaker": null }
    ]
  }
}
```

> `owner_candidate` / `due_date_candidate` は LLM による候補値。確定値ではないため人手で確認すること。

### transcript.json（中間ファイル）

生の ASR 出力を保存する。辞書補正は適用されていない（補正はメモリ上で行い、`minutes.json` の `transcript` フィールドに反映される）。

### logs/{job_id}.jsonl の形式

各行が 1 つのイベントを表す JSONL 形式。

```json
{
  "timestamp": "2026-04-29T10:00:01+00:00",
  "job_id": "job_20260429_100000_abcdef",
  "stage": "asr",
  "level": "INFO",
  "message": "asr 完了",
  "duration_ms": 36288,
  "extra": {}
}
```

---

## 7. 設定

設定ファイルは `config/default.yaml`。主要項目を以下に示す。

### ASR 設定

| フィールド | デフォルト | 説明 |
|---|---|---|
| `asr.model_size` | `small` | Whisper モデルサイズ（`tiny` / `base` / `small` / `medium` / `large`） |
| `asr.language` | `ja` | 認識言語 |
| `asr.initial_prompt` | （設定済み） | Whisper に渡すドメインヒント文。`null` で無効化 |
| `asr.correction.enabled` | `true` | 辞書ベース補正の有効/無効 |
| `asr.correction.dict_path` | `config/correction_dict.yaml` | 補正辞書ファイルのパス |

### LLM 設定

| フィールド | デフォルト | 説明 |
|---|---|---|
| `analysis.model` | `gemma4` | Ollama で使用するモデル名 |
| `analysis.base_url` | `http://localhost:11434/v1` | Ollama のエンドポイント |
| `analysis.timeout_seconds` | `900` | LLM 応答のタイムアウト（秒） |
| `analysis.max_retries` | `3` | タイムアウト時のリトライ回数 |

### 設定例（config/default.yaml 抜粋）

```yaml
asr:
  model_size: small
  language: ja
  initial_prompt: "これはシステム開発に関する技術的な会議の録音です。..."
  correction:
    enabled: true
    dict_path: config/correction_dict.yaml

analysis:
  model: gemma4
  base_url: http://localhost:11434/v1
  timeout_seconds: 900
  max_retries: 3
```

### 補正辞書（config/correction_dict.yaml）

```yaml
rules:
  - wrong: "使用書"    # ASR が誤認識した表記
    correct: "仕様書"  # 正しい表記
  - wrong: "バック修正"
    correct: "バグ修正"
```

完全文字列一致で置換するため、「使用書」を置換しても「使用する」「使用方法」は変わらない。

---

## 8. 既知誤認識・補正

### 実音声テスト（CASE-02: スマホ録音・Whisper small）での確認結果

| 実際の発話 | ASR 認識結果 | 補正後 | 対応状況 |
|---|---|---|---|
| 仕様書 | 使用書 / 私用書 | 仕様書 | ✅ correction_dict で補正済み |
| バグ修正 | バック修正 | バグ修正 | ✅ correction_dict で補正済み |
| 本番反映 | 本番映し | 本番反映 | ✅ correction_dict で補正済み |
| 外部 API | バイブ API 等 | — | ❌ 未対応（文脈依存のため辞書追加は慎重に） |
| ログイン画面 | 録音画面 | — | ❌ 未対応（initial_prompt の副作用の可能性） |

### initial_prompt で改善が確認できた語

| 語 | run-1（prompt なし） | run-3（prompt あり）|
|---|---|---|
| 本番反映 | 本番範囲 ❌ | 本番反映 ✅ |
| スプリント | 正認識 ✅ | 正認識 ✅ |
| 検索機能 | 正認識 ✅ | 正認識 ✅ |

### 辞書補正の限界

- 登録した誤変換語と完全一致する場合のみ補正する。部分一致・文脈依存の補正は行わない
- 「外部 API → バイブ API」のように ASR が全く異なる音として認識するケースは辞書では対応困難
- 補正辞書への追加はドメイン特化で行う。汎用的な同音異義語の全量登録は意図していない

---

## 9. ディレクトリ構成

```
VideoMinutesGenerator/
├── config/
│   ├── default.yaml          # メイン設定ファイル
│   └── correction_dict.yaml  # 同音異義語補正辞書
├── data/
│   ├── work/{job_id}/        # 中間ファイル（audio.wav / transcript.json / analysis.json）
│   └── output/{job_id}/      # 最終出力（minutes.md / minutes.json / manifest.json）
├── logs/
│   └── {job_id}.jsonl        # 構造化ログ（ステージ別処理時間・エラー）
├── eval/
│   └── results/              # 評価ケース別の実行結果記録
├── src/vmg/                  # ソースコード
│   ├── asr/                  # 音声認識・辞書補正
│   ├── analysis/             # LLM による情報抽出
│   ├── pipeline/             # ステージ統合・スキップ制御
│   ├── common/               # 設定・ログ・型定義
│   └── cli.py                # CLI エントリポイント
└── tests/                    # 単体テスト・統合テスト
```

---

## 10. トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| `Connection refused` / `Ollama に接続できない` | Ollama が起動していない | `ollama serve &` で起動する。`curl http://localhost:11434/api/tags` で確認 |
| `ffmpeg: command not found` | FFmpeg が未インストール | `brew install ffmpeg`（macOS）/ `apt install ffmpeg`（Ubuntu）でインストール |
| ASR がとても遅い | CPU 実行はモデルサイズに比例して時間がかかる | `model_size: small`（デフォルト）が最速。GPU 環境なら自動的に高速化される |
| `LLMTimeoutError` | LLM が `timeout_seconds` 以内に応答しなかった | `config/default.yaml` の `analysis.timeout_seconds` を増やす（デフォルト: 900 秒） |
| 日本語が誤認識される | Whisper small の認識限界 / ノイズ | `correction_dict.yaml` に誤認識パターンを追加する。または `model_size: medium` に変更する |
| 出力ファイルが見つからない | job_id を確認していない | コマンド実行後の標準出力に表示される `Markdown:` 行のパスを確認する |
| `No module named 'vmg'` | venv が有効化されていない | `source .venv/bin/activate` を実行してから再試行する |
| `No module named 'whisper'` | Whisper が未インストール | `pip install openai-whisper` を実行する |
