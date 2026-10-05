# vega-runtime

vega-harness のスキルが使う同梱Python。
[python-build-standalone](https://github.com/astral-sh/python-build-standalone) の CPython 3.12.14 に `requirements.txt` の依存を入れたもの。
`runtime/` は git 管理外。

## 導入

- オンライン: このディレクトリで `bash scripts/build-runtime.sh` を実行する（github.com と PyPI への接続が必要）。
  - Windows は git-bash で実行する（PowerShell の素の `bash` は WSL を起動することがある）。
  - 対象と同じ OS・CPU のマシンで実行する（バイナリは OS・CPU ごとに別）。
- 未導入のままスキルを使った場合は、エージェントがユーザーの確認をとってから上記を実行する。
- オフライン: 担当者から構築済みのパッケージを入手し、スキルの配置先（例: `<プロジェクト>/.agents/skills/`）に展開する。
  `vega-runtime/runtime/bin/` と `vega-runtime/runtime/<os>-<arch>/` ができていればよい。

## 確認

```sh
runtime/bin/python -m pip check
runtime/bin/python -c "import pypdf, reportlab, pdfplumber, pypdfium2, openpyxl, docx, pptx, yaml; print('ok')"
```

Windows の PowerShell では `runtime/bin/python` を `runtime\bin\python.bat` に置き換える。

## 注意

- Python のバージョンは `scripts/build-runtime.sh` の `PY_VERSION` / `PBS_TAG` で固定している。
