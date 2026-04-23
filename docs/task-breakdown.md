# task-breakdown.md

# 動画議事録生成システム タスク分解書 v0.1（MVP）

## 1. 概要

本書は `requirements.md` および `architecture.md` に基づき、MVP実装を実装順にタスク分解したものである。  
1タスクは可能な限り小さく分割し、それぞれ独立してテスト・検証できる単位とする。

**実装順序**

```
Phase 0: 共通基盤
Phase 1: ingest
Phase 2: preprocess
Phase 3: asr
Phase 4: analysis（input_builder → extractor → validator → postprocess）
Phase 5: formatter
Phase 6: export
Phase 7: pipeline
```

**タスク数**: 24タスク

---

## 2. タスク一覧

| ID | タスク名 | フェーズ | 依存 |
|---|---|---|---|
| TASK-00-01 | プロジェクト初期セットアップ | 共通基盤 | なし |
| TASK-00-02 | 共通型定義 | 共通基盤 | TASK-00-01 |
| TASK-00-03 | 設定管理 | 共通基盤 | TASK-00-01 |
| TASK-00-04 | 構造化ロガー | 共通基盤 | TASK-00-01 |
| TASK-00-05 | インターフェース定義 | 共通基盤 | TASK-00-02 |
| TASK-01-01 | 動画ファイルバリデーション | ingest | TASK-00-02, TASK-00-04 |
| TASK-01-02 | ジョブID発行・job_meta 作成 | ingest | TASK-01-01 |
| TASK-02-01 | 音声抽出（FFmpeg） | preprocess | TASK-01-02, TASK-00-04 |
| TASK-02-02 | 音声前処理バリデーション | preprocess | TASK-02-01 |
| TASK-03-01 | WhisperLocalProvider 実装 | asr | TASK-00-05, TASK-02-02 |
| TASK-03-02 | transcript.json 出力 | asr | TASK-03-01 |
| TASK-04-01 | input_builder 実装 | analysis | TASK-03-02, TASK-00-02 |
| TASK-04-02 | extractor 実装（Claude API） | analysis | TASK-04-01, TASK-00-03 |
| TASK-04-03 | validator 実装 | analysis | TASK-04-02 |
| TASK-04-04 | postprocess 実装 | analysis | TASK-04-03 |
| TASK-05-01 | 標準議事録テンプレート作成 | formatter | TASK-00-02 |
| TASK-05-02 | StandardFormatter 実装 | formatter | TASK-05-01, TASK-00-05 |
| TASK-06-01 | Markdown 出力 | export | TASK-05-02 |
| TASK-06-02 | JSON 出力 | export | TASK-04-04, TASK-05-02 |
| TASK-06-03 | manifest.json 出力 | export | TASK-06-01, TASK-06-02 |
| TASK-07-01 | Pipeline Runner 実装 | pipeline | Phase 1〜6 全タスク完了（TASK-01-01〜TASK-06-03） |
| TASK-07-02 | ステージスキップ機構 | pipeline | TASK-07-01 |
| TASK-07-03 | CLI エントリポイント実装 | pipeline | TASK-07-01, TASK-07-02 |
| TASK-07-04 | エンドツーエンド統合テスト | pipeline | TASK-07-03 |

---

## 3. タスク詳細

---

### Phase 0: 共通基盤

---

#### TASK-00-01: プロジェクト初期セットアップ

| 項目 | 内容 |
|---|---|
| **目的** | Python プロジェクトの骨格を整備し、依存関係と開発環境を定義する |
| **入力** | architecture.md §11 のディレクトリ構成 |
| **出力** | `pyproject.toml` / `.gitignore` / `config/default.yaml`（空テンプレート） / ディレクトリ構造 |
| **依存タスク** | なし |
| **完了条件** | `pip install -e .` が通る / `pytest` が実行できる（テスト0件でも可） |
| **テスト観点** | インストール確認 / ディレクトリ構造の確認 |

---

#### TASK-00-02: 共通型定義

| 項目 | 内容 |
|---|---|
| **目的** | ステージ間で受け渡すデータ構造をPydanticで定義し、型安全性を担保する |
| **入力** | architecture.md §5.1 の型定義（MeetingInfo / TranscriptSegment / Transcript / AnalysisResult / Topic / Todo / OutputManifest / MinutesOutput） |
| **出力** | `src/common/models.py` |
| **依存タスク** | TASK-00-01 |
| **完了条件** | 全型がインポート可能 / Pydantic で構築・バリデーション・シリアライズ / デシリアライズできる |
| **テスト観点** | 正常値での構築 / 必須フィールド欠落時の ValidationError / JSON シリアライズ → 再構築の往復確認 / `owner_candidate` / `due_date_candidate` が `str \| None` であること |

---

#### TASK-00-03: 設定管理

| 項目 | 内容 |
|---|---|
| **目的** | アプリケーション全体の設定（APIキー・モデル設定・api_policy 等）を型安全に読み込む |
| **入力** | architecture.md §10.2 の技術スタック / §5.4 の api_policy |
| **出力** | `src/common/config.py` / `config/default.yaml` |
| **依存タスク** | TASK-00-01 |
| **完了条件** | `config/default.yaml` を読み込み設定値にアクセスできる / 必須項目欠落時に起動時 ConfigError を発生させる |
| **テスト観点** | 正常読み込み / 必須キー欠落時の ConfigError / 環境変数による APIキー上書き確認 |

---

#### TASK-00-04: 構造化ロガー

| 項目 | 内容 |
|---|---|
| **目的** | 各ステージから呼び出せる JSON Lines 形式のロガーを実装し、可観測性を確保する |
| **入力** | architecture.md §7.3 のログ設計（timestamp / job_id / stage / level / message / duration_ms / extra） |
| **出力** | `src/common/logger.py` |
| **依存タスク** | TASK-00-01 |
| **完了条件** | ステージ名・job_id・duration_ms を含む JSON Lines が `logs/{job_id}.jsonl` に出力される |
| **テスト観点** | ログエントリの構造確認（全フィールドの存在） / ファイル出力確認 / 複数ステージのログが1ファイルに追記されること |

---

#### TASK-00-05: インターフェース定義

| 項目 | 内容 |
|---|---|
| **目的** | ASRProvider / FormatterProvider / DiarizationProvider の抽象基底クラスを定義し、差し替え可能な設計を確立する |
| **入力** | architecture.md §6 のインターフェース設計 |
| **出力** | `src/common/interfaces.py` |
| **依存タスク** | TASK-00-02 |
| **完了条件** | 各インターフェースが定義され、継承して具象クラスを実装できる / 未実装メソッドがあると TypeError になる |
| **テスト観点** | インターフェースを継承した最小実装クラスが作れること / 抽象メソッド未実装時の TypeError 確認 |

---

### Phase 1: ingest

---

#### TASK-01-01: 動画ファイルバリデーション

| 項目 | 内容 |
|---|---|
| **目的** | 対応形式（mp4 / mov / mkv）の動画ファイルを受け付け、不正ファイルを ValidationError で拒否する |
| **入力** | 動画ファイルパス（文字列） |
| **出力** | バリデーション済み `IngestResult`（パス / 形式 / サイズ）または ValidationError |
| **依存タスク** | TASK-00-02, TASK-00-04 |
| **完了条件** | mp4 / mov / mkv は受け付ける / 存在しないファイルは ValidationError / 非対応形式は ValidationError |
| **テスト観点** | 正常系（mp4 / mov / mkv 各形式） / 存在しないパス / 非対応拡張子（例: avi） / 拡張子なしファイル |

---

#### TASK-01-02: ジョブID発行・job_meta 作成

| 項目 | 内容 |
|---|---|
| **目的** | 各処理ジョブに一意の ID を発行し、`data/work/{job_id}/job_meta.json` に実行情報を記録する |
| **入力** | `IngestResult`（バリデーション済みパス） |
| **出力** | `data/work/{job_id}/job_meta.json`（job_id / 実行日時 ISO8601 / 入力ファイルパス） |
| **依存タスク** | TASK-01-01 |
| **完了条件** | job_id が発行される / 同一動画の2回実行で異なる job_id になる / job_meta.json の内容が正しい |
| **テスト観点** | job_id の一意性確認 / job_meta.json のスキーマ確認 / ディレクトリの自動作成確認 |

---

### Phase 2: preprocess

---

#### TASK-02-01: 音声抽出（FFmpeg）

| 項目 | 内容 |
|---|---|
| **目的** | 動画から 16kHz モノラル WAV 音声を FFmpeg で抽出し、ASR への入力とする |
| **入力** | `IngestResult`（動画ファイルパス） / job_id |
| **出力** | `data/work/{job_id}/audio.wav`（16kHz / モノラル） |
| **依存タスク** | TASK-01-02, TASK-00-04 |
| **完了条件** | audio.wav が生成される / 16kHz モノラル WAV であることを確認できる / FFmpeg 失敗時に ProcessingError を返す |
| **テスト観点** | 正常系（mp4 / mov / mkv 各形式） / 音声トラックなし動画の検出と警告 / FFmpeg 未インストール時のエラー |

---

#### TASK-02-02: 音声前処理バリデーション

| 項目 | 内容 |
|---|---|
| **目的** | 抽出した音声の有効性を確認し、後続の ASR で問題が起きないことを保証する |
| **入力** | `data/work/{job_id}/audio.wav` |
| **出力** | `PreprocessResult`（音声ファイルパス / 音声長（秒） / サンプルレート） |
| **依存タスク** | TASK-02-01 |
| **完了条件** | 音声長が取得できる / 5秒未満の場合は警告ログを出力する（エラーではない） / 無音ファイルは警告 |
| **テスト観点** | 通常音声 / 5秒未満の短い音声 / 無音 WAV / 破損 WAV の処理 |

---

### Phase 3: asr

---

#### TASK-03-01: WhisperLocalProvider 実装

| 項目 | 内容 |
|---|---|
| **目的** | ローカル Whisper モデルを使ってタイムスタンプ付き文字起こしを実行する ASRProvider 実装を作る |
| **入力** | `PreprocessResult`（audio.wav パス） / 設定（モデルサイズ・言語） |
| **出力** | `Transcript`（TranscriptSegment のリスト。speaker は null） |
| **依存タスク** | TASK-00-05（ASRProvider インターフェース）, TASK-02-02 |
| **完了条件** | `Transcript` オブジェクトが生成される / 各セグメントに start_time・end_time・text が含まれる / speaker は null |
| **テスト観点** | 日本語音声での文字起こし動作 / タイムスタンプの存在・形式（HH:MM:SS）の確認 / モデルサイズ設定の切り替え |

---

#### TASK-03-02: transcript.json 出力

| 項目 | 内容 |
|---|---|
| **目的** | `Transcript` オブジェクトを `data/work/{job_id}/transcript.json` に永続化し、再実行時の再利用を可能にする |
| **入力** | `Transcript` オブジェクト / job_id |
| **出力** | `data/work/{job_id}/transcript.json` |
| **依存タスク** | TASK-03-01 |
| **完了条件** | transcript.json が正しいスキーマで出力される / 再読み込みで `Transcript` が完全に復元できる |
| **テスト観点** | JSON スキーマの確認（segments / language フィールド） / シリアライズ → デシリアライズの往復 / 空セグメントの扱い |

---

### Phase 4: analysis

---

#### TASK-04-01: input_builder 実装

| 項目 | 内容 |
|---|---|
| **目的** | `Transcript` のテキストを Claude API 送信用プロンプトに変換する。長い transcript はチャンク分割する |
| **入力** | `Transcript`（transcript.json から読み込み） |
| **出力** | `PromptInput`（プロンプト文字列 / 使用セグメント範囲） |
| **依存タスク** | TASK-03-02, TASK-00-02 |
| **完了条件** | プロンプトが生成される / トークン数上限を超える場合に分割される / 空 transcript は空コンテンツとして扱う |
| **テスト観点** | 短い transcript（分割なし） / 長い transcript（分割発生） / 空の transcript / タイムスタンプ・話者情報の含め方 |

---

#### TASK-04-02: extractor 実装（Claude API 呼び出し）

| 項目 | 内容 |
|---|---|
| **目的** | Claude API を呼び出し、要約・議題・決定事項・保留事項・ToDo候補を構造化 JSON として取得する |
| **入力** | `PromptInput` / Claude API 設定（モデル名・APIキー） |
| **出力** | `RawAnalysisJSON`（LLM 生成の未検証 JSON 文字列） |
| **依存タスク** | TASK-04-01, TASK-00-03 |
| **完了条件** | Claude API が呼び出せる / JSON 形式のレスポンスが得られる / API エラー時にリトライ（最大3回）する / リトライ超過時は LLMError |
| **テスト観点** | 正常応答 / API エラー時のリトライ動作 / タイムアウト処理 / モデル名設定の切り替え / **単体テストでは Claude API をモック/スタブに差し替えて実行する（外部API呼び出しを行わない）** |

---

#### TASK-04-03: validator 実装

| 項目 | 内容 |
|---|---|
| **目的** | LLM が返した JSON のスキーマバリデーションを行い、不正な出力を検出する |
| **入力** | `RawAnalysisJSON`（未検証 JSON 文字列） |
| **出力** | `ValidatedAnalysisJSON` または LLMError |
| **依存タスク** | TASK-04-02 |
| **完了条件** | 正常スキーマの JSON はパスする / 必須フィールド欠落・型不一致は LLMError を発生させる / スキーマ不正時は再プロンプト要求を extractor に返せる |
| **テスト観点** | 正常スキーマ / summary 欠落 / todos 型不一致 / 完全に不正な JSON（parse 失敗） |

---

#### TASK-04-04: postprocess 実装

| 項目 | 内容 |
|---|---|
| **目的** | 検証済み JSON を `AnalysisResult` に変換し、candidate フラグ付与と後処理を行う |
| **入力** | `ValidatedAnalysisJSON` |
| **出力** | `AnalysisResult` / `data/work/{job_id}/analysis.json` |
| **依存タスク** | TASK-04-03 |
| **完了条件** | `AnalysisResult` が生成される / `owner_candidate` / `due_date_candidate` が設定される / decisions・todos の重複が除去される / 「来週」等の曖昧表現がそのまま保持される |
| **テスト観点** | candidate フィールドの設定確認 / 重複 decisions の除去 / 曖昧表現（「月末」「来週」）の保持 / analysis.json のスキーマ確認 |

---

### Phase 5: formatter

---

#### TASK-05-01: 標準議事録テンプレート作成

| 項目 | 内容 |
|---|---|
| **目的** | `requirements.md` §8.3 の標準議事録形式を出力する Jinja2 テンプレートを作成する |
| **入力** | requirements.md §8.3 のテンプレート仕様（会議情報〜参考ログの8セクション） |
| **出力** | `src/formatter/templates/standard.md.j2` |
| **依存タスク** | TASK-00-02 |
| **完了条件** | テンプレートが全8セクションを含む / データがない項目は空欄またはデフォルト文字列で出力される |
| **テスト観点** | 全セクションの出力確認 / 空の decisions・todos での出力確認 / ToDo テーブルの列（タスク / 担当候補 / 期限候補 / 備考）の確認 |

---

#### TASK-05-02: StandardFormatter 実装

| 項目 | 内容 |
|---|---|
| **目的** | `AnalysisResult` + `Transcript` + `MeetingInfo` を入力として、標準議事録 Markdown 文字列を生成する |
| **入力** | `AnalysisResult` / `Transcript` / `MeetingInfo` |
| **出力** | Markdown 文字列（メモリ内） |
| **依存タスク** | TASK-05-01, TASK-00-05（FormatterProvider インターフェース） |
| **完了条件** | FormatterProvider インターフェースを満たす / 全8セクションが Markdown として出力される / 参考ログに `[HH:MM:SS]` 形式のタイムスタンプが含まれる |
| **テスト観点** | 全セクションの出力確認 / 空データ（決定事項なし・ToDo なし）での動作 / タイムスタンプ形式の確認 |

---

### Phase 6: export

---

#### TASK-06-01: Markdown 出力

| 項目 | 内容 |
|---|---|
| **目的** | 整形済み Markdown 文字列を `data/output/{job_id}/minutes.md` に書き出す |
| **入力** | Markdown 文字列 / job_id |
| **出力** | `data/output/{job_id}/minutes.md` |
| **依存タスク** | TASK-05-02 |
| **完了条件** | ファイルが正しく書き出される / 出力先ディレクトリが存在しない場合は自動作成される / OutputError は即時終了 |
| **テスト観点** | ファイル内容の確認（先頭行が `# 議事録`） / 出力先ディレクトリの自動作成 / 書き込み権限なし時の OutputError |

---

#### TASK-06-02: JSON 出力

| 項目 | 内容 |
|---|---|
| **目的** | `MinutesOutput` オブジェクトを `data/output/{job_id}/minutes.json` に書き出す |
| **入力** | `MinutesOutput`（MeetingInfo + AnalysisResult + Transcript を統合） / job_id |
| **出力** | `data/output/{job_id}/minutes.json` |
| **依存タスク** | TASK-04-04, TASK-05-02 |
| **完了条件** | JSON が正しく書き出される / 再読み込みで `MinutesOutput` が完全に復元できる / インデント付き（pretty-print）で出力 |
| **テスト観点** | JSON スキーマの確認（全フィールド） / シリアライズ → デシリアライズの往復 / `owner_candidate` / `due_date_candidate` の出力確認 |

---

#### TASK-06-03: manifest.json 出力

| 項目 | 内容 |
|---|---|
| **目的** | 出力ファイル一覧・生成日時・job_id を `manifest.json` に記録し、監査性を担保する |
| **入力** | job_id / 出力ファイルパスリスト / 生成日時 |
| **出力** | `data/output/{job_id}/manifest.json`（job_id / generated_at（ISO8601） / files / source_transcript） |
| **依存タスク** | TASK-06-01, TASK-06-02 |
| **完了条件** | manifest.json に job_id・generated_at・files・source_transcript が含まれる / files は実際に生成されたファイル名の一覧 |
| **テスト観点** | manifest のスキーマ確認 / generated_at の ISO8601 形式確認 / files のパス正確性 |

---

### Phase 7: pipeline

---

#### TASK-07-01: Pipeline Runner 実装

| 項目 | 内容 |
|---|---|
| **目的** | ingest → preprocess → asr → analysis → formatter → export を順番に実行する統合ランナーを実装する |
| **入力** | 動画ファイルパス / `MeetingInfo`（会議名・日時・参加者） |
| **出力** | 各ステージの実行結果（最終的に minutes.md / minutes.json / manifest.json） |
| **依存タスク** | Phase 1〜6 全タスク完了（TASK-01-01〜TASK-06-03） |
| **完了条件** | 全ステージが順番に実行される / 各ステージの出力が次のステージに正しく渡される / いずれかのステージ失敗でパイプラインが停止し、失敗ステージをログに記録する |
| **テスト観点** | 正常系エンドツーエンド実行（フィクスチャ動画使用） / 中間ステージでの失敗時の停止確認 |

---

#### TASK-07-02: ステージスキップ機構

| 項目 | 内容 |
|---|---|
| **目的** | 既存の中間ファイルを検出して完了済みステージをスキップし、再実行コストを削減する |
| **入力** | job_id / ステージ名 |
| **出力** | スキップ判定結果（bool） / 既存ファイルのデータ（スキップ時） |
| **依存タスク** | TASK-07-01 |
| **完了条件** | `data/work/{job_id}/{stage_output}` が存在する場合はステージをスキップし既存ファイルを読み込む / `--force` 指定時は強制再実行する |
| **テスト観点** | スキップあり・なしの両ケース / `--force` オプションでの強制再実行 / 中間ファイルが破損している場合の再実行 |

---

#### TASK-07-03: CLI エントリポイント実装

| 項目 | 内容 |
|---|---|
| **目的** | コマンドラインから Pipeline Runner を実行できる CLI を実装する |
| **入力** | `--input`（動画パス）/ `--title` / `--datetime` / `--participants` / `--job-id`（オプション）/ `--force`（オプション） |
| **出力** | CLI コマンド（例: `python -m vmg` または `video-minutes`） |
| **依存タスク** | TASK-07-01, TASK-07-02 |
| **完了条件** | CLI コマンドで全処理が実行される / `--help` が表示される / 必須引数欠落時にエラーメッセージと使い方が表示される |
| **テスト観点** | 正常実行（全引数指定） / 必須引数欠落時のエラー / `--help` の出力確認 / `--force` 付き実行 |

---

#### TASK-07-04: エンドツーエンド統合テスト

| 項目 | 内容 |
|---|---|
| **目的** | フィクスチャ動画（短いテスト用動画）を使って、一連の処理が完走し正しい出力が得られることを確認する |
| **入力** | `tests/fixtures/` の短尺テスト動画（< 1分を前提。Whisper・Claude API 呼び出しを伴うため長尺動画は使用しない） |
| **出力** | `data/output/{job_id}/minutes.md` / `data/output/{job_id}/minutes.json` / `data/output/{job_id}/manifest.json` |
| **依存タスク** | TASK-07-03 |
| **完了条件** | テスト動画を入力として3ファイルが生成される / minutes.md に全8セクションが含まれる / minutes.json が MinutesOutput スキーマに準拠する / manifest.json に正しい job_id と generated_at が含まれる |
| **テスト観点** | 出力ファイルの存在確認 / JSON スキーマ確認 / Markdown 構造確認（`# 議事録` から始まる） / manifest の整合性（job_id・files の一致） / **本テストは処理時間が長いため `@pytest.mark.slow` 等のマーカーで分類し、通常の CI では省略・手動実行や専用ジョブに限定できる構成とする** |

---

## 4. 依存関係グラフ

```
TASK-00-01
  ├── TASK-00-02
  │     └── TASK-00-05
  │           ├── TASK-03-01 ─────────────────────────┐
  │           └── TASK-05-02 ──────────────────────┐  │
  ├── TASK-00-03                                   │  │
  │     └── TASK-04-02                             │  │
  └── TASK-00-04                                   │  │
        ├── TASK-01-01                             │  │
        └── TASK-02-01                             │  │
                                                   │  │
TASK-01-01 → TASK-01-02 → TASK-02-01 → TASK-02-02 ─┘  │
                                                        │
TASK-03-01 → TASK-03-02 → TASK-04-01 → TASK-04-02      │
  → TASK-04-03 → TASK-04-04 ─────────────────────────┐ │
                                                      │ │
TASK-00-02 → TASK-05-01 → TASK-05-02 ───────────────┘─┘
                                    │
                            TASK-06-01 ─┐
                            TASK-06-02 ─┼── TASK-06-03
                                        │
                            TASK-07-01 → TASK-07-02 → TASK-07-03 → TASK-07-04
```

---

## 5. MVP 対象外（将来拡張）

以下は本タスク分解の対象外。将来の Should / Later フェーズで対応する。

| 機能 | 対応フェーズ |
|---|---|
| 話者分離（diarization） | Should |
| 固有名詞辞書補正 | Should |
| 同一文字起こしからの再フォーマット | Should |
| DOCX / PDF 出力 | Later |
| 管理職向け・タスク特化型フォーマット | Later |
| transcript 匿名化・マスキングモード | Later |
| ローカルLLM（Ollama 等）対応 | Later |
| UI 編集画面 | Later |

---

## 6. 本書の位置付け

本書は `architecture.md` に続く第3の設計成果物である。  
以後は以下の順で成果物を拡張する。

1. requirements.md
2. architecture.md
3. task-breakdown.md（本書）
4. test-plan.md
5. implementation plan

---
