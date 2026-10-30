[English](../en/installation.md) | [日本語](installation.md)

# RenderEyeMCPのインストール

このページでは、`rendereye-mcp`バイナリ、RenderDoc拡張機能、設定ファイルを
インストールします。コーディングエージェントの接続は[設定](configuration.md)を
参照してください。

- [インストールされるもの](#インストールされるもの)
- [前提条件](#前提条件)
- [Windowsへのインストール](#windowsへのインストール)
- [Linuxへのインストール](#linuxへのインストール)
- [RenderDoc拡張機能を有効にする](#renderdoc拡張機能を有効にする)
- [インストールの確認](#インストールの確認)
- [アップデート](#アップデート)
- [アンインストール](#アンインストール)
- [テストした内容](#テストした内容)

## インストールされるもの

| 要素 | 場所 |
|------|------|
| `rendereye-mcp.exe`(MCPブリッジ + IPCサービス) | Windows: `%LOCALAPPDATA%\RenderEyeMCP\`<br>Linux: `~/.local/bin/` |
| RenderDoc拡張機能`rendereye/` | 自動検出したRenderDocプラグインフォルダー |
| 設定ファイル`.env` | 実行ファイルと同じフォルダー |

RenderDoc本体のフォルダーには何もインストールしません。RenderDoc自体も同梱していません。

## 前提条件

- **RenderDoc 1.46**以上がインストールされていること。拡張機能の最小バージョンは1.46です。
- MCP対応のコーディングエージェント: **Claude Code**または**Codex**。
- Python、pip、uv、Goツールチェーンは不要です。

## Windowsへのインストール

### ステップ1 — リリースアーカイブをダウンロード

[GitHubリリース](https://github.com/taqu/RenderEyeMCP/releases)ページから
`rendereye-mcp_<version>_windows_amd64.zip`をダウンロードして展開します。

### ステップ2 — インストーラーを実行

展開したフォルダーでPowerShellを開き、次を実行します。

```powershell
.\install.ps1
```

インストーラーは次の処理を行います。

1. `rendereye-mcp.exe`を`%LOCALAPPDATA%\RenderEyeMCP\`にコピーします。
2. RenderDocプラグインフォルダーを自動検出し、`extension/`のファイルをコピーします。
3. `%LOCALAPPDATA%\RenderEyeMCP\`にデフォルトの`.env`を作成します(再実行時は上書き
   しません)。
4. エージェントの設定に使うMCP設定スニペットを表示します。

**RenderDocが検出されない場合:** パスを直接指定します。

```powershell
.\install.ps1 -RenderDocExtDir "C:\Program Files\RenderDoc\plugins"
```

**アップデート:** 既存バイナリを上書きするには`-Force`を付けます。

```powershell
.\install.ps1 -Force
```

**手動インストール**(インストーラーを使わない場合):

```powershell
$dest = "$env:LOCALAPPDATA\RenderEyeMCP"
New-Item -ItemType Directory -Force -Path $dest
Copy-Item rendereye-mcp.exe $dest
# 拡張機能をRenderDocのextensionsフォルダーにコピー
Copy-Item -Recurse extension\ "$env:APPDATA\qrenderdoc\extensions\rendereye"
```

### ステップ3 — バイナリの動作確認

```powershell
& "$env:LOCALAPPDATA\RenderEyeMCP\rendereye-mcp.exe" version
```

`rendereye-mcp v<version> ...`のようなバージョン行が表示されれば成功です。

[RenderDoc拡張機能を有効にする](#renderdoc拡張機能を有効にする)に進みます。

## Linuxへのインストール

### ステップ1 — リリースアーカイブをダウンロード

[GitHubリリース](https://github.com/taqu/RenderEyeMCP/releases)ページから
`rendereye-mcp_<version>_linux_amd64.tar.gz`をダウンロードして展開します。

```bash
tar -xzf rendereye-mcp_<version>_linux_amd64.tar.gz
cd rendereye-mcp_<version>_linux_amd64
```

### ステップ2 — インストーラーを実行

```bash
./install.sh
```

`rendereye-mcp`を`~/.local/bin/`(または`--install-dir DIR`)にコピーし、RenderDoc
プラグインフォルダーを自動検出して拡張機能をコピーし、バイナリと同じ場所にデフォルトの
`.env`を作成します。

**RenderDocが検出されない場合:**

```bash
./install.sh --renderdoc-ext-dir ~/.local/share/renderdoc/plugins
```

**アップデート:**

```bash
./install.sh --force
```

### ステップ3 — PATHへの追加(必要な場合)

`~/.local/bin`が`$PATH`にない旨の警告が出た場合は、シェルのプロファイル(`~/.bashrc`
または`~/.zshrc`)に以下を追加します。

```bash
export PATH="$PATH:$HOME/.local/bin"
```

新しいターミナルを開いて確認します。

```bash
rendereye-mcp version
```

LinuxでのRenderDoc連携は実機検証をまだ行っていません。インストーラーは実装済みの
コードパスに従っています。

## RenderDoc拡張機能を有効にする

RenderDocはユーザー拡張機能を一度有効にするまで読み込みません。

1. RenderDocを起動します。
2. **Tools → Manage Extensions**を開きます。
3. 一覧で**RenderEyeMCP**を選び、**Always Load**を有効にします。

*Always Load*を有効にすると、すべてのRenderDocウィンドウで拡張機能が起動します。

拡張機能は`127.0.0.1:37020`のIPCサービスに接続します。IPCサービスは、コーディング
エージェントが`rendereye-mcp`を起動したときにMCPブリッジが自動で立ち上げます。
RenderDocが先に起動していても、拡張機能がバックグラウンドで再接続を試みる
(最大30秒間隔)ため、起動順は気にしなくて構いません。

## インストールの確認

順番に確認してください。

1. **バイナリが動作する**

   ```powershell
   & "$env:LOCALAPPDATA\RenderEyeMCP\rendereye-mcp.exe" version
   ```

   `rendereye-mcp v1.0.0 ...`のようなバージョン行が表示されればOKです。

2. **MCPサーバーが起動し、エージェントからToolが見える** —
   [設定 → 接続の確認](configuration.md#接続の確認)を参照してください。たとえば
   `claude mcp get rendereye`が`Connected`と表示されればOKです。

3. **RenderDocが検出される** — RenderDocを(拡張機能を有効にして)起動し、
   エージェントに頼みます。

   > RenderEyeMCPから見えるRenderDocセッションを一覧表示してください。

   `connection_state: connected`のセッションが含まれていればOKです。

4. **読み込み済みのCaptureを調査できる** — `.rdc`ファイルを開いてDrawCallを選択し、
   次のように頼みます。

   > RenderDocで開いているCaptureと、選択中のEventを教えてください。

プロセスが起動しただけでは、すべてがつながっている証拠にはなりません。拡張機能・
サービス・MCPブリッジのすべてが関わるのはステップ3からです。

## アップデート

1. 新しいリリースアーカイブをダウンロードして展開します。
2. 実行中のIPCサービスやコーディングエージェントのセッションを停止します。
3. `-Force`を付けてインストーラーを再実行します。

   ```powershell
   .\install.ps1 -Force
   ```

4. 更新した拡張機能を読み込ませるためRenderDocを再起動します。
5. コーディングエージェントを再起動します。

実行ファイルのパスが変わらなければ、エージェントの設定ファイルを変更する必要はありません。

## アンインストール

**Windows:**

```powershell
# 実行ファイルと.envを削除
Remove-Item -Recurse "$env:LOCALAPPDATA\RenderEyeMCP"

# RenderDoc拡張機能を削除(パスは環境によって異なる場合があります)
Remove-Item -Recurse "$env:APPDATA\qrenderdoc\extensions\rendereye"
```

**Linux:**

```bash
rm -f ~/.local/bin/rendereye-mcp ~/.local/bin/.env
rm -rf ~/.local/share/renderdoc/plugins/rendereye
```

## テストした内容

| 方法 | 環境 | 結果 |
|------|------|------|
| `install.ps1` | Windows 11、展開したリリースアーカイブ | 成功 |
| `install.ps1 -Force` | Windows 11、既存インストールに再実行 | 成功 |
| 手動コピー | Windows 11 | 成功 |
| `install.sh` | — | コードパスを確認済み。RenderDoc実機検証は未実施 |
| クリーンなWindowsマシン/VM | — | **未実施** |
| RenderDocを使ったLinuxでのエンドツーエンド | — | **未実施** |
