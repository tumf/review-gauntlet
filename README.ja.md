Review Gauntlet
===============

ファイル × ルールのカバレッジを追跡する、計画優先の AI コードレビュー。

Review Gauntlet は、AI コードレビューのための計画優先型カバレッジゲートです。レビュアーを実行する前に、ファイル × レビュールールのレビュー直交表を作成します。各セルは「このファイルをこのルールで確認する」という具体的なレビュー義務を表します。Review Gauntlet は、そのセルに対して AI レビュアー、静的解析器、またはカスタムアダプターを実行し、証拠と指摘を記録し、必要なカバレッジが完了した場合にのみ完了できます。

レビュアーは問題を見つけます。Review Gauntlet は、どのファイルがどのルールで確認されたかを証明します。

## クイックスタート

リポジトリをレビューする最短手順:

Review Gauntlet は単体のレビュアーではありません。開始前に、opencode などの外部レビューエージェント CLI をインストール・認証し、そのエージェントに対応する Review Gauntlet スキルまたはプロンプトガイダンスを導入し、Review Gauntlet がそれを呼び出す方法を示すアダプター設定を作成してください。

```bash
# 1. CLI をインストール（すでにインストール済みならスキップ）
uv tool install review-gauntlet

# 2. 外部レビューエージェントを別途インストール・設定し、アダプター設定を作成
uvx review-gauntlet config init --preset opencode

# 3. 現在のリポジトリでレビューセッションを開始
review-gauntlet init

# 4. 設定済みエージェントでセッション完了まで ready タスクを実行
review-gauntlet run

# 5. 最終チェックポイントと指摘を確認
review-gauntlet status
review-gauntlet findings
```

`run` は設定済みの外部エージェントを使い、ready タスクを繰り返し実行し、アクティブセッションが finalize されると停止します。`review` は低レベルまたはカスタムワークフロー向けに 1 回の呼び出しで 1 バッチだけ進めます。`verify-fixes` は `fixed_pending_verification` とマークされた指摘を再確認し、`fixed_verified` または `reopened` に移動します。`finalize` は、必要なカバレッジが完了し、live findings が閉じられ、`status` が `can_finalize: true` を返した場合にのみ成功します。

## AI レビューツールとの違い

AI レビューツールは通常、diff からコメントを生成します。Review Gauntlet はその一段手前から始めます。レビュー計画を作成し、ファイルとレビュールールを掛け合わせてカバレッジ直交表を構築し、必要なセルに対してレビュアーを実行し、完了したレビュー義務ごとに証拠を記録します。

| ツール種別 | 主な役割 |
|---|---|
| Codex Review / Open Code Review / opencode | レビューコメントを生成する |
| 静的解析器 | 既知のルール違反を検出する |
| Review Gauntlet | レビューを計画し、ファイル × ルール直交表を作成し、カバレッジを追跡し、証拠を保存し、完了をゲートする |

Review Gauntlet はレビュアーと連携するためのものであり、競合するものではありません。

## 仕組み

Review Gauntlet はコードレビューを計画優先かつ監査可能にします。

1. レビュー対象を定義する
   - ファイル、ディレクトリ、diff、コミット、その他のレビュー対象
2. レビュールールを定義する
   - セキュリティ、正しさ、保守性、アーキテクチャ、プロジェクト固有チェック、カスタムルール
3. レビュー直交表を作成する
   - 各ファイル × ルールの組み合わせがレビューセルになる
4. レビュアーを実行する
   - AI レビュアー、静的解析器、opencode、Codex スタイルのエージェント、またはカスタムアダプターが割り当てセルを検査する
5. 証拠と指摘を追跡する
   - プロンプト、出力、指摘、カバレッジ状態、未解決の問題を記録する
6. 完了条件を満たした場合のみ finalize する
   - 必要なカバレッジが完了し、live findings が閉じられた場合のみ完了する

## レビュー実行前の準備

レビューセッションは CLI だけでは動作しません。事前に必要なものをすべてインストールしてください。

1. `review-gauntlet` CLI をインストールする
2. 外部レビューエージェント CLI をインストール・設定する
3. そのエージェントに対応する Review Gauntlet スキルまたはプロンプトガイダンスをインストールする
4. `review-gauntlet.jsonc` などの発見可能なアダプター設定を追加する

### CLI のインストール

```bash
uv tool install review-gauntlet
```

### スキルのインストール

Review Gauntlet エージェントスキルをインストールします。

```bash
npx skills add tumf/review-gauntlet
```

### アダプター設定の作成

Review Gauntlet は `.review-gauntlet/config.jsonc`、`review-gauntlet.jsonc`、または XDG ユーザー設定ディレクトリから設定を自動検出します。スタータープリセットはインストール済みパッケージに同梱されているため、初回利用者でも追加の準備なしで設定を作成できます。

プロジェクト設定を作成します。

```bash
review-gauntlet config init --preset opencode
```

グローバル既定設定を作成する場合:

```bash
review-gauntlet config init --global --preset opencode
```

利用可能なプリセットを確認し、有効設定を検証します。

```bash
review-gauntlet config preset list
review-gauntlet config preset show opencode
review-gauntlet config validate
review-gauntlet config effective --format json
```

既存の生成済み設定を上書きするには `--force`、作成せずに書き込み先とプリセット内容を確認するには `--dry-run`、任意パスへ書き込むには `--output <path>` を使います。エージェントのコマンドや引数が異なる場合は生成された JSONC を編集し、`review-gauntlet review` が end-to-end で動作することを確認してください。

---

```bash
uvx review-gauntlet config init --preset opencode
# （対応する外部レビューエージェントは別途インストール・認証）
review-gauntlet init
review-gauntlet run
review-gauntlet status
```

`uvx review-gauntlet config init --preset opencode` は、パッケージから直接実行できるスターターフローです。通常利用では `uv tool install review-gauntlet` で CLI をインストールし、同じコマンドを `review-gauntlet` として使えるようにしてください。

## インストール

通常利用では CLI を `review-gauntlet` としてインストールします。

```bash
uv tool install review-gauntlet
review-gauntlet --help
```

## ソースからのインストール

最新の GitHub 版を使う場合やコントリビュートする場合に使います。

```bash
git clone https://github.com/tumf/review-gauntlet.git
cd review-gauntlet
uv sync
make install
review-gauntlet --help
```

`make install` は `uv tool install --reinstall .` により、ローカルパッケージを正式な `review-gauntlet` コマンドとしてインストールします。

## 基本的な使い方

明示的なレビュー対象を選び、`run` で設定済みの外部エージェント経由で ready タスクをセッション完了まで実行します。

```bash
# ブランチまたは範囲をレビュー
review-gauntlet init --from main --to HEAD

# リポジトリ全体をレビュー
review-gauntlet init --all

# 推奨: アクティブセッションが finalize されるまで ready タスクを実行
review-gauntlet run

# デバッグや監査結果の確認
review-gauntlet status
review-gauntlet findings

# 誤った init を破棄する場合。チェックポイントは作成しない
review-gauntlet cancel
```

`run` は通常の進行コマンドです。`review` の constitution に基づく動作は変わりません: `review` は 1 回の呼び出しで正確に 1 バッチだけ進め、`run` は外部エージェント経由で繰り返し ready タスクを実行します。`finalize` はクリーンアップコマンドではなくゲートです。必要なカバレッジが完了し、live findings が閉じられるまで失敗します。誤った `init` を破棄する場合だけ `cancel` を使ってください。`cancel` はセッションを `cancelled` として記録し、アクティブセッションのマーカーを削除しますが、チェックポイントは作成しません。

### 高度な `ready` の使い方

`ready` は CI システム、カスタムオーケストレーター、外部統合、デバッグ向けに次のレビュープロンプトを出力します。Review Gauntlet の外部でオーケストレーションループを所有したい場合に使います。

```bash
review-gauntlet ready | opencode run
```

カスタムオーケストレーターは `ready` を繰り返し呼び出せますが、通常のセッション進行には `review-gauntlet run` を推奨します。

## シェル補完

インストール済みの `review-gauntlet` コマンドは、一般的な対話シェル向けの補完スクリプトを生成できます。現在のセッションで評価するか、シェル起動ファイルが読み込む場所に書き込んでください。

Bash:

```bash
source <(review-gauntlet completion bash)
```

Zsh:

```zsh
review-gauntlet completion zsh > "${fpath[1]}/_review-gauntlet"
autoload -Uz compinit && compinit
```

Fish:

```fish
review-gauntlet completion fish > ~/.config/fish/completions/review-gauntlet.fish
```

## コマンド

対象選択は `init` で行い、`review` はアクティブなセッションを 1 回だけ進めます。裸の `init` は、完全で利用可能なチェックポイントがある場合 `.review-gauntlet/checkpoints/latest/status.json` を使い、その `review_base_commit` から `HEAD` までをレビューします。チェックポイントがない場合、裸の `init` は対象となる全ファイルをレビューします。

OCR 互換の対象マッピング:

```bash
# 既定レビュー: 最新 finalize 済みチェックポイント -> HEAD、初回は全ファイル
review-gauntlet init

# OCR ブランチ/範囲レビュー: 2 つの ref 間で変更されたファイル
review-gauntlet init --from main --to HEAD

# OCR 単一コミットレビュー: 1 コミットで変更されたファイル
review-gauntlet init --commit <commit-oid>

# review-gauntlet 専用の全リポジトリレビュー: 対象となる inventory ファイルすべて
review-gauntlet init --all

# 推奨: 設定済みの外部エージェントで ready タスクをオーケストレーション
review-gauntlet run

# 低レベル/カスタムワークフロー向けにレビューを 1 ステップだけ実行
review-gauntlet review

# 最大 20 セルを選択し、最大 4 アダプター呼び出しを同時実行
review-gauntlet review --budget 20 --concurrency 4
```

`run` またはレビュー手順の後は、セッション状態と指摘を確認し、必要に応じて人間の判断を記録し、カバレッジと指摘が両方閉じられた場合のみ finalize します。

```bash
review-gauntlet status
review-gauntlet findings
review-gauntlet mark <finding-id> fixed --reason "fixed in follow-up"
review-gauntlet verify-fixes
review-gauntlet finalize
# Finalize は Git レビュー可能な JSON/Markdown スナップショットを atomic に書き込む
git add .review-gauntlet/checkpoints/latest

# init 対象を間違えた場合は finalize ではなく cancel する
review-gauntlet cancel
```

`cancel` は、誤って初期化したアクティブセッションを破棄するための正式なコマンドです。ledger に `sessions.state = 'cancelled'` を記録し、`.review-gauntlet/active-session.json` を削除するため、その後の `status`、`review`、`ready` は新しい `init` まで no-active-session として失敗します。`finalize` と異なり、チェックポイントは書かず、レビュー完了も主張しません。

`status` は `coverage` をレビューセル状態ごとの件数として報告します。

| カバレッジ状態 | 意味 |
|---|---|
| `pending` | ファイル × ルールのセルがまだレビューを必要としている。 |
| `reviewed` | セルが現在のファイル digest に対してレビュー済み。 |
| `stale` | レビュー後にファイルが変更されたため、セルを再レビューする必要がある。 |
| `superseded` | 古い永続化セルが現在の対象計画に含まれなくなった。 |

`findings` は既定で open findings を報告します。terminal findings も含めるには `--all` を渡します。各 finding 行には次が含まれます。

| フィールド | 意味 |
|---|---|
| `finding_id` | `RGF-...` のような安定した Review Gauntlet finding ID。 |
| `fingerprint` | リポジトリ、対象、パス、ルール、主張、コードアンカー、ルールセットから導出される重複排除キー。 |
| `state` | Finding のライフサイクル状態。Open 状態は `untriaged`、`confirmed`、`fixed_pending_verification`、`reopened`。Terminal 状態は `fixed_verified`、`false_positive`、`waived`、`accepted_risk`。 |
| `path` | 最新 occurrence のリポジトリ相対ファイルパス。 |
| `rule_id` | Finding を生成したレビュールール。 |
| `content` | レビュアーが提供した finding テキスト。 |
| `metadata` | owner や expiration など、人間の判断で記録された JSON メタデータ。 |
| `start_line` / `end_line` | 最新の行範囲。正確な範囲がない場合は `0`。 |
| `imprecise` | 最新位置が概算かどうか。 |

`finalize` が成功するには、カバレッジと live findings が閉じられ、レビュー対象 universe のファイルが `HEAD` と一致している必要があります。dirty な tracked、staged、unstaged、または対象となる untracked ファイルがあるとチェックポイント作成はブロックされます。`status.json`、`findings.json`、`events.json`、`summary.md` を `.review-gauntlet/checkpoints/<checkpoint_id>/` のような生成済みチェックポイントディレクトリへ書き込み、`.review-gauntlet/checkpoints/latest` をそのチェックポイントへのポインターとして更新し、アクティブセッションをクリアします。次のコマンドは `review-gauntlet init` になります。独立した checkpoint コマンドは意図的にありません。

`review --concurrency` の既定値は `3` で、正の整数である必要があります。`--budget` は 1 回のレビュー実行で選択される合計セル数を引き続き制限します。`--concurrency` は、その中で同時に実行されるアダプター呼び出し数だけを制限します。ネストされた外部アダプターコマンドへ concurrency フラグを自動的に渡すものではありません。

### 診断およびレガシー計画コマンド

`inventory`、`plan`、`report` コマンドは互換性と検査のために引き続き利用できます。ファイル検出、レビュー分割、レポート描画を確認するために使います。通常の日常レビューライフサイクルではありません。

現在のリポジトリ inventory と分類を確認します。

```bash
review-gauntlet inventory
```

slice と required checks を含むレガシーレビュー計画を確認します。

```bash
review-gauntlet plan
```

レガシー Markdown 行列レポートを描画します。

```bash
review-gauntlet report
```

## 既定のファイルフィルタリング

Inventory 検出は Git の挙動を維持します。Git 管理リポジトリでは引き続き `git ls-files --cached --others --exclude-standard` を既存の bounded subprocess timeout 付きで使うため、`.gitignore` などの exclude-standard ルールが review-gauntlet の組み込みフィルターより前に適用されます。

組み込み artifact フィルターは、生成物や依存パスを full inventory と target-scoped inventory の両方から除外します。これには `.review-gauntlet/`、`__pycache__/`、`.ruff_cache/`、`build/`、`dist/`、`wheels/`、`htmlcov/` などの Python/editor/cache 出力、および `vendor/`、`node_modules/`、`target/`、`.happypack/`、`.cachefile/`、`_packages/`、`rpm/`、`pkgs/`、`oh_modules/` などの OCR 由来の依存・ビルド staging パスが含まれます。

レビューセッションは、セルと digest の作成時に追加の既定 review-path フィルターを適用します。ファイルは一般 inventory では分類可能なままですが、`init` は既定で `openspec/`、`tests/`、`docs/` を除外します。また、`__tests__/`、`*_test.go`、`*Test.java`、`*Test.kt`、`*.spec.ts`、`*.test.tsx`、`test_*.py`、`*_spec.rb`、`*.spec.ets`、`*.test.ets` などの一般的な OCR スタイルのテストまたは生成パスも除外します。レビューセルと target digest は、`uv.lock`、`poetry.lock`、`requirements*.txt`、`package.json`、`package-lock.json`、`yarn.lock`、`pnpm-lock.yaml`、`Cargo.toml`、`Cargo.lock`、`go.mod`、`go.sum`、`pom.xml`、`Gemfile.lock`、`composer.lock`、`Package.resolved`、`pubspec.lock`、`mix.lock`、`vcpkg.json`、`flake.lock`、`stack.yaml.lock`、`Manifest.toml`、`renv.lock` などの一般的な package manifest と lock file も除外します。これらの package ファイルは、別の artifact または Git ignore ルールで除外されない限り、一般 inventory からは削除されません。通常のソースファイル、および `setup.py`、`build.gradle`、`mix.exs`、`build.zig` のような package 隣接の実行可能ロジックファイルは、レビューセルの対象として残ります。

`review` は設定を次の順序で検出します: 明示的な `--config`、`.review-gauntlet/config.jsonc`、`.review-gauntlet/config.json`、`review-gauntlet.jsonc`、`review-gauntlet.json`、`$XDG_CONFIG_HOME/review-gauntlet/config.jsonc`、最後に `$XDG_CONFIG_HOME/review-gauntlet/config.json`。`XDG_CONFIG_HOME` が未設定または空の場合、グローバル fallback base は `~/.config` であるため、JSONC fallback パスは `~/.config/review-gauntlet/config.jsonc` です。リポジトリローカル設定は常にグローバル XDG 設定より優先され、検出は既存ファイルを読むだけです。グローバル設定ディレクトリやファイルを作成することはありません。コマンドアダプターは argv 配列を使い、shell string は使いません。provider login、model choice、secret は外部 CLI 設定内に留まります。

opencode file-json verdicts 向けの最小 JSONC 設定:

```jsonc
{
  "adapter": {
    "type": "command",
    "command": "opencode",
    "args": ["run", "{prompt}"],
    "output": {"mode": "file-json", "path": "{output_file}"}
  }
}
```

生成された OCR プロンプトは `{prompt}` として 1 つの argv 要素に展開されます。プロンプト artifact は監査証拠として引き続き書き込まれますが、prompt-file transport はコマンドアダプター契約の一部ではありません。`cwd`、`env`、`timeout_seconds`、`quiet_timeout_seconds` は任意の escape hatch です。`cwd` を省略すると呼び出し元の現在の作業ディレクトリを継承し、`env` を省略すると固定の自動変数なしで親環境を継承し、明示的な `env` 値は継承環境を上書きします。`timeout_seconds` を省略すると総実行時間の既定は 3600 秒 / 60 分です。`quiet_timeout_seconds` を省略すると stdout/stderr が出力されない時間の既定は 600 秒 / 10 分です。stdout と stderr のどちらの出力でも quiet timeout はリセットされます。TUI がしきい値前にエージェントを quiet と表示することはありますが、quiet 表示は失敗ではなく実行中/alive の状態です。

設定済みエージェントコマンドに環境変数を渡したい場合は `adapter.env` を使います。モデル選択、feature flag、wrapper 固有のパスなど、Review Gauntlet 設定と一緒に管理したい値に利用できます。

```jsonc
{
  "adapter": {
    "type": "command",
    "command": "opencode",
    "args": ["run", "{prompt}"],
    "env": {
      "OPENCODE_MODEL": "anthropic/claude-sonnet-4",
      "REVIEW_GAUNTLET_REPO": "{repo_root}",
      "REVIEW_GAUNTLET_STATE": "{state_dir}"
    }
  }
}
```

環境変数の値は、アダプター引数と同じテンプレート構文で展開されます。親プロセスの環境に追加されるため、継承された変数を上書きすることもできます。provider credential は project config にコミットせず、外部 CLI や secret manager 側に置いてください。

Verdict は OCR スタイルコメントを含む JSON である必要があります。

```json
{"comments":[{"path":"src/app.py","content":"Issue","start_line":1,"end_line":1}]}
```

対応するテンプレート変数には `{repo_root}`、`{state_dir}`、`{run_id}`、`{run_dir}`、`{cell_id}`、`{cell_dir}`、`{prompt}`、`{output_file}`、`{file_path}`、`{rule_id}` があります。

## 開発者ワークフロー

```bash
uv sync
make check
make format
make lint
make typecheck
make test
make coverage
```

## 設計

Review Gauntlet はレビューを stateful なカバレッジワークフローとして扱います。

- 明示的な対象集合からセッションを初期化する
- 対象ファイルをレビュー slice とカバレッジセルへ分類する
- 外部コマンドアダプター経由でレビューを正確に 1 ステップずつ実行する
- プロンプト、出力、指摘、カバレッジ状態を監査証拠として記録する
- 必要なカバレッジと live findings が閉じられた場合のみ finalize する

外部レビューツールは、ハードコードされた runner ではなくコマンドアダプターを通じて統合されます。アダプターは argv 配列を受け取り、レビュー artifact を安全なテンプレート変数に展開し、stdout またはファイルに書き込まれる JSON verdicts をサポートします。これにより、opencode、Codex スタイルのツール、静的解析器、カスタム wrapper などの CLI が、review-gauntlet に provider login や secret 管理を所有させることなく参加できます。
