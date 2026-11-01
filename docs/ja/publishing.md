[English](../en/publishing.md) | [日本語](publishing.md)

# リリースガイド

このページでは、RenderEyeMCPのリリースのビルド、検証、公開方法について説明します。

- [対応プラットフォーム](#対応プラットフォーム)
- [アーカイブの命名規則](#アーカイブの命名規則)
- [リリースワークフローの仕組み](#リリースワークフローの仕組み)
- [公開前の検証（ドライラン）](#公開前の検証ドライラン)
- [リリースの公開](#リリースの公開)
- [ポータブルインストール](#ポータブルインストール)
- [拡張機能のセットアップ](#拡張機能のセットアップ)
- [トラブルシューティング](#トラブルシューティング)

## 対応プラットフォーム

| プラットフォーム | アーカイブ | Goバイナリ | インストーラー |
|------------------|-----------|------------|----------------|
| Windows x64 | `.zip` | `rendereye-mcp.exe` | `install.ps1` |
| Linux x64 | `.tar.gz` | `rendereye-mcp` | `install.sh` |

RenderDocはWindowsとLinuxで動作します。
macOSはRenderDocのリリースが存在しないため、サポート対象外です。

## アーカイブの命名規則

```text
RenderEyeMCP-v1.0.0-windows-amd64.zip
RenderEyeMCP-v1.0.0-linux-amd64.tar.gz
checksums.txt
```

バージョンはgitタグから取得されます（例: `v1.0.0` → `1.0.0`）。
`v1.1.0-beta.1` のようなハイフン付きのタグはGitHub上でプレリリースとして扱われます。

## リリースワークフローの仕組み

`.github/workflows/release.yml` のワークフローは4つのジョブで構成されています。

| ジョブ | 内容 |
|--------|------|
| `test` | `go test ./...` と `go vet ./...` を実行 |
| `build` | バイナリのビルド、アーカイブの組み立て、内容の検証、チェックサムの生成 |
| `checksums` | 各プラットフォームの `.sha256` ファイルをまとめて `checksums.txt` を生成 |
| `publish` | GitHubリリースを作成してすべてのアーカイブをアップロード — **タグプッシュ時のみ** |

手動の `workflow_dispatch` 実行では `publish` ジョブはスキップされます。
アーカイブはワークフローアーティファクトとしてアップロードされるため、ダウンロードして確認できます。

## 公開前の検証（ドライラン）

GitHubリリースを作成せずにビルドとパッケージングのパイプライン全体をテストするには:

1. GitHubの **Actions → Release** を開きます。
2. **Run workflow** をクリックします。
3. テストするブランチを選択します。
4. **Run workflow** をクリックします。

`publish` 以外のすべてのジョブが実行されます。
完了したランの **Artifacts** セクションからアーカイブをダウンロードしてローカルで確認できます。

```bash
# Linuxアーカイブの内容確認
tar -tzf RenderEyeMCP-dev-*-linux-amd64.tar.gz
```

```powershell
# Windowsアーカイブの内容確認
Expand-Archive RenderEyeMCP-dev-*-windows-amd64.zip -DestinationPath test-extract\
Get-ChildItem test-extract\ -Recurse
```

## リリースの公開

1. `extensions/rendereye/extension.json` に正しいバージョンが記載されていることを確認します。

2. タグを作成してプッシュします。

   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

3. `Release` ワークフローが自動的にトリガーされます。**Actions** タブで進捗を確認します。

4. ワークフローが完了すると、GitHubリリースが以下のアーカイブとともに公開されます。
   - `RenderEyeMCP-v1.0.0-windows-amd64.zip`
   - `RenderEyeMCP-v1.0.0-linux-amd64.tar.gz`
   - `checksums.txt`

プレリリースを公開するには、`v1.1.0-rc.1` のようにハイフン区切りの識別子を含むタグを使います。
リリースは自動的にプレリリースとしてフラグが立てられます。

## ポータブルインストール

各アーカイブは自己完結型で、展開したディレクトリからインストールします。
バイナリはシステムのパスにコピーされません。ユーザーは展開先の
`rendereye-mcp.exe`（または `rendereye-mcp`）を直接参照するようにコーディングエージェントを設定します。

**Windowsアーカイブの構成:**

```text
RenderEyeMCP-v1.0.0-windows-amd64/
├── rendereye-mcp.exe
├── install.ps1          ← このディレクトリから実行
├── extensions/          ← %APPDATA%\qrenderdoc\extensions\rendereye\ にインストール
│   ├── __init__.py
│   ├── extension.json
│   └── ...
├── README.md
└── LICENSE
```

**Linuxアーカイブの構成:**

```text
RenderEyeMCP-v1.0.0-linux-amd64/
├── rendereye-mcp
├── install.sh           ← このディレクトリから実行
├── extension/           ← ~/.local/share/qrenderdoc/extensions/rendereye/ にインストール
│   ├── __init__.py
│   ├── extension.json
│   └── ...
├── README.md
└── LICENSE
```

どちらのインストーラーも、アーカイブを完全に展開してから実行する必要があります。
別のディレクトリから `install.ps1` や `install.sh` を実行しないでください。

エンドユーザー向けの手順は[インストール](installation.md)を参照してください。

## 拡張機能のセットアップ

RenderDoc Python Extension（`extensions/rendereye/`）はすべてのアーカイブに含まれています。
インストーラースクリプトを実行することで、RenderDocのユーザー拡張機能ディレクトリにインストールされます。

拡張機能はPythonで書かれており、RenderDoc組み込みのPythonインタープリターを使用します。
エンドユーザーが別途Pythonをインストールする必要はありません。

インストール後、RenderDocで一度有効化する必要があります:
**Tools → Manage Extensions → RenderEyeMCP → Always Load**

## トラブルシューティング

**`go: toolchain constraint` でビルドが失敗する**

`go.mod` に最小Goバージョンが指定されています。ランナーのGoバージョンがその要件を
満たしていることを確認してください。ワークフローは `go-version-file: go.mod` を使って
適切なバージョンを自動的に選択します。

**アーカイブに `extensions/__init__.py` や `extension/extension.json` がない**

リポジトリルートの `extensions/rendereye/` が存在し、必要なファイルが含まれていることを
確認してください。ワークフローはアセンブル時にこのディレクトリをアーカイブにコピーします。

**チェックサムの検証に失敗する**

チェックサムファイルはビルドランナー上で生成されたアーカイブのファイル名を使用します。
ファイル名を変更せず、元の名前で検証してください。

**リリースがすでに存在する**

`publish` ジョブはタグに対応するリリースが存在しないことを確認してから作成します。
再公開するには、GitHubの既存のリリースを削除してからワークフローを再実行してください。
