---
name: vega-runtime
description: スキルのPythonスクリプトを実行する同梱Pythonランタイムの呼び出し方（bash・PowerShell などシェルごと）と、ランタイムが見つからない・壊れているときの対処。Pythonスクリプトを持つスキルから参照される。
---

# vega-runtime

スクリプトを持つスキルが使う同梱Python。依存パッケージは導入済みで、実行時にシステムのPythonもネットワークも使わない。

## 呼び出し方

`<runtime-dir>` はこのスキルのディレクトリ（読み込み時に表示される "Base directory for this skill"）。

| シェル | 入口 |
|---|---|
| bash / git-bash | `<runtime-dir>/runtime/bin/python` |
| PowerShell / cmd.exe（Windows） | `<runtime-dir>\runtime\bin\python.bat` |

呼び出し元のスキルからは、ユーザーの作業ディレクトリのまま（`cd` しない）次の形で実行する。
`<skill-dir>` は呼び出し元スキルのディレクトリ（そのスキルの "Base directory for this skill"）:

```bash
<skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/<script>.py ...
```

- 入口は `-s -E -X utf8` 付きで起動する（ユーザーの site-packages と `PYTHON*` 環境変数を無視し、入出力は UTF-8）。
- システムの `python` は使わない。`pip install` もしない。

### Windows の PowerShell / cmd.exe

OpenCode は Windows では既定で PowerShell を使う（git-bash から起動した場合などは bash）。
PowerShell / cmd.exe では `runtime/bin/python`（shスクリプト）は動かないので、`python.bat` を `\` 区切り・引用符付きで呼ぶ:

```powershell
& "<skill-dir>\..\vega-runtime\runtime\bin\python.bat" "<skill-dir>\scripts\<script>.py" ...
```

`python.bat` は引数を cmd.exe に渡し直すため、`&` `|` `<` `>` `^` `%` を含む引数は壊れることがある。
その場合は同じフラグで直接呼ぶ（`win-x64` は `runtime\` 内にある `win-*` フォルダの名前に合わせる）:

```powershell
& "<runtime-dir>\runtime\win-x64\python\python.exe" -s -E -X utf8 "<skill-dir>\scripts\<script>.py" ...
```

## ランタイムが無い・壊れているとき

次のときだけ `<runtime-dir>/references/setup.md` を読んでその手順に従う。それ以外のときは読まない。

- 呼び出し元から見た入口（`<skill-dir>/../vega-runtime/runtime/bin/python`、Windows は `python.bat`）が存在しない
- 入口で実行したスクリプトが `ModuleNotFoundError` / `ImportError`、「vega-runtime is incomplete」、または入口自体の `No such file` で失敗した
