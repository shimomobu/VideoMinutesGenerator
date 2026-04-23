# test-plan.md

# 動画議事録生成システム テスト計画書 v0.1（MVP）

## 1. 文書目的

本書は `requirements.md` / `architecture.md` / `task-breakdown.md` に基づき、MVP実装に対するテスト方針・対象・観点・受け入れ基準を定義する。  
実装と並行してテストを整備し、各ステージが独立して検証できる構成とする。

---

## 2. テスト方針

### 2.1 基本方針

| 方針 | 内容 |
|---|---|
| TDD | 実装前にテストを書く（RED → GREEN → REFACTOR） |
| 疎結合テスト | 各モジュールは外部依存を最小化した状態で単体テストできること |
| 外部API分離 | Ollama・FFmpeg・Whisper の呼び出しは単体テストではモック/スタブに差し替える |
| カバレッジ目標 | 単体テスト・結合テストを合わせて `src/` 配下で **80%以上** を最低ラインとする（E2Eテストはカバレッジ目標の主対象外） |
| E2E限定実行 | E2Eテストは処理が重いため `@pytest.mark.slow` で分類し、通常の CI では省略可能とする |

### 2.2 テスト種別と役割

| 種別 | 目的 | 外部依存 | 実行場所 |
|---|---|---|---|
| 単体テスト（unit） | モジュール・関数の動作確認 | モック/スタブ | すべての CI / ローカル |
| 結合テスト（integration） | ステージ間のデータ受け渡し確認 | 最小限の実ファイル | CI / ローカル |
| E2Eテスト | パイプライン全体の完走確認 | 実Whisper・実Claude API | 限定実行（手動またはCI専用ジョブ） |

### 2.3 テスト配置方針

```
tests/
  unit/
    test_models.py
    test_config.py
    test_logger.py
    test_ingest.py
    test_preprocess.py
    test_asr.py
    test_analysis_input_builder.py
    test_analysis_extractor.py
    test_analysis_validator.py
    test_analysis_postprocess.py
    test_formatter.py
    test_export.py
    test_pipeline.py
  integration/
    test_ingest_to_preprocess.py
    test_preprocess_to_asr.py
    test_asr_to_analysis.py
    test_analysis_to_export.py
    test_pipeline_skip.py
  fixtures/
    sample_short.mp4        # < 1分の短尺テスト動画
    transcript_sample.json  # 文字起こしサンプル
    analysis_sample.json    # 解析結果サンプル
```

---

## 3. 単体テスト（unit test）対象一覧

### 3.1 共通基盤

| テスト対象 | ファイル | 主なテストケース |
|---|---|---|
| 型定義（models） | `src/common/models.py` | 正常値での構築 / 必須フィールド欠落時の ValidationError / JSON シリアライズ → 再構築往復 / `owner_candidate`・`due_date_candidate` が `str \| None` |
| 設定管理（config） | `src/common/config.py` | YAML 正常読み込み / 必須キー欠落時の ConfigError / 環境変数による APIキー上書き |
| 構造化ロガー（logger） | `src/common/logger.py` | 全フィールド含む JSON Lines 出力 / ファイル追記確認 / ステージ名フォーマット（`"analysis.extractor"` 形式） |
| インターフェース | `src/common/interfaces.py` | 継承した最小実装クラスの動作 / 抽象メソッド未実装時の TypeError |

### 3.2 ingest

| テスト対象 | 主なテストケース |
|---|---|
| ファイルバリデーション | mp4 / mov / mkv の受け付け / 存在しないパスの ValidationError / 非対応拡張子の ValidationError / 拡張子なしファイルの拒否 |
| ジョブID発行 | 一意性（同一動画の2回実行で別ID） / job_meta.json のスキーマ確認 / 出力ディレクトリの自動作成 |

### 3.3 preprocess

| テスト対象 | 主なテストケース |
|---|---|
| 音声抽出ロジック | FFmpeg コマンド生成の確認（スタブ） / 出力ファイルパスの確認 / ProcessingError の発生（FFmpeg 失敗時） |
| 音声前処理バリデーション | 音声長の取得 / 5秒未満の警告ログ出力 / 無音 WAV の警告 |

### 3.4 asr

| テスト対象 | 主なテストケース |
|---|---|
| WhisperLocalProvider | Whisper スタブを使った Transcript 生成 / 各セグメントの start_time・end_time・text の存在確認 / speaker が null であること / HH:MM:SS 形式のタイムスタンプ確認 |
| transcript.json 出力 | JSON スキーマ確認（segments / language フィールド） / シリアライズ → デシリアライズ往復 / 空セグメントの扱い |

### 3.5 analysis

| テスト対象 | 主なテストケース |
|---|---|
| input_builder | 短い transcript（分割なし）のプロンプト生成 / 長い transcript（分割発生）のチャンク分割 / 空 transcript の処理 |
| extractor | Ollama（httpx）モック経由の正常応答 / 接続エラー時のリトライ（最大3回）/ リトライ超過時の LLMError / **単体テストでは httpx.post をモック/スタブに差し替えて実行する** |
| validator | 正常スキーマのパス / 必須フィールド欠落の LLMError / 型不一致の LLMError / JSON parse 失敗の LLMError |
| postprocess | `owner_candidate` / `due_date_candidate` の設定確認 / 重複 decisions の除去 / 「来週」「月末」等の曖昧表現の保持 / analysis.json のスキーマ確認 |

### 3.6 formatter

| テスト対象 | 主なテストケース |
|---|---|
| StandardFormatter | 全8セクションの出力確認 / 空データ（decisions なし・todos なし）での動作 / ToDo テーブルの列（タスク / 担当候補 / 期限候補 / 備考） / `[HH:MM:SS]` 形式のタイムスタンプ確認 |
| Jinja2 テンプレート | テンプレート構文エラーのない確認 / 変数未定義時のデフォルト値出力 |

### 3.7 export

| テスト対象 | 主なテストケース |
|---|---|
| Markdown 出力 | ファイル内容確認（先頭行が `# 議事録`） / 出力ディレクトリの自動作成 / OutputError（書き込み権限なし） |
| JSON 出力 | JSON スキーマ確認 / シリアライズ → デシリアライズ往復 / `owner_candidate`・`due_date_candidate` の出力確認 |
| manifest.json 出力 | job_id / generated_at（ISO8601）/ files / source_transcript の存在確認 / files のパス正確性 / **再実行時に manifest.json をいつ上書きするかは実装時に運用方針を確定する（要検討）** |

### 3.8 pipeline

| テスト対象 | 主なテストケース |
|---|---|
| スキップ判定 | 中間ファイルあり → スキップ確認 / 中間ファイルなし → 実行確認 / `--force` 時の強制実行 |
| エラーハンドリング | 中間ステージ失敗時のパイプライン停止 / ログへの失敗ステージ記録 |

---

## 4. 結合テスト（integration test）対象一覧

| テスト名 | 範囲 | 確認内容 |
|---|---|---|
| ingest → preprocess | TASK-01-01 〜 TASK-02-02 | IngestResult を preprocess に渡し、audio.wav が生成されること |
| preprocess → asr | TASK-02-02 〜 TASK-03-02 | audio.wav を asr に渡し、transcript.json が生成されること（Whisper スタブ使用） |
| asr → analysis | TASK-03-02 〜 TASK-04-04 | transcript.json を analysis に渡し、analysis.json が生成されること（Claude API モック使用） |
| analysis → formatter → export | TASK-04-04 〜 TASK-06-03 | analysis.json を formatter に渡し、minutes.md / minutes.json / manifest.json が生成されること |
| pipeline スキップ機構 | TASK-07-01, TASK-07-02 | 既存中間ファイルがある場合にステージがスキップされること / `--force` で強制再実行されること |

---

## 5. モック対象

| 外部依存 | モック方法 | 適用テスト種別 |
|---|---|---|
| **Ollama HTTP API**（`httpx.post`） | `mocker.patch("httpx.post")` でレスポンスを固定 | 単体テスト・結合テスト |
| **FFmpeg**（`subprocess.run`） | `subprocess.run` をモックし、正常終了・失敗をシミュレート | 単体テスト |
| **Whisper モデル**（`whisper.load_model`） | モデルロードと `transcribe` をスタブ化し、サンプル transcript を返す | 単体テスト・結合テスト |
| **ファイルシステム（書き込み）** | `tmp_path`（pytest 組み込み）を使用して実ファイル書き込みを分離 | 単体テスト |

> **方針**: E2Eテスト以外では実際の Ollama・FFmpeg・Whisper を呼び出さない。  
> 単体テストで `httpx.post` をモック化することで、Ollama 起動依存・応答時間を排除する。

---

## 6. 異常系テスト観点

### 6.1 入力異常

| 観点 | 期待する動作 |
|---|---|
| 存在しない動画ファイルを指定 | ValidationError / エラーメッセージ表示 |
| 非対応形式の動画ファイル（例: `.avi`） | ValidationError / エラーメッセージ表示 |
| 音声トラックのない動画 | 警告ログ出力後に処理継続（または ProcessingError） |
| 5秒未満の極短時間音声 | 警告ログ出力後に処理継続 |
| 空の文字起こし結果（無音・聞き取り不能） | 空 Transcript として analysis へ渡す / summary が空でも異常終了しない |

### 6.2 外部処理異常（Ollama）

| 観点 | 期待する動作 |
|---|---|
| Ollama 未起動・接続エラー | 最大3回リトライ後に LLMError（base_url / model / 起動確認を含むメッセージ） |
| タイムアウト | 最大3回リトライ後に LLMError |
| HTTP エラーレスポンス（500 等） | 最大3回リトライ後に LLMError |
| 不正な JSON レスポンス（parse 失敗） | validator が LLMError を発生させる |
| 必須フィールド欠落のレスポンス | validator が LLMError を発生させ、再プロンプトを試みる（最大2回） |

### 6.3 ファイルシステム異常

| 観点 | 期待する動作 |
|---|---|
| 出力先ディレクトリへの書き込み権限なし | OutputError / 即時終了 |
| 中間ファイルが破損している（JSON parse 失敗） | 破損ステージから再実行（`--force` と同等の挙動） |
| ディスク容量不足 | OutputError / 即時終了 |

### 6.4 処理内容の境界値

| 観点 | 期待する動作 |
|---|---|
| 決定事項が0件の会議 | decisions が空リストで正常出力（エラーにしない） |
| ToDo が0件の会議 | todos が空リストで正常出力（エラーにしない） |
| 参加者が0人（未設定） | participants が空リストで正常出力 |
| `due_date_candidate` が「来週」「月末」など曖昧表現 | 文字列をそのまま保持（正規化しない） |
| 非常に長い会議（チャンク分割が発生） | 分割後の各チャンクが正常に処理され、結果が統合される |

---

## 7. 最低限の受け入れ基準

### 7.1 コード品質

| 基準 | 閾値 |
|---|---|
| 単体テストのカバレッジ | **80%以上**（測定対象は `src/` 配下のみ。E2Eテストは完走確認が主目的のためカバレッジ目標の主対象外とする） |
| 重点モジュール | `src/common/` と `src/analysis/` は特に単体テストを重点的に整備する（型定義・LLM呼び出し・バリデーション・後処理が集中するため） |
| 結合テストのパス | §4 の5テストすべてパス |
| 型チェック（mypy） | エラーなし |

### 7.2 機能要件の充足（requirements.md §10.1 MVP対応）

| 機能 | 受け入れ基準 |
|---|---|
| 動画取込（FR-01） | mp4 / mov / mkv を受け付け、不正形式を拒否できること |
| 音声抽出（FR-02） | FFmpeg で audio.wav が生成されること |
| 文字起こし（FR-03） | タイムスタンプ付きで transcript.json が生成されること |
| 会議要約生成（FR-05） | summary フィールドにテキストが含まれること |
| 議題抽出（FR-06） | agenda リストが生成されること（0件も許容） |
| 決定事項抽出（FR-07） | decisions リストが生成されること（0件も許容） |
| 保留事項抽出（FR-08） | pending_items リストが生成されること（0件も許容） |
| ToDo抽出（FR-09） | todos リストが生成されること / `owner_candidate`・`due_date_candidate` が候補値として含まれること |
| Markdown出力（FR-11） | 全8セクションを含む minutes.md が生成されること |
| JSON出力（FR-12） | MinutesOutput スキーマに準拠した minutes.json が生成されること |
| 再実行性（NFR） | 中間ファイルが存在するステージがスキップされること |
| 監査性（NFR） | manifest.json に job_id・generated_at・files が含まれること |
| 可観測性（NFR） | logs/{job_id}.jsonl に全ステージの実行ログが記録されること |

### 7.3 非機能要件

| 基準 | 内容 |
|---|---|
| 再実行性 | 中間ファイルが存在する場合、該当ステージをスキップして次ステージから再実行できること |
| セキュリティ | 音声・映像ファイルが外部APIに送信されないこと（extractor のログで確認） |
| エラーメッセージ | ValidationError / LLMError / OutputError 発生時に原因を特定できるメッセージが出ること |

---

## 8. E2Eテストの範囲と前提

### 8.1 目的

実際の Whisper と Ollama（ローカルLLM / Gemma 4）を使い、パイプライン全体が完走して正しい出力ファイルが生成されることを確認する。

### 8.2 前提・制約

| 項目 | 内容 |
|---|---|
| フィクスチャ動画 | `tests/fixtures/sample_short.mp4`（**< 1分の短尺動画のみ使用**。Whisper・Ollama 呼び出しを伴うため長尺動画は使用しない） |
| 実API使用 | ローカル Whisper モデル + ローカル Ollama（Gemma 4）を使用 |
| Ollama | Ollama が起動していること（`ollama serve` または常駐プロセス） |
| FFmpeg | 実行環境に FFmpeg がインストールされていること |
| Whisper モデル | `tiny` または `small` モデルを使用（テスト速度優先） |
| 実行条件 | `@pytest.mark.slow` でマーク。通常の CI では省略し、E2E専用ジョブまたは手動で実行する |

### 8.3 実行コマンド例

```bash
# 通常の CI（unit + integration のみ。E2E を除く）
pytest tests/unit/ tests/integration/ -v

# E2Eのみ実行（-m slow は @pytest.mark.slow マーク付きのテストのみ対象）
# 事前に Ollama を起動しておくこと: ollama serve
pytest tests/ -m slow -v

# すべて実行（unit + integration + E2E）
pytest tests/ -v
```

### 8.4 E2Eテストの確認項目

| 確認項目 | 期待する結果 |
|---|---|
| 出力ファイルの生成 | minutes.md / minutes.json / manifest.json の3ファイルが生成される |
| Markdown 構造 | `# 議事録` で始まる / 全8セクションのヘッダーが存在する |
| JSON スキーマ | MinutesOutput スキーマに準拠している |
| ToDo candidate | `owner_candidate` / `due_date_candidate` が含まれている |
| manifest 整合性 | job_id が一致する / files に実際の出力ファイル名が含まれる / generated_at が ISO8601 形式 |
| ログ記録 | `logs/{job_id}.jsonl` に全ステージのエントリが存在する |

### 8.5 E2E対象外（MVP外）

- 話者分離（diarization）の動作確認
- 60分超の長時間動画での処理
- 並列ジョブの競合確認

---

## 9. テストツール・ライブラリ

| ツール | 用途 |
|---|---|
| pytest | テストランナー |
| pytest-cov | カバレッジ計測 |
| pytest-mock | モック・スタブ |
| pydantic | 型バリデーション（models のテスト） |
| tmp_path（pytest 組み込み） | テスト用一時ディレクトリ |
| @pytest.mark.slow | E2E・重いテストのマーキング |

---

## 10. 本書の位置付け

本書は `task-breakdown.md` に続く第4の設計成果物である。  
以後は以下の順で成果物を拡張する。

1. requirements.md
2. architecture.md
3. task-breakdown.md
4. test-plan.md（本書）
5. implementation plan

---
