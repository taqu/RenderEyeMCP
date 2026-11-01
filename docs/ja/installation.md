[English](../en/installation.md) | [日本語](installation.md)

# RenderEyeMCPのインストール

このページでは、RenderEyeMCPのバイナリとRenderDoc拡張機能をインストールします。
コーディングエージェントの接続は[設定](configuration.md)を参照してください。

- [インストールされるもの](#インストールされるもの)
- [前提条件](#前提条件)
- [Windowsへのインストール](#windowsへのインストール)
- [Linuxへのインストール](#linuxへのインストール)
- [RenderDoc拡張機能を有効にする](#renderdoc拡張機能を有効にする)
- [インストールの確認](#インストールの確認)
- [アップデート](#アップデート)
- [アンインストール](#アンインストール)

## インストールされるもの

| 要素 | 場所 |
|------|------|
| `rendereye-mcp.exe`（MCPブリッジ＋共有IPCサービス） | アーカイブを展開した場所 |
| RenderDoc拡張機能 `rendereye` | Windows: `%APPDATA%\qrenderdoc\extensions\rendereye\`<br>Linux: `~/.local/share/qrenderdoc/extensions/rendereye/` |

RenderDoc本体のフォルダーには何もインストールしません。
RenderEyeMCPの実行にPython、pip、uvは不要です。

## 前提条件

- **RenderDoc 1.46**以上がインストールされていること。
- MCPのstdioトランスポートに対応したコーディングエージェント（Claude Code、Codex、Cursorなど）。

## Windowsへのインストール

1. [GitHub Releases](https://github.com/taqu/RenderEyeMCP/releases)ページから
   最新の `rendereye-mcp_<バージョン>_windows_amd64.zip` をダウンロードします。

2. アーカイブを恒久的なディレクトリに展開します。例:

   ```text
   C:\Tools\RenderEyeMCP\
   ```

   展開後のディレクトリ構成:

   ```text
   rendereye-mcp.exe
   install.ps1
   extensions\
   README.md
   LICENSE
   ```

3. そのディレクトリでPowerShellを開き、インストーラーを実行します:

   ```powershell
   .\install.ps1
   ```

   インストーラーがRenderDoc拡張機能を
   `%APPDATA%\qrenderdoc\extensions\rendereye\` にコピーし、
   コーディングエージェントの設定スニペットを出力します。

   既存の拡張機能インストールを上書きするには `.\install.ps1 -Force` を使います。

4. インストーラーが出力したスニペットを使ってコーディングエージェントを設定します。
   詳細は[設定](configuration.md)を参照してください。

## Linuxへのインストール

1. [GitHub Releases](https://github.com/taqu/RenderEyeMCP/releases)ページから
   最新の `rendereye-mcp_<バージョン>_linux_amd64.tar.gz` をダウンロードします。

2. アーカイブを恒久的なディレクトリに展開します:

   ```bash
   mkdir -p ~/tools/rendereye-mcp
   tar -xzf rendereye-mcp_*_linux_amd64.tar.gz -C ~/tools/rendereye-mcp --strip-components=1
   ```

3. インストーラーを実行します:

   ```bash
   cd ~/tools/rendereye-mcp
   ./install.sh
   ```

   インストーラーがRenderDoc拡張機能を
   `~/.local/share/qrenderdoc/extensions/rendereye/` にコピーし、
   コーディングエージェントの設定スニペットを出力します。

   既存のインストールを上書きするには `./install.sh --force` を使います。

4. アーカイブがパーミッションを保持していない場合は実行権限を付与します:

   ```bash
   chmod +x ~/tools/rendereye-mcp/rendereye-mcp
   ```

## RenderDoc拡張機能を有効にする

RenderDocはユーザー拡張機能を一度有効にするまで読み込みません:

1. RenderDocを起動します。
2. **Tools → Manage Extensions** を開きます。
3. リストから **RenderEyeMCP** を選択し、**Load** をクリックして **Always Load** にチェックを入れます。

*Always Load* を設定すると、UnityやUnreal Engineが開くウィンドウを含む
すべてのRenderDocウィンドウで拡張機能が起動します。

拡張機能は `127.0.0.1:37020` のRenderEyeMCP IPCサービスに接続します。
サービスはコーディングエージェントがバイナリを初めて起動したときに自動的に開始するため、
手動で起動する必要はありません。

## インストールの確認

1. **バイナリの動作確認:**

   ```powershell
   C:\Tools\RenderEyeMCP\rendereye-mcp.exe version
   ```

   バージョン番号とビルド日時が表示されます。

2. **拡張機能のインストール確認:**

   `%APPDATA%\qrenderdoc\extensions\rendereye\` に `__init__.py`、
   `extension.json` などのファイルが存在することを確認します。

3. **エージェントがツールを認識しているか** — エージェントの設定後、次のように聞きます:

   > rendereyeサーバーで使えるMCPツールを一覧表示してください。

   `get_current_capture` や `list_renderdoc_sessions` などのツールが表示されます。

4. **RenderDocに接続されているか** — 拡張機能を有効にしてRenderDocを起動し、
   キャプチャを開いてエージェントに聞きます:

   > RenderEyeMCPが認識しているRenderDocのセッションを一覧表示してください。

   `connection_state: connected` のセッションが表示されます。

## アップデート

1. 新しいリリースのアーカイブをダウンロードします。
2. 前のディレクトリの内容を置き換えるように展開します。
3. `install.ps1`（または `install.sh`）を再度実行してRenderDoc拡張機能を更新します。
4. 更新された拡張機能を読み込むためにRenderDocを再起動します。

バイナリのパスが同じであれば、エージェントの設定変更は不要です。

## アンインストール

1. RenderDoc拡張機能のディレクトリを削除します:
   - Windows: `%APPDATA%\qrenderdoc\extensions\rendereye\` を削除
   - Linux: `~/.local/share/qrenderdoc/extensions/rendereye/` を削除

2. エージェントのMCP設定ファイルから `rendereye` エントリを削除します。

3. 展開したアーカイブのディレクトリを削除します。
