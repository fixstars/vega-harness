---
name: vega-working-memory
description: ワークスペース直下の .working-memory/ を、計画・実装・調査で知り得た重要な情報や決定を記録するメモ帳として使う。セッション開始時・compact 前後の復元起点として読み、作業中は学んだそばから追記する。Use when starting or resuming a session, before context compaction, or when important findings or decisions should be recorded. Persistent working memory across sessions.
metadata:
  scope: universal
---

# working-memory

ワークスペース直下の `.working-memory/` を、エージェントが自由に読み書きできるメモ置き場として扱う（compact前の情報の置き場としても利用する）。

一時的な使い捨ての作業状態。**git の管理外**に置く（成果物は docs や PR に昇格してからコミットする）。git 管理外なので、ユーザにデータを置いてもらうとき・表示用データ（HTML等）を出すときの作業領域としても使う。

## 3つの層

- **インデックス** — `00-summary.md`。トピック横断の目次（リンク + 1行要約 + ステータス）。compact 後の再入場ポイント。
- **サマリ** — `{tt}-00-{slug}.md`、トピックごとに1つ。〜20行、**上書き**で更新: 結論 / 現状 / 次の一手。
- **詳細** — `{tt}-{ss}-{slug}.md`、セッションごとに1つ。**追記のみ**、密でよい（読み返す用途にはサマリ層を使う）。

`tt` = トピック連番、`ss` = セッション連番、`-00-` はサマリ用に予約。

## ルール

1. なければ `mkdir -p .working-memory`。新トピックは次の `tt`。セッションごとに詳細ファイルを `{tt}-01`, `{tt}-02`, … と増やす
2. 学んだそばから詳細に追記する（各コミットや次の手順の前に。ユーザーに問い合わせず書いてよい）
3. サマリを常に最新に保つ（上書き更新）。詳細ログは**追記のみのまま**保つ
4. 文脈が重くなってきたら `.working-memory` に書き出し、ユーザーに compact を促す（実行できるのは本人だけ）
5. インデックス（`00-summary.md`）とトピックサマリを最新に保つ。なければ作る
6. **git の管理外に置く** — グローバルignore（`git config --global core.excludesFile ~/.config/git/ignore` し、そのファイルに `.working-memory/` を追加）で追跡対象から外す。グローバル設定が使えない環境では、プロジェクトの `.gitignore` に `.working-memory/` を追加する

## セッション上で共有するとき

- **要約して伝える** — 結論 → 何の話か → 方針 → 具体 の順。読み手が次の行動を決められる情報に絞る
- **自己完結で書く** — 番号ラベル・略号に頼らず、その場で意味が取れる形にする（1週間後に読み返しても分かるように）

## 開始時の手順

1. `.working-memory/00-summary.md` があれば読む（無ければこのセッションで作る）
2. 関連トピックのサマリ `{tt}-00-*.md` を読む
3. 必要なら直近の詳細ファイルを確認し、`git log --oneline -10` と `git status` で実コードとの差分を埋める
4. ユーザーに前回の状態を1〜3行で要約してから作業に入る
