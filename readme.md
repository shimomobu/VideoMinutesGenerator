# Video Minutes Generator

会議動画から、要約・決定事項・保留事項・ToDo を含む議事録を自動生成するプロジェクト。

## 1. 目的

Video Minutes Generator は、会議動画を入力として以下を自動化することを目的とする。

- 音声抽出
- 文字起こし
- 話者単位または発話単位での整理
- 会議要約生成
- 決定事項抽出
- 保留事項抽出
- ToDo抽出
- Markdown / JSON 形式での議事録出力

## 2. スコープ

### 対象
- 会議動画ファイルの取り込み
- 音声抽出
- 文字起こし
- 議事録の自動生成
- Markdown / JSON 出力

### 対象外
- リアルタイム字幕
- 完全自動の本人特定ベース話者識別
- 法的証跡保証
- 初期段階での DOCX / PDF 出力

## 3. 想定ユースケース

- 定例会議の議事録作成
- プロジェクト会議の決定事項整理
- 打ち合わせ内容の要約共有
- ToDo と担当者の抽出
- 会議記録の再確認

## 4. ディレクトリ構成

```text
VideoMinutesGenerator/
├─ docs/
│  ├─ requirements.md
│  └─ architecture.md
├─ src/
│  ├─ ingest/
│  ├─ preprocess/
│  ├─ asr/
│  ├─ diarization/
│  ├─ analysis/
│  ├─ formatter/
│  ├─ export/
│  └─ common/
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  └─ fixtures/
├─ data/
│  ├─ input/
│  ├─ work/
│  └─ output/
├─ scripts/
├─ .claude/
├─ .github/
├─ logs/
├─ README.md
├─ .gitignore
└─ .env.example
```

## 5. モジュール責務

| モジュール | 役割 |
|---|---|
| ingest | 動画ファイル取込 |
| preprocess | 音声抽出、前処理 |
| asr | 音声認識、文字起こし |
| diarization | 話者分離 |
| analysis | 要約、議題、決定事項、保留事項、ToDo 抽出 |
| formatter | 議事録テンプレート整形 |
| export | Markdown / JSON 出力 |
| common | 共通処理、設定、ユーティリティ |

## 6. MVP

初期リリースで実装対象とする機能は以下。

- 動画取込
- 音声抽出
- 文字起こし
- 会議要約生成
- 決定事項抽出
- 保留事項抽出
- ToDo抽出
- Markdown 出力
- JSON 出力

## 7. 出力イメージ

```markdown
# 議事録

## 1. 会議情報
- 会議名:
- 日時:
- 参加者:
- 元動画ファイル:

## 2. 会議要約
- 

## 3. 議題
1. 
2. 

## 4. 議論内容
### 議題1
- 要点:
- 補足:

## 5. 決定事項
- 

## 6. 保留事項
- 

## 7. ToDo
| No | タスク | 担当 | 期限 | 備考 |
|---|---|---|---|---|
| 1 |  |  |  |  |

## 8. 参考ログ
- [00:00:00] Speaker A: ...
```

## 8. 開発方針

| 項目 | 方針 |
|---|---|
| 開発方式 | MVP先行 |
| 品質方針 | 完全自動高精度より、まず使える議事録を優先 |
| 設計方針 | 前処理、ASR、解析、フォーマッタを疎結合にする |
| 安全方針 | 元データ、中間データ、出力データを分離保存する |
| テスト方針 | 単体テストと結合テストを分離する |

## 9. 想定成果物

| ファイル | 内容 |
|---|---|
| docs/requirements.md | 要件定義 |
| docs/architecture.md | アーキテクチャ設計 |
| README.md | プロジェクト概要 |
| test-plan.md | テスト方針 |
| task-breakdown.md | タスク分解 |

## 10. 今後の拡張候補

- DOCX / PDF 出力
- UI による議事録編集
- 固有名詞辞書補正
- 外部ストレージ連携
- 検索機能
- リアルタイム処理

## 11. 備考

本 README はプロジェクト開始時点の初版であり、要件や設計の具体化に応じて更新する。
