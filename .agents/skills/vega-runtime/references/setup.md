# ランタイムの導入手順

ランタイムが無い・壊れているときだけ従う。
`<runtime-dir>` は vega-runtime スキルのディレクトリ、`<skill-dir>` は呼び出し元スキルのディレクトリ。

0. **先に有無を確かめる。** `<runtime-dir>/runtime/bin/python`（Windows は `python.bat`）があるか確認する（bash は `ls`、PowerShell は `Test-Path`）。
   - ある、かつ `<skill-dir>/../vega-runtime/runtime/bin/python` が無い: 配置の問題。構築せずに止め、
     「vega-runtime を他のスキルと同じフォルダに置いてください」と伝える（移動やリンク作成は自分でしない）。
   - ある、かつスクリプトが失敗した: 壊れている。1 へ進み、作り直してよいか尋ねる。
   - 無い: 1 へ進む。
1. **ユーザーの了承なしに実行しない。** 先に次を伝え、導入してよいか尋ねて返事を待つ（`question` ツールがあれば使う）:
   - 同梱Python（vega-runtime）が未導入、または壊れていること
   - 導入すると github.com と PyPI から約60〜140MB（OSによる）をダウンロードし、展開後は数百MB（Linuxで約450MB）になること
   - 導入先は `<runtime-dir>/runtime/` で、数分かかること
   - オフライン環境では導入できないこと
2. 断られた、またはユーザーがオフラインと答えたときは実行せずに止め、
   「担当者から構築済みのランタイムを入手し、スキルの配置先に展開してください」と伝える。
3. 了承されたら、作業ディレクトリのまま実行する。bash ツールの timeout は 900000（15分）を指定する。
   パスは引用符で囲み、`\` を `/` に置き換える:
   - bash / git-bash: `bash "<runtime-dir>/scripts/build-runtime.sh"`
   - PowerShell: `& "$env:ProgramFiles\Git\bin\bash.exe" "<runtime-dir>/scripts/build-runtime.sh"`
     （素の `bash` は WSL を起動することがあるので使わない）
   - `bash.exe` が見つからなければ git-bash の場所をユーザーに尋ねる。無ければ 2 と同じく止める。
4. 出力の最後に `==> verified` と `==> done` が出れば成功。元の作業に戻る。
   ダウンロードの進捗表示や、PowerShell が出す `NativeCommandError` はエラーではない。
5. 失敗したら、再試行や別の方法（システムのPython、`pip install`、スクリプトの書き換え）は試さない。
   エラー出力の要点をユーザーに伝え、担当者への相談を案内して止める。
   ダウンロードや依存の導入で失敗した場合、それまでのランタイムはそのまま残る。
