# architecture.md

# 動画議事録生成システム アーキテクチャ設計書 v0.2

## 1. 文書目的

本書は `requirements.md` を基準として、動画議事録生成システムの設計方針・モジュール構成・データフロー・インターフェース設計を定義する。  
実装・テスト設計・タスク分解の起点となる設計ドキュメントとして位置づける。

**v0.2 変更点**
- analysis モジュールを input_builder / extractor / validator / postprocess に責務分割
- Claude API 外部送信ポリシーを明記（§5.4）→ v0.3 でローカルLLM方針に改定
- Todo の owner / due_date を candidate 扱いとして明記
- output manifest の保存を追加

**v0.3 変更点**
- LLM解析を Claude API から Gemma 4 + Ollama（ローカル）に移行
- transcript を含む全データを外部送信しない完全ローカル構成に変更（§5.4 改定）

**v0.4 変更点**
- 辞書ベース ASR 後処理補正（TranscriptCorrector）を asr モジュールに追加（§8 拡張ポイント更新）
- `asr.initial_prompt` を config から制御可能にした
- Streamlit デモ UI（`app.py`）を追加。デモ目的のみ。本番 UI ではない（§9.4 参照）

---

## 2. 全体アーキテクチャ

### 2.1 設計原則

| 原則 | 内容 |
|---|---|
| 疎結合 | 各ステージは独立したモジュールとし、依存を最小化する |
| 差し替え可能性 | ASR・フォーマッタなど可変性の高い箇所はインターフェースで抽象化する |
| ローカル完結 | デフォルト構成で外部APIへの音声・映像送信を行わない |
| 再実行性 | 各ステージの出力を永続化し、失敗時に途中から再実行できる |
| 監査性 | 元データ・中間データ・出力データの対応関係を保持する |
| 可観測性 | 各ステージのログ・処理時間・エラーを構造化して記録する |

### 2.2 アーキテクチャパターン

| パターン | 適用箇所 | 目的 |
|---|---|---|
| Pipeline パターン | 全体処理フロー | ステージの直列実行・スキップ・再実行を制御する |
| Strategy パターン | ASR・Formatter | 実装を差し替え可能にする |
| Plugin パターン | Diarization | MVPでは省略可能、将来差し込めるスロットとして設計する |
| Repository パターン | data/ 配下 | 中間・最終データの読み書きを抽象化する |

### 2.3 全体構成図

```
[ ユーザー入力 ]
     │
     ▼
┌─────────────────────────────────────────────────────┐
│                   Pipeline Runner                    │
│  ジョブID管理 / ステージ実行制御 / 再実行制御         │
└─────────────────────────────────────────────────────┘
     │
     ▼
┌──────────┐   ┌───────────┐   ┌──────────┐   ┌─────────────┐
│  ingest  │──▶│ preprocess│──▶│   asr    │──▶│ diarization │ ← MVP外・将来拡張
└──────────┘   └───────────┘   └──────────┘   └─────────────┘
                                    │                │
                                    └───────┬────────┘
                                            ▼
                                    ┌────────────────────────┐
                                    │        analysis        │
                                    │  1. input_builder      │
                                    │  2. extractor          │
                                    │  3. validator          │
                                    │  4. postprocess        │
                                    └────────────────────────┘
                                            │
                                            ▼
                                    ┌──────────────┐
                                    │  formatter   │
                                    │ テンプレート整形│
                                    └──────────────┘
                                            │
                                            ▼
                                    ┌──────────────┐
                                    │    export    │
                                    │ Markdown/JSON│
                                    │  + manifest  │
                                    └──────────────┘
```

---

## 3. 処理フロー

### 3.1 MVP処理フロー（diarization なし）

```
1. ingest
   入力: 動画ファイルパス (mp4 / mov / mkv)
   処理: ファイル存在確認、形式検証、メタ情報取得
   出力: バリデーション済みファイルパス + ジョブID発行

2. preprocess
   入力: 動画ファイル
   処理: FFmpeg で音声トラックを WAV に抽出
   出力: data/work/{job_id}/audio.wav

3. asr
   入力: audio.wav
   処理: ローカル Whisper でタイムスタンプ付き文字起こし
         話者識別なし（初期は speaker: null または "Speaker_A/B" 擬似識別）
   出力: data/work/{job_id}/transcript.json

4. analysis（4段階のサブ処理）
   4-1. input_builder
        入力: transcript.json
        処理: transcript テキストを LLM プロンプト用に整形・チャンク化
        出力: 送信用プロンプト（メモリ内）

   4-2. extractor
        入力: プロンプト
        処理: Ollama（ローカルLLM）を呼び出し、構造化出力（JSON）を取得する
              ※ 全データをローカルで処理する（外部送信なし）
        出力: LLM生成 JSON（未検証）

   4-3. validator
        入力: LLM生成 JSON
        処理: JSONスキーマバリデーション（必須フィールド・型チェック）
              バリデーション失敗時は再プロンプトを要求する
        出力: 検証済み JSON

   4-4. postprocess
        入力: 検証済み JSON
        処理: 期限候補・担当候補の正規化、重複除去、candidate フラグ付与
        出力: data/work/{job_id}/analysis.json

5. formatter
   入力: analysis.json + transcript.json + 会議メタ情報
   処理: 議事録テンプレートへの流し込み（Jinja2）
   出力: 整形済みテキスト（メモリ内）

6. export
   入力: 整形済みテキスト + analysis.json
   処理: Markdown / JSON ファイルとして書き出し、output manifest を生成
   出力: data/output/{job_id}/minutes.md
          data/output/{job_id}/minutes.json
          data/output/{job_id}/manifest.json
```

### 3.2 将来の処理フロー（diarization 追加後）

```
ingest → preprocess → asr → [diarization] → analysis → formatter → export
                                  ↑
                              diarization ステージが transcript.json の
                              speaker フィールドを更新する
```

diarization は asr と analysis の間のオプションステージとして設計する。  
パイプライン設定ファイル（config）で有効/無効を切り替えられる構成とする。

---

## 4. モジュール分割

### 4.1 モジュール一覧

| モジュール | パス | 責務 |
|---|---|---|
| ingest | src/ingest/ | 動画ファイルの受け付けと検証 |
| preprocess | src/preprocess/ | 音声抽出・前処理 |
| asr | src/asr/ | 音声認識・文字起こし（抽象化） |
| diarization | src/diarization/ | 話者分離（MVP外スロット） |
| analysis/input_builder | src/analysis/input_builder/ | transcript → LLMプロンプト変換 |
| analysis/extractor | src/analysis/extractor/ | Ollama HTTP API 呼び出し・構造化出力取得 |
| analysis/validator | src/analysis/validator/ | LLM出力のスキーマバリデーション |
| analysis/postprocess | src/analysis/postprocess/ | 後処理・candidate 正規化 |
| formatter | src/formatter/ | 議事録テンプレート整形（抽象化） |
| export | src/export/ | ファイル出力・manifest 生成 |
| common | src/common/ | 設定・ログ・ユーティリティ・データ定義 |
| pipeline | src/pipeline/ | ステージ実行制御・ジョブ管理 |

### 4.2 各モジュール詳細

#### ingest

| 項目 | 内容 |
|---|---|
| 入力 | 動画ファイルパス（文字列） |
| 出力 | IngestResult（ジョブID、検証済みパス、ファイルサイズ、フォーマット） |
| 処理 | 対応形式チェック（mp4/mov/mkv）、ファイル存在確認、ジョブID発行 |
| 外部依存 | なし |

#### preprocess

| 項目 | 内容 |
|---|---|
| 入力 | IngestResult |
| 出力 | PreprocessResult（音声ファイルパス、音声長、サンプルレート） |
| 処理 | FFmpeg で音声抽出（16kHz WAV）、無音検出 |
| 外部依存 | FFmpeg（ローカル実行） |

#### asr

| 項目 | 内容 |
|---|---|
| 入力 | PreprocessResult |
| 出力 | Transcript（TranscriptSegment のリスト） |
| 処理 | ASRProvider インターフェース経由でWhisperを呼び出す |
| 外部依存 | openai-whisper（ローカル）または互換実装 |
| 抽象化 | ASRProvider インターフェースで差し替え可能（後述） |

#### diarization（将来拡張スロット）

| 項目 | 内容 |
|---|---|
| 入力 | Transcript + 音声ファイルパス |
| 出力 | Transcript（speaker フィールド更新済み） |
| 処理 | 話者分離モデルで TranscriptSegment の speaker を更新する |
| 外部依存 | pyannote.audio（将来追加） |
| MVP | 無効化状態で存在。有効化は設定で切り替え可能 |

#### analysis/input_builder

| 項目 | 内容 |
|---|---|
| 入力 | Transcript |
| 出力 | PromptInput（送信用プロンプト文字列、使用セグメント範囲） |
| 処理 | transcript セグメントをテキスト連結し、トークン数上限に応じてチャンク分割する |
| 外部依存 | なし |

#### analysis/extractor

| 項目 | 内容 |
|---|---|
| 入力 | PromptInput |
| 出力 | RawAnalysisJSON（LLM生成の未検証 JSON） |
| 処理 | Ollama ローカルLLM（Gemma 4）を呼び出し、要約・議題・決定事項・保留事項・ToDo候補を取得する |
| 外部依存 | Ollama HTTP API（ローカル `http://localhost:11434/v1`）。外部送信なし |
| 送信ポリシー | §5.4 参照 |

#### analysis/validator

| 項目 | 内容 |
|---|---|
| 入力 | RawAnalysisJSON |
| 出力 | ValidatedAnalysisJSON |
| 処理 | 必須フィールドの存在確認、型チェック、スキーマ不正時は再プロンプトを要求する |
| 外部依存 | なし（Pydantic バリデーション） |

#### analysis/postprocess

| 項目 | 内容 |
|---|---|
| 入力 | ValidatedAnalysisJSON |
| 出力 | AnalysisResult（data/work/{job_id}/analysis.json） |
| 処理 | 期限候補・担当候補の正規化（「来週」などの曖昧表現をそのまま保持しつつ candidate フラグを付与）、重複除去 |
| 外部依存 | なし |

#### formatter

| 項目 | 内容 |
|---|---|
| 入力 | AnalysisResult + Transcript + MeetingInfo |
| 出力 | フォーマット済みテキスト（Markdown文字列） |
| 処理 | FormatterProvider インターフェースにJinja2テンプレートで議事録を生成する |
| 外部依存 | Jinja2 |
| 抽象化 | FormatterProvider インターフェースで差し替え可能 |
| Jinja2フィルタ | `seconds_to_hms`: セグメントタイムスタンプ → "HH:MM:SS" / `duration_hms`: 会議時間 → "X時間Y分Z秒"（上位単位が0の場合は省略。例: 90秒→"1分30秒", 45秒→"45秒"） |

#### export

| 項目 | 内容 |
|---|---|
| 入力 | フォーマット済みテキスト + AnalysisResult |
| 出力 | minutes.md、minutes.json、manifest.json |
| 処理 | ファイル書き出し、出力先ディレクトリ作成、output manifest の生成 |
| 外部依存 | なし |

---

## 5. データフロー

### 5.1 中央データ構造

各ステージ間のデータは以下の型で定義する。

```
MeetingInfo
  title: str
  datetime: str                    # ISO 8601形式（例: 2026-04-22T10:00:00+09:00）
  participants: list[str]
  source_file: str
  duration_seconds: int            # preprocess で取得した会議時間（秒）

TranscriptSegment
  start_time: str                  # "HH:MM:SS" 形式
  end_time: str                    # "HH:MM:SS" 形式
  speaker: str | None              # MVP初期は null 許容、擬似識別は "Speaker_A" 等
  text: str

Transcript
  segments: list[TranscriptSegment]
  language: str

AnalysisResult
  summary: str
  agenda: list[str]
  topics: list[Topic]
  decisions: list[str]
  pending_items: list[str]
  todos: list[Todo]

Topic
  title: str
  summary: str
  key_points: list[str]

Todo
  task: str
  owner_candidate: str | None      # LLM抽出の候補値。確定値ではない。人手レビュー前提
  due_date_candidate: str | None   # LLM抽出の候補値。確定値ではない。曖昧表現をそのまま保持
  notes: str | None

OutputManifest
  job_id: str
  generated_at: str                # ISO 8601形式（例: 2026-04-22T10:30:00+09:00）
  files: list[str]                 # 出力ファイル名のリスト（例: ["minutes.md", "minutes.json"]）
  source_transcript: str           # 元になった transcript.json のパス

MinutesOutput
  meeting_info: MeetingInfo
  summary: str
  agenda: list[str]
  topics: list[Topic]
  decisions: list[str]
  pending_items: list[str]
  todos: list[Todo]
  transcript: list[TranscriptSegment]
```

> **Todo の candidate フィールドについて**  
> `owner_candidate` および `due_date_candidate` はLLMが transcript から推定した候補値であり、確定値ではない。  
> 「来週」「月末」などの曖昧表現はそのまま保持する。最終的な確定は人手レビューを前提とする。

### 5.2 ステージ間データの永続化

再実行性を担保するため、各ステージの出力は `data/work/{job_id}/` に保存する。

```
data/
  input/
    {filename}                    ← 元動画（コピーまたはシンボリックリンク）
  work/
    {job_id}/
      job_meta.json               ← ジョブID、実行日時、入力ファイルパス
      audio.wav                   ← preprocess 出力
      transcript.json             ← asr 出力
      diarization.json            ← diarization 出力（将来拡張）
      analysis.json               ← analysis/postprocess 出力
  output/
    {job_id}/
      minutes.md                  ← 最終出力（Markdown）
      minutes.json                ← 最終出力（JSON）
      manifest.json               ← output manifest（出力ファイル一覧・生成日時・job_id）
```

**manifest.json の構造例**

```json
{
  "job_id": "job_20260422_001",
  "generated_at": "2026-04-22T10:30:00+09:00",
  "files": ["minutes.md", "minutes.json"],
  "source_transcript": "data/work/job_20260422_001/transcript.json"
}
```

### 5.3 再実行制御

パイプラインは各ステージ実行前に `data/work/{job_id}/` の出力ファイルを確認する。  
出力ファイルが存在する場合は当該ステージをスキップし、既存ファイルを読み込んで次ステージへ進む。  
強制再実行する場合は `--force` オプションで特定ステージ以降を再実行できる。

### 5.4 ローカル処理ポリシー（v0.3 改定）

本システムは全データをローカルで処理し、外部送信を行わない完全ローカル構成とする。

#### データ処理方針

| データ種別 | 処理方針 | 備考 |
|---|---|---|
| 音声ファイル（WAV等） | **ローカルのみ** | Whisper ローカル実行 |
| 動画ファイル | **ローカルのみ** | FFmpeg ローカル実行 |
| transcript テキスト | **ローカルのみ** | Ollama（Gemma 4）ローカル実行 |

#### LLM処理方針

- analysis/extractor は Ollama HTTP API（`http://localhost:11434/v1`）を通じてローカルの Gemma 4 を呼び出す
- ネットワーク接続不要。会議内容が外部サービスに送信されることはない
- Ollama が未起動の場合は `LLMError` でエラーメッセージに `base_url` / `model` / 起動確認方法を含める

#### 将来の拡張ポイント

以下のモードを将来追加できる設計を維持する。

| モード | 内容 |
|---|---|
| 匿名化モード | transcript 内の固有名詞をマスクして処理する |
| モデル切り替え | Ollama 対応モデル（Mistral、Llama 等）を設定で切り替える |

設定ファイル（`config/default.yaml`）の `api_policy` セクションで制御できる設計とする。

---

## 6. インターフェース設計方針

### 6.1 基本方針

- 可変性が高いコンポーネントはインターフェース（抽象基底クラス）で定義し、実装を差し替え可能にする
- インターフェースは `src/common/interfaces.py` に集約して定義する
- 各ステージの実装はインターフェースを満たす具象クラスとして `src/{module}/` に配置する

### 6.2 ASR 抽象化（ASRProvider）

```
interface ASRProvider:
  def transcribe(audio_path: str, language: str) -> Transcript
```

| 実装 | 用途 |
|---|---|
| WhisperLocalProvider | ローカルWhisper（デフォルト） |
| WhisperAPIProvider | OpenAI Whisper API（将来オプション） |
| FasterWhisperProvider | faster-whisper（高速化版、将来オプション） |

設定ファイルで使用するプロバイダを切り替える。

### 6.3 Formatter 抽象化（FormatterProvider）

```
interface FormatterProvider:
  def format(
    meeting_info: MeetingInfo,
    analysis: AnalysisResult,
    transcript: Transcript
  ) -> str
```

| 実装 | 用途 |
|---|---|
| StandardFormatter | 標準議事録形式（MVP採用） |
| ExecutiveSummaryFormatter | 管理職向け要約型（将来拡張） |
| DetailedLogFormatter | 実務詳細型（将来拡張） |
| TaskFocusedFormatter | タスク管理特化型（将来拡張） |

### 6.4 Diarization プラグポイント

パイプライン設定に `diarization.enabled: bool` を設け、無効時はスロットを通過する。

```
interface DiarizationProvider:
  def diarize(transcript: Transcript, audio_path: str) -> Transcript
```

MVP 期間中は `PassThroughDiarizationProvider`（何もしないノーオペレーション実装）を使用する。

---

## 7. エラーハンドリング方針

### 7.1 例外の分類

| 分類 | 内容 | 対応 |
|---|---|---|
| ValidationError | 入力ファイルの形式・存在チェック失敗 | 即時終了。ユーザーにメッセージを返す |
| ProcessingError | FFmpeg/Whisper などの処理失敗 | ステージ単位でリトライ可能にする |
| LLMError | Ollama 応答失敗・スキーマ不正 | 再試行（最大N回）後に失敗扱い |
| OutputError | ファイル書き込み失敗 | 即時終了。出力先確認を促す |
| ConfigError | 設定ファイル不正・必須設定欠落 | 起動時に検出して即時終了 |

### 7.2 再試行戦略

- `ProcessingError`・`LLMError` は設定可能なリトライ回数（デフォルト: 3回）とバックオフを持つ
- LLM のスキーマ不正は再プロンプトで修正試行する（最大2回）
- リトライ超過後はステージ失敗としてログに記録し、終了する

### 7.3 ログ設計

- 出力形式: JSON Lines（1行1イベント）
- 出力先: `logs/{job_id}.jsonl`
- 各エントリに含む項目:

```json
{
  "timestamp": "2026-04-22T10:00:05+09:00",
  "job_id": "job_20260422_001",
  "stage": "analysis.extractor",
  "level": "INFO",
  "message": "LLM extraction completed",
  "duration_ms": 12345,
  "extra": {}
}
```

- ステージ開始・終了・スキップ・エラーを必ず記録する
- analysis サブステージ（input_builder / extractor / validator / postprocess）はそれぞれ `stage` フィールドを `"analysis.input_builder"` のように記録する

---

## 8. 拡張ポイント

| 拡張ポイント | 現在の実装 | 将来の拡張方法 |
|---|---|---|
| ASRプロバイダ | WhisperLocalProvider | ASRProvider を実装した新クラスを追加し、設定で切り替える |
| 話者分離 | PassThrough（無効） | DiarizationProvider を実装し、設定で有効化する |
| 議事録フォーマット | StandardFormatter | FormatterProvider を実装した新クラスを追加する |
| 出力形式 | Markdown / JSON | export モジュールに新しい Exporter を追加する |
| 解析項目 | 要約・議題・決定・保留・ToDo | analysis/extractor のプロンプトと validator スキーマを拡張する |
| 固有名詞補正（辞書ベース） | asr/corrector.py（実装済み） | `config/correction_dict.yaml` にルールを追加する |
| 外部送信ポリシー | transcript テキスト送信（デフォルト許可） | analysis/input_builder に匿名化・マスキング処理を追加する。またはローカルLLMプロバイダに差し替える |
| UI | app.py（Streamlit デモ、同期実行） | 本番 UI・非同期化・進捗バー・キャンセルは将来課題（§9.4 参照） |

---

## 9. MVP範囲と将来拡張の切り分け

### 9.1 MVP（初期リリース）

- 動画取込（mp4 / mov / mkv）
- 音声抽出（FFmpeg）
- 文字起こし（ローカルWhisper）
- `asr.initial_prompt` による ASR 認識補助（config 制御）
- 辞書ベース ASR 後処理補正（TranscriptCorrector）
- 話者なし・擬似識別（Speaker_A/B）
- 会議要約生成（Ollama + Gemma 4）
- 議題抽出
- 決定事項抽出
- 保留事項抽出
- ToDo抽出（タスク・担当候補・期限候補 ※ candidate 扱い）
- Markdown出力
- JSON出力
- output manifest 出力
- 再実行機構（ステージスキップ）
- 構造化ログ
- CLI エントリポイント（`python3 -m vmg` / `video-minutes`）

### 9.2 Should（MVP後・優先度高）

- 話者分離（diarization）の有効化
- 固有名詞辞書補正
- 同一文字起こしからの再フォーマット（formatter のみ再実行）

### 9.3 Later（将来拡張）

- DOCX / PDF 出力
- 管理職向け要約型・タスク管理特化型フォーマット
- 外部ストレージ連携
- 検索UI
- リアルタイム処理
- transcript 匿名化・マスキングモード

### 9.4 デモ UI（MVP 外・暫定）

`app.py` として Streamlit ベースのデモ UI を実装済み。以下の方針とする。

| 項目 | 方針 |
|---|---|
| 位置づけ | **デモ用途のみ**。本番 UI ではない |
| 実行方式 | `run_pipeline()` を**同期実行**で呼ぶ。処理中はブラウザが固まって見える |
| 進捗バー | **なし**（`st.spinner` のみ）。MVP 外 |
| キャンセル機能 | **なし**。MVP 外 |
| 非同期化 | **未実装**。将来課題 |
| 起動コマンド | `streamlit run app.py` |

将来の本番 UI 化にあたっては、非同期実行・進捗表示・キャンセル対応の設計が必要になる。

---

## 10. 技術スタック

### 10.1 選定方針

| 方針 | 内容 |
|---|---|
| ローカル完結 | 音声・映像・transcript を含む全データをローカルで処理する（外部送信なし） |
| ライブラリ優先 | 汎用処理はOSSライブラリを活用し、実装量を最小化する |

### 10.2 採用技術一覧

| 領域 | 採用技術 | バージョン目安 | 理由 |
|---|---|---|---|
| 言語 | Python | 3.11+ | ML/音声処理ライブラリの充実度 |
| 音声抽出 | FFmpeg | 最新安定版 | 動画フォーマット対応の汎用性 |
| ASR（デフォルト） | openai-whisper | 最新版 | ローカル完結・日本語精度 |
| LLM解析 | Ollama + Gemma 4（ローカル） | - | 完全ローカル・外部送信なし |
| Ollama HTTP クライアント | httpx | 0.27+ | 軽量・依存最小 |
| テンプレート | Jinja2 | 3.x | フォーマッタ拡張性 |
| CLI | Click | 8.x | シンプルなパイプライン制御 |
| 設定管理 | Pydantic + YAML | 2.x | 型安全な設定読み込み |
| テスト | pytest | 7.x | 標準的・プラグイン充実 |
| デモ UI | Streamlit | 1.30+ | デモ目的のみ（`pip install ".[ui]"` で追加） |

---

## 11. ディレクトリ構成

```text
VideoMinutesGenerator/
├─ docs/
│  ├─ requirements.md
│  └─ architecture.md               ← 本書
├─ src/
│  ├─ ingest/                       # 動画取込・検証
│  ├─ preprocess/                   # 音声抽出
│  ├─ asr/                          # 音声認識（ASRProvider インターフェース含む）
│  ├─ diarization/                  # 話者分離（MVP外スロット）
│  ├─ analysis/
│  │  ├─ input_builder/             # transcript → LLMプロンプト変換
│  │  ├─ extractor/                 # Claude API 呼び出し
│  │  ├─ validator/                 # LLM出力スキーマバリデーション
│  │  └─ postprocess/               # 後処理・candidate 正規化
│  ├─ formatter/                    # テンプレート整形（FormatterProvider インターフェース含む）
│  ├─ export/                       # ファイル出力・manifest 生成
│  ├─ pipeline/                     # ステージ実行制御・ジョブ管理
│  └─ common/                       # 設定・ログ・型定義・インターフェース
├─ tests/
│  ├─ unit/                         # モジュール単体テスト
│  ├─ integration/                  # ステージ間結合テスト
│  └─ fixtures/                     # テスト用サンプルデータ
├─ data/
│  ├─ input/                        # 入力動画
│  ├─ work/                         # 中間データ（ステージ出力）
│  └─ output/                       # 最終出力（minutes.md / minutes.json / manifest.json）
├─ logs/                            # ジョブログ（JSONLines）
├─ scripts/                         # 補助スクリプト
├─ config/
│  ├─ default.yaml                  # デフォルト設定（api_policy 含む）
│  └─ correction_dict.yaml          # 辞書ベース ASR 後処理補正ルール
├─ app.py                           # Streamlit デモ UI（デモ目的のみ。本番 UI ではない）
├─ .env.example
├─ .gitignore
└─ README.md
```

---

## 12. 設計上の決定事項と根拠

| 決定事項 | 採用内容 | 根拠 |
|---|---|---|
| ASRのデフォルト | ローカルWhisper | セキュリティ要件（音声の外部送信禁止）を満たすため |
| ASRの抽象化 | ASRProvider インターフェース | 将来 Whisper API・faster-whisper への差し替えを可能にするため |
| Diarizationの位置 | MVP外・オプショナルスロット | MVPは文字起こしと解析の精度確認を優先し、diarizationは段階的に追加する |
| LLM解析の完全ローカル化 | Ollama（Gemma 4）ローカル実行 | 音声・映像・transcript を含む全データをローカルで処理し、外部送信ゼロを実現する |
| 中間データの永続化 | ステージごとにJSONファイルで保存 | 60分動画の処理は長時間かかるため、再実行時のコスト削減が必須 |
| フォーマッタの抽象化 | FormatterProvider インターフェース | 管理職向け・実務詳細型など複数フォーマットの拡張を前提とするため |
| analysis の責務分割 | input_builder / extractor / validator / postprocess | 各サブ処理を独立してテスト可能にし、LLM呼び出し箇所（extractor）を局所化するため |
| Todo フィールドの candidate 化 | owner_candidate / due_date_candidate | LLM抽出値は推定であり確定値でないことを型定義で明示し、人手レビューを前提とするため |
| output manifest の生成 | manifest.json を output に常時出力 | 出力ファイルと生成コンテキスト（job_id・日時）の対応を自動で記録し、監査性を担保するため |
| 外部送信ポリシーの設計 | api_policy 設定で匿名化/禁止モードを将来追加 | 機密会議での利用に備え、外部送信制御の拡張ポイントを設計段階で確保するため |
| デモ UI の実行方式 | `run_pipeline()` を同期実行（app.py） | デモ用途のため実装の単純さを優先。非同期化・進捗バー・キャンセルは MVP 外とした |
| デモ UI の位置づけ | `app.py` はデモ目的のみ。本番 UI ではない | 本番利用には非同期化・エラー復帰・認証等の追加設計が必要なため明示的に分離する |

---

## 13. 本書の位置付け

本書は `requirements.md` に続く第2の設計成果物である。  
以後は以下の順で成果物を拡張する。

1. requirements.md
2. architecture.md（本書）
3. task-breakdown.md
4. test-plan.md
5. implementation plan

---
