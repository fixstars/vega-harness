---
name: vega-ai-native-audit
description: FDE entry diagnosis. Evaluates a customer project against Fixstars' standard agent development flow (onboarding, planning, implementation, verification, review, external integration, safe operation), identifies where the flow would break, and produces a work plan to clear the blockers plus skill/MCP handoff candidates. Use when an FDE is assigned to a customer project, before deploying a coding agent, or to re-diagnose progress.
---

# AI-Native Audit — フロー阻害要因の診断

顧客プロジェクトに標準のエージェント開発フローを回したとき、どこで詰まるかを診断し、解除計画を作る。

**フロー**: オンボーディング → 計画 → 実装 → 検証 → レビュー → 外部連携（必要時のみ） → 安全運用 → skill化

## 診断項目（15）

**着手ゲート** — ここが止まると着手できない:

| 項目 | 見ること |
|---|---|
| `repository-access` | リポジトリの読み書き（git remote の実効確認） |
| `issue-tracker-access` | issue/MRトラッカー（gh / glab）の読み書き |
| `external-system-access` | 必要な外部システムと到達手段（MCP / CLI / script） |
| `ci-visibility` | CI設定（稼働中のものか。レガシーCIのみなら PARTIAL） |
| `environment-reproducibility` | lockfile・バージョンピン |
| `verification-commands` | 一発検証（lint/typecheck/test を1コマンドで。タスクランナー、package.json scripts、pytest 等の設定を手掛かりに判定） |
| `test-assets` | テスト本体の実在（テストが無いと、コードが壊れたことを自律検出できない） |
| `dev-env-provisioning` | 環境構築の1コマンド性（compose / devcontainer / bootstrap） |
| `agent-docs` | AGENTS.md（コマンド・規約の入口） |

**継続ワークフロー** — 回り続けるための整備:

| 項目 | 見ること |
|---|---|
| `review-criteria` | レビュー基準（CONTRIBUTING、definition of done）とMRテンプレート |
| `context-docs` | 用語集・ADR による背景供給 |
| `test-isolation` | テストの独立性（外部URL直書き vs モック。エアギャップ・flaky対策） |
| `skill-candidates` | 繰り返し手順のskill化候補 |

**安全運用**:

| 項目 | 見ること |
|---|---|
| `secret-hygiene` | コミット済み秘密情報（本番は FAIL。テスト用鍵や秘密値なしの .env は PARTIAL） |
| `agent-permissions` | エージェントの権限ポリシー（opencode.json 等、AGENTS.md の権限記述） |

## 手順

スクリプトは隣接する `vega-runtime` スキルが提供するPythonで、ユーザーの作業ディレクトリから実行する（このスキルのディレクトリへ `cd` しない）:

```bash
<skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/audit_scan.py ...
```

`<skill-dir>` は、このスキルを読み込んだときに表示される "Base directory for this skill" の絶対パス。ファイル引数は通常どおり作業ディレクトリ基準で解決される。Windows の PowerShell / cmd.exe では `<skill-dir>\..\vega-runtime\runtime\bin\python.bat` を使う。依存は導入済み。システムの `python` は使わない。

このPythonが無い場合は実行を止め、システムPythonへのフォールバックやパッケージ導入をせず、`vega-runtime` スキルの手順に従う（導入はユーザーの了承を得てから）。

1. **スキャン**（まず実行）:
   ```bash
   <skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/audit_scan.py <root> --out audit.json
   ```
   各項目を PASS / PARTIAL / FAIL / UNKNOWN で判定し、`work_plan`（担当・工数・影響付き、FAIL→UNKNOWN順）と `handoff`（skill化・外部連携の整備候補）を出す
2. **UNKNOWNの補完**（判断系）: `external-system-access`（必要な外部システムと到達手段）/ `verification-commands`（コマンドの実実行、ユーザー同意ベース）/ `agent-docs`・`review-criteria`（文書の質）/ `skill-candidates`（skill化候補 → vega-skill-creator へ）/ `agent-permissions`（権限ポリシーの実効性）
3. **レポート**: `ai-native-audit-report.md` に ①フロー別の問題 ②解除計画（quick → structural の順、顧客依頼事項を明示）③整備候補と再診断条件（何が PASS になれば前進か）を保存し、要約をチャットに表示

## 原則

- **探索優先**: コード・git・CLI で分かることは探索で済ませ、人への確認は最後にする（1問ずつ、推奨答案付き）
- 各判定にエビデンス（実行コマンドと結果）を添える。実行は読み取り・探索・同意を得たテストに限る
- 判定基準は「フローが止まるか」。手段が代替可能なら PASS とする
