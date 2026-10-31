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
| `rendereye-mcp.exe`(MCPブリッジ + IPCサービス) | アーカイブを展開したフォルダーにそのまま残ります |
| RenderDoc拡張機能`rendereye/` | Windows: `%APPDATA%\qrenderdoc\extensions\rendereye\`<br>Linux: `~/.local/share/qrenderdoc/extensions/rendereye/` |
| 設定ファイル`.env` | アーカイブを展開したフォルダー(`rendereye-mcp.exe`と同じ場所) |

実行ファイルは別の場所にコピー**しません**。展開したフォルダーはそのまま残しておき、
コーディングエージェントのMCP設定から`rendereye-mcp.exe`を直接指定してください。
展開したフォルダーを移動・削除する場合は、エージェントの設定も更新してください。

RenderDoc本体のプログラムフォルダーには何もインストールしません。RenderDoc自体も
同梱していません。

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

1. 同じフォルダーに`rendereye-mcp.exe`があることを確認します。
2. `extension/`のファイルを`%APPDATA%\qrenderdoc\extensions\rendereye\`にコピーします。
3. 実行ファイルの隣にデフォルトの`.env`を作成します(再実行時は上書きしません)。
4. エージェントの設定に使うMCP設定スニペットを表示します。

**拡張機能フォルダーを指定する場合:** 直接指定します。

```powershell
.\install.ps1 -RenderDocExtDir "C:\カスタムパス\extensions"
```

**アップデート:** 既存の拡張機能を上書きするには`-Force`を付けます。

```powershell
.\install.ps1 -Force
```

**手動インストール**(インストーラーを使わない場合):

```powershell
$extDst = "$env:APPDATA\qrenderdoc\extensions\rendereye"
New-Item -ItemType Directory -Force -Path $extDst
Copy-Item -Recurse extension\* $extDst
```

### ステップ3 — バイナリの動作確認

```powershell
.\rendereye-mcp.exe version
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

`rendereye-mcp`が同じフォルダーにあることを確認し、拡張機能を
`~/.local/share/qrenderdoc/extensions/rendereye/`にコピーし、実行ファイルの隣に
デフォルトの`.env`を作成します。

**拡張機能フォルダーを指定する場合:**

```bash
./install.sh --renderdoc-ext-dir ~/.local/share/qrenderdoc/extensions
```

**アップデート:**

```bash
./install.sh --force
```

### ステップ3 — バイナリの動作確認

```bash
./rendereye-mcp version
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
   .\rendereye-mcp.exe version
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

1. 新しいリリースアーカイブをダウンロードしてフォルダーに展開します。
2. 実行中のIPCサービスやコーディングエージェントのセッションを停止します。
3. `-Force`を付けてインストーラーを再実行して拡張機能を更新します。

   ```powershell
   .\install.ps1 -Force
   ```

4. 別のフォルダーに展開した場合は、エージェントのMCP設定の`command`パスを更新します。
5. 更新した拡張機能を読み込ませるためRenderDocを再起動します。
6. コーディングエージェントを再起動します。

同じフォルダーに展開した場合、エージェントの設定は変更する必要がありません。

## アンインストール

**Windows:**

1. RenderEyeMCPを使っているコーディングエージェントを停止し、IPCサービスが終了するのを
   待ちます。
2. エージェントのMCP設定からRenderEyeMCPのエントリを削除します。
3. RenderDoc拡張機能を削除します。

   ```powershell
   Remove-Item -Recurse "$env:APPDATA\qrenderdoc\extensions\rendereye"
   ```

4. 展開したRenderEyeMCPフォルダー(`rendereye-mcp.exe`と`.env`が入っているフォルダー)を
   削除します。

**Linux:**

1. RenderDoc拡張機能を削除します。

   ```bash
   rm -rf ~/.local/share/qrenderdoc/extensions/rendereye
   ```

2. 展開したRenderEyeMCPフォルダーを削除します。

## テストした内容

| 方法 | 環境 | 結果 |
|------|------|------|
| `install.ps1` | Windows 11、展開したリリースアーカイブ | 成功 |
| `install.ps1 -Force` | Windows 11、既存インストールに再実行 | 成功 |
| 手動コピー | Windows 11 | 成功 |
| `install.sh` | — | コードパスを確認済み。RenderDoc実機検証は未実施 |
| クリーンなWindowsマシン/VM | — | **未実施** |
| RenderDocを使ったLinuxでのエンドツーエンド | — | **未実施** |
