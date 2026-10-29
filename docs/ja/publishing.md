[English](../en/publishing.md) | [日本語](publishing.md)

# PyPI 公開ガイド

このドキュメントでは、GitHub Actions と PyPI Trusted Publishing (OIDC) を使用して
RenderEyeMCP を PyPI および TestPyPI に公開する方法を説明します。

## 概要

RenderEyeMCP は長期間有効な API トークンの代わりに **PyPI Trusted Publishing**
(OpenID Connect) を使用します。`PYPI_API_TOKEN` や `TEST_PYPI_API_TOKEN` などの
シークレットはリポジトリに保存しません。認証は、設定された GitHub Environment 内で
ワークフローが実行される際に GitHub Actions OIDC を通じて自動的に行われます。

2 つの独立したワークフローが、2 つの独立した公開先を処理します:

| ワークフローファイル | 公開先 | タグ形式 | バージョン | 用途 |
|---|---|---|---|---|
| `publish-pypi.yml` | PyPI | `v1.0.0` | `1.0.0` | 正式リリース |
| `publish-testpypi.yml` | TestPyPI | `v1.0.0-test.1` | `1.0.0.dev1` | リリース前検証 |

各ワークフローファイルは、ファイルレベルで公開先が固定されています。実行時に PyPI と
TestPyPI を切り替える共有ワークフローは存在しません。

---

## タグ命名規則

### 本番タグ

```
vMAJOR.MINOR.PATCH
```

例: `v0.1.0`、`v1.0.0`、`v1.2.3`

これらのタグは `publish-pypi.yml` を起動します。パッケージバージョンは先頭の `v` を
除いたタグです。ソースファイル (`pyproject.toml`、`__init__.py`、`extension.json`) の
バージョンは、タグをプッシュする前にタグと一致している必要があります。

### テストタグ

```
vMAJOR.MINOR.PATCH-test.N
```

例: `v0.1.0-test.1`、`v0.1.0-test.2`、`v1.0.0-test.1`

`N` は正の整数 (`>= 1`) でなければなりません。これらのタグは `publish-testpypi.yml` を
起動します。パッケージバージョンは PEP 440 の開発バージョンに正規化されます:

| Git タグ | パッケージバージョン |
|---|---|
| `v0.1.0-test.1` | `0.1.0.dev1` |
| `v0.1.0-test.2` | `0.1.0.dev2` |
| `v1.0.0-test.3` | `1.0.0.dev3` |

各テストイテレーションには一意の `N` が必要です — TestPyPI は同じバージョンの
再アップロードを許可しません。

### 無効なタグ

以下のタグ形式は**拒否**されます — 公開は行われません:

| タグ | 理由 |
|---|---|
| `v0.1` | パッチセグメントがない |
| `v0.1.0-test` | 番号なしのテストサフィックス |
| `v0.1.0-test.0` | テストイテレーションは 1 以上が必要 |
| `v0.1.0-test.foo` | 数値以外のイテレーション |
| `v0.1.0-debug` | 不明なサフィックス |
| `release-0.1.0` | 間違ったプレフィックス |

---

## ワークフロー: `publish-testpypi.yml`

ワークフローファイルは `.github/workflows/publish-testpypi.yml` です。

### トリガー

`v*-test.*` に一致するタグへのプッシュ。

### ジョブ構造

```
タグプッシュ (v*-test.*)
    |
    classify ── タグがテストリリースであることを検証し、それ以外を拒否
    |              出力: version=x.y.z.devN
    |
    build ── チェックアウト、バージョン x.y.z.devN を注入、uv build、twine check、スモークテスト
    |
    publish-testpypi → environment: testpypi → https://test.pypi.org/legacy/
```

### 主要な特性

- `id-token: write` は `publish-testpypi` **のみ**に付与されます。`classify` と
  `build` ジョブは OIDC 権限を受け取りません。
- `classify` ジョブはテストタグ以外のすべてのタグを拒否します。誤ってプッシュされた
  本番タグは TestPyPI アップロードを起動できません。
- `publish-testpypi` ジョブは OIDC 認証情報を要求する前にバージョンに `.dev` が
  含まれていることを確認する明示的なガードステップを持っています。
- 同じタグの重複アップロードを防ぐために `concurrency` を使用します。

---

## ワークフロー: `publish-pypi.yml`

ワークフローファイルは `.github/workflows/publish-pypi.yml` です。

### トリガー

`v*` に一致するタグへのプッシュ。

### ジョブ構造

```
タグプッシュ (v*)
    |
    classify ── タグが本番リリースであることを検証し、それ以外を拒否
    |              出力: version=x.y.z
    |
    build ── チェックアウト、ソースバージョンがタグと一致するか検証、uv build、twine check、スモークテスト
    |
    publish-pypi → environment: pypi → https://pypi.org/
```

### 主要な特性

- `id-token: write` は `publish-pypi` **のみ**に付与されます。`classify` と
  `build` ジョブは OIDC 権限を受け取りません。
- `classify` ジョブは本番タグ以外のすべてのタグを拒否します。テストタグ (`v*-test.*`)
  やその他のサフィックス付きタグはビルドや公開に進むことができません。
- `publish-pypi` ジョブは OIDC 認証情報を要求する前にバージョンにプレリリースセグメントが
  含まれていないことを確認する明示的なガードステップを持っています。
- 同じタグの重複アップロードを防ぐために `concurrency` を使用します。

---

## Trusted Publishing の設定

公開が成功するには、各インデックスで Trusted Publisher を登録する必要があります。
2 つのワークフローは**独立した** Trusted Publisher 登録を使用します。

### 必要なアカウント

- `rendereye-mcp` プロジェクトへのオーナーまたはメンテナーアクセスを持つ
  https://pypi.org/ の PyPI アカウント。
- https://test.pypi.org/ の TestPyPI アカウント (PyPI とは別のアカウント)。

### GitHub Environment の設定

リポジトリ設定 (**Settings → Environments**) で 2 つの GitHub Environment を作成します:

| Environment | 推奨される保護ルール |
|---|---|
| `pypi` | 手動承認を必須とする; 本番タグのブランチ/ref に制限する |
| `testpypi` | 承認不要 (またはメンテナーに自動承認) |

### Trusted Publisher の登録

**各**インデックスで Trusted Publisher を登録します。以下の正確な値を使用してください:

**TestPyPI** — https://test.pypi.org/manage/account/publishing/

| フィールド | 値 |
|---|---|
| リポジトリオーナー | `taqu` |
| リポジトリ名 | `RenderEyeMCP` |
| ワークフローファイル名 | `publish-testpypi.yml` |
| Environment 名 | `testpypi` |

**PyPI** — https://pypi.org/manage/account/publishing/

| フィールド | 値 |
|---|---|
| リポジトリオーナー | `taqu` |
| リポジトリ名 | `RenderEyeMCP` |
| ワークフローファイル名 | `publish-pypi.yml` |
| Environment 名 | `pypi` |

⚠️ ワークフローファイル名は対応する Trusted Publisher 登録と完全に一致する必要があります。
両方のワークフローファイルに同じファイル名を使用しないでください。

インデックスに `rendereye-mcp` プロジェクトがまだ存在しない場合は、上記と同じ値で
**Pending Publisher** を登録してください。最初のアップロード時にプロジェクトが
自動的に作成されます。

---

## テストリリースの公開

最初の正式リリースの前にパッケージングパイプラインを検証するためにテストリリースを
使用します。

### ステップ 1 — テストタグを作成してプッシュする

```bash
# 初回
git tag v1.0.0-test.1
git push origin v1.0.0-test.1

# 修正後に再公開する場合 (大きい N を使用)
git tag v1.0.0-test.2
git push origin v1.0.0-test.2
```

### ステップ 2 — ワークフローを監視する

リポジトリの **Actions** タブを開きます。`Publish to TestPyPI` ワークフローが実行されます:

1. `Validate Test Tag` — タグ形式を確認し、`version=1.0.0.dev1` を出力
2. `Build Distributions` — バージョン `1.0.0.dev1` を注入し、ホイールと sdist をビルドし、スモークテストを実行
3. `Publish to TestPyPI` — OIDC で認証し、TestPyPI にアップロード

### ステップ 3 — TestPyPI で確認する

公開されたパッケージは以下に表示されます:

```
https://test.pypi.org/project/rendereye-mcp/1.0.0.dev1/
```

### ステップ 4 — TestPyPI からインストールする

```bash
python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  "rendereye-mcp==1.0.0.dev1"
```

**注意**: `--extra-index-url` で PyPI を追加することで、TestPyPI にミラーされていない
依存関係を pip で解決できます。すべての期待される依存関係が正しくインストールされることを
確認してください。

### ステップ 5 — インストールされたパッケージをスモークテストする

```bash
python -c "import rendereye_mcp; print(rendereye_mcp.__version__)"
rendereye-mcp --help
```

期待される出力: バージョン `1.0.0.dev1` と MCP サーバーのヘルプテキスト。

---

## 正式リリースの公開

### 前提条件

1. `rendereye-mcp` プロジェクトが PyPI に存在するか、Pending Publisher が登録されている。
2. `pypi` GitHub Environment が適切な保護ルールで存在する。
3. `pyproject.toml`、`src/rendereye_mcp/__init__.py`、および
   `extensions/rendereye/extension.json` のバージョンがすべてリリースバージョンと一致している。
4. `main` のすべてのテストがパスしている。

### ステップ 1 — ソースのバージョンを更新する

以下の 3 つのファイルを編集して同じバージョン文字列を設定します:

- `pyproject.toml` → `version = "1.0.0"`
- `src/rendereye_mcp/__init__.py` → `__version__ = "1.0.0"`
- `extensions/rendereye/extension.json` → `"version": "1.0.0"`

`main` にコミットしてプッシュします。CI は `validate_release.py --check-versions` で
一貫性を検証します。

### ステップ 2 — 本番タグを作成してプッシュする

```bash
git tag v1.0.0
git push origin v1.0.0
```

⚠️ **PyPI は一度公開されたディストリビューションの置き換えを許可しません。**
タグをプッシュする前にバージョンを再確認してください。`rendereye_mcp-1.0.0-py3-none-any.whl`
がすでに PyPI に存在する場合、再アップロードはできません。

### ステップ 3 — リリースを承認する (必要な場合)

`pypi` GitHub Environment が手動承認を必要とする場合、アップロードが進む前に
メンテナーが Actions UI で `Publish to PyPI` ジョブを承認する必要があります。

### ステップ 4 — PyPI で確認する

```
https://pypi.org/project/rendereye-mcp/1.0.0/
```

```bash
python -m pip install "rendereye-mcp==1.0.0"
python -c "import rendereye_mcp; print(rendereye_mcp.__version__)"
```

---

## セキュリティに関する注意

- `id-token: write` は各ワークフローの公開ジョブのみに付与されます。
  `classify` と `build` ジョブは OIDC 権限を受け取りません。
- 各ワークフローは公開先がファイルレベルで固定されています — 実行時に PyPI と
  TestPyPI を選択する条件分岐はありません。
- 各公開ジョブには、公開前にバージョン形式を再確認する明示的なガードステップがあり、
  多層防御を提供します。
- 長期間有効な PyPI トークンは GitHub シークレットに保存しません。
- GitHub Environment 名と登録済みの Trusted Publisher 間の不一致は OIDC 認証の
  失敗を引き起こします — 設定ミスにより誤ったインデックスへ静かに公開されることはありません。
- 同じタグの部分的なアップロードを避けるため、concurrency は
  `cancel-in-progress: false` に設定されています。

---

## トラブルシューティング

### Trusted Publisher が設定されていない

**症状**: アップロード中の `403 Forbidden` または OIDC トークン交換の失敗。

**修正**: Trusted Publisher が正しいインデックスに、リポジトリオーナー (`taqu`)、
リポジトリ名 (`RenderEyeMCP`)、ワークフローファイル名 (TestPyPI には
`publish-testpypi.yml`、PyPI には `publish-pypi.yml`)、Environment 名
(`testpypi` または `pypi`) の正確な値で登録されていることを確認します。

### Trusted Publisher 登録のワークフローファイル名が間違っている

**症状**: Environment 名が正しいにもかかわらず OIDC 認証が失敗する。

**修正**: TestPyPI 登録には `publish-testpypi.yml` を使用する必要があります。
PyPI 登録には `publish-pypi.yml` を使用する必要があります。両方の登録に同じ
ファイル名を使用しないでください。

### 間違った Environment 名

**症状**: パブリッシャーが登録されているにもかかわらず OIDC 認証が失敗する。

**修正**: ワークフローの GitHub Environment 名 (`environment: pypi` または
`environment: testpypi`) がインデックスに登録されているものと完全に一致していることを
確認します。

### 重複するディストリビューションバージョン

**症状**: アップロード中の `400 File already exists`。

**修正**: より大きなテストイテレーション番号を使用します (例: `v1.0.0-test.1` の代わりに
`v1.0.0-test.2`)。本番では同じバージョンを再公開することはできません — パッチバージョンを
増やしてください。

### 無効なパッケージメタデータ

**症状**: ビルドジョブで `twine check` が失敗する。

**修正**: `pyproject.toml` で必須フィールド (`description`、`authors`、`license` など)
が欠けていないか確認し、バージョン文字列が PEP 440 に準拠していることを確認します。

### タグとソース間のバージョン不一致

**症状**: 本番タグに対してビルドジョブが "Version mismatch" で失敗する。

**修正**: タグをプッシュする前に `pyproject.toml`、`__init__.py`、`extension.json`
を本番タグバージョンに合わせて更新します。

### ホイールのインストール失敗

**症状**: ビルドジョブのスモークテストステップが失敗する。

**修正**: `pyproject.toml` のすべてのランタイム依存関係が PyPI で利用可能であること、
`src/rendereye_mcp/__main__.py` が `main` をエクスポートしていることを確認します。

### TestPyPI での依存関係の解決

**症状**: TestPyPI からの `pip install` が依存関係がミラーされていないため失敗する。

**修正**: 上記のように `--extra-index-url https://pypi.org/simple/` を追加します。

---

## テスト済みおよび未テストの項目

| 項目 | ステータス |
|---|---|
| タグ分類ロジック | ✅ テスト済み (ユニットテスト) |
| バージョン正規化 | ✅ テスト済み (PEP 440 バリデーション) |
| 公開先の分離 | ✅ テスト済み (本番/テスト/無効は交差不可) |
| ワークフロー YAML 構造 | ✅ テスト済み (独立したジョブ、クロス公開なし) |
| ホイールのビルドとスモークテスト | ✅ `uv build` でローカルテスト済み |
| `twine check` メタデータ検証 | ✅ ローカルでパス |
| OIDC Trusted Publisher 登録 | ⏳ 外部セットアップ待ち (PyPI + TestPyPI アカウント) |
| 実際の TestPyPI アップロード | ⏳ Trusted Publisher 登録待ち |
| 実際の PyPI アップロード | ⏳ TestPyPI 検証と明示的な承認待ち |
| TestPyPI からのインストール後検証 | ⏳ アップロード待ち |

エンドツーエンドの公開フローは、実際の TestPyPI アップロードが成功するまで
**検証されていません**。OIDC 認証はインデックスに接続せずに完全にテストすることは
できません。
