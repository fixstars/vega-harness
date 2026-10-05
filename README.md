# Fixstars Vega Harness

[Fixstars Vega](https://www.fixstars.com/ja/products-services/vega) 上で AI 駆動開発を行うためのハーネス。
オンプレミス・オフラインの OpenCode + open-weight LLM 環境に、AIエージェントが実務を行うためのスキルを追加する。

## 収録スキル

| スキル | できること |
|---|---|
| vega-ai-native-audit | 開発プロジェクトでAIエージェントが自律的に回るかを診断し、つまずき箇所と改善手順を示す |
| vega-pdf | PDFの読み取り（スキャン文書のOCR対応）と、フォームの作成・記入、結合・分割、透かし、暗号化、メタデータ編集 |
| vega-xlsx | Excelの読み取り・作成・編集（数式・グラフ・表、CSV変換） |
| vega-docx | Wordの読み取り・作成・編集（テンプレート適用、コメント・変更履歴の確認） |
| vega-powerpoint | PowerPointの読み取り・作成・編集（テンプレート適用、スライド画像の書き出し） |
| vega-grill-me | 企画・設計を1問ずつ質問で詰め、曖昧さを残さず固める |
| vega-skill-creator | AIスキルの作成・改良と、テストによる品質評価・呼び出されやすさの最適化 |
| vega-working-memory | セッションをまたいで作業の経緯・決定事項を保持する |
| vega-runtime | 他スキルが使う同梱Pythonランタイム（未導入なら初回利用時に確認のうえ導入） |

普段どおり日本語で依頼するだけで、内容に合ったスキルが自動で使われる
（例:「このPDFを読んで」「この表をExcelにまとめて」「この企画の詰めが甘い点を質問して」）。

## 動作要件

### 依存アプリケーション

- **OpenCode**
- **同梱Python（`vega-runtime` スキル）**
  - 下記手順2で導入する（省略した場合は初回利用時に確認のうえ導入）

### 対応OS

- Windows（PowerShell / git-bash）
- Linux （Ubuntu系）

## インストール

### 1. リポジトリを取得

```sh
git clone https://github.com/fixstars/vega-harness.git
cd vega-harness
```

スキルは `.agents/skills/` に入っているため、このディレクトリで OpenCode を起動するとスキルが読み込まれます。

### 2. Pythonランタイムを導入（`vega-runtime`）

`bash .agents/skills/vega-runtime/scripts/build-runtime.sh` を実行する（要ネット接続。Windowsはgit-bash）。
省略した場合は、初回利用時にエージェントが確認のうえ実行する。

オンライン上から入手が難しい場合は、別途担当者へご相談ください。

詳細は `.agents/skills/vega-runtime/README.md` を参照。

### 他のプロジェクトで使う

`.agents/skills/` の中身を、次のどちらかにコピーする:

| 配置先 | スコープ |
|---|---|
| `<プロジェクト>/.agents/skills/` | プロジェクト単位 |
| `~/.agents/skills/` | ユーザー全体 |

各スキルは同じ配置先の `vega-runtime` のPythonを使うため、スキルは分けずにまとめてコピーする。

## ライセンス

- 本リポジトリの自作部分: **Apache-2.0**（ルート `LICENSE`）
- 各スキルのライセンスは各ディレクトリの `LICENSE` に従う（MIT または Apache-2.0）
    - 由来・変更点は各スキル内の `ATTRIBUTION.md` に記載
- `vega-pdf` 同梱のフォント（BIZ UDPゴシック）: **SIL Open Font License 1.1**（`.agents/skills/vega-pdf/assets/fonts/OFL.txt`）
