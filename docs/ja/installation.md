[English](../en/installation.md) | [日本語](installation.md)

# RenderEyeMCPのインストール

このページでは、RenderEyeMCP本体、RenderDoc拡張機能、設定ファイルをインストールします。
コーディングエージェントの接続は[設定](configuration.md)を参照してください。

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

| 要素 | 場所 | 作成するもの |
|------|------|--------------|
| `rendereye-mcp`コマンド(MCPサーバー、共有サービス、セットアップツール) | Pythonのツール環境 | `uv tool install`または`pip` |
| 設定ファイル`.env` | Windows: `%LOCALAPPDATA%\RenderEyeMCP\.env`<br>Linux: `$XDG_CONFIG_HOME/rendereye_mcp/.env`(既定は`~/.config/rendereye_mcp/.env`) | `rendereye-mcp setup` |
| RenderDoc拡張機能`rendereye` | Windows: `%APPDATA%\qrenderdoc\extensions\rendereye\`<br>Linux: `$XDG_DATA_HOME/qrenderdoc/extensions/rendereye/`(既定は`~/.local/share/...`) | `rendereye-mcp setup` |
| ユーザー環境変数`RENDEREYE_ENV_FILE`(`.env`の場所) | Windows: ユーザー環境変数(レジストリ)<br>Linux: シェルのプロファイルに自分で追加 | `rendereye-mcp setup`(Windows) |

RenderDoc本体のフォルダーには何もインストールしません。RenderDoc自体も同梱していません。

## 前提条件

- **RenderDoc 1.46**がインストールされていること。拡張機能の最小バージョンは1.46です。
- **Python 3.11以上**。`uv`を使う場合はPythonを別途インストールする必要はありません。
- **[uv](https://docs.astral.sh/uv/)**(推奨)、または`python -m venv`と`pip`。
- ソースからインストールする場合のみGit。

> **リリース状況:** まだ公開リリースはありません。以下のコマンドはソースのチェックアウト
> またはwheelファイル(`rendereye_mcp-<version>-py3-none-any.whl`)を使います。
> リリースが公開されると、ZIPの`python/`フォルダーにwheelが含まれます。

## Windowsへのインストール

### 方法A — uv(推奨)

```powershell
# 必要ならuvをインストールし、新しいターミナルを開く
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# ソースのチェックアウトから
git clone https://github.com/taqu/RenderEyeMCP.git
cd RenderEyeMCP
uv tool install .

# ...またはwheelファイルから
uv tool install .\rendereye_mcp-1.0.0-py3-none-any.whl
```

インストール後に`rendereye-mcp`が見つからない場合は、`uv tool update-shell`を実行して
新しいターミナルを開いてください。次のコマンドで確認できます。

```powershell
rendereye-mcp --version
```

### 方法B — 仮想環境とpip(uvなし)

```powershell
$installDir = "$env:LOCALAPPDATA\RenderEyeMCP"
py -3.11 -m venv "$installDir\venv"      # Python 3.11以上なら何でもよく、`python`でも構いません
& "$installDir\venv\Scripts\python.exe" -m pip install .\rendereye_mcp-1.0.0-py3-none-any.whl
& "$installDir\venv\Scripts\rendereye-mcp.exe" --version
```

以降の手順では、`rendereye-mcp`を
`& "$env:LOCALAPPDATA\RenderEyeMCP\venv\Scripts\rendereye-mcp.exe"`に読み替えてください。

### setupを実行する

```powershell
rendereye-mcp setup
```

`setup`は次の4つを行います。

1. 同梱のテンプレートから`%LOCALAPPDATA%\RenderEyeMCP\.env`を作成します。**既存の
   `.env`は上書きしません**(`Existing .env preserved`と表示されます)。
2. `%ProgramFiles%\RenderDoc\qrenderdoc.exe`と
   `%ProgramFiles(x86)%\RenderDoc\qrenderdoc.exe`を探し、見つかったパスを
   `RENDEREYE_RENDERDOC_EXE`に書き込みます。すでに設定済みの値は変更しません。
3. RenderDoc拡張機能を`%APPDATA%\qrenderdoc\extensions\rendereye\`にコピーします
   (setupを再実行すると更新されます)。
4. ユーザー環境変数`RENDEREYE_ENV_FILE`を登録します。

**RenderDocを別の場所にインストールしている場合:** setupが`RenderDoc not found`と
表示したら、`.env`を編集してフルパスを設定してください。

```dotenv
RENDEREYE_RENDERDOC_EXE=D:\Tools\RenderDoc\qrenderdoc.exe
```

このパスは`server_status`/`doctor`のチェックと、任意機能の`capture_open`だけで
使われます。自分で開いたCaptureを調べるだけなら不要です。

`RENDEREYE_ENV_FILE`を反映させるため、**新しいターミナルを開き**、起動中のコーディング
エージェントやIDEも再起動してください。続いて
[RenderDoc拡張機能を有効にする](#renderdoc拡張機能を有効にする)に進みます。

## Linuxへのインストール

LinuxはRenderDocとの実機検証をまだ行っていません。以下は実装されている処理に沿った
手順です。

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh     # 必要な場合
git clone https://github.com/taqu/RenderEyeMCP.git
cd RenderEyeMCP
uv tool install .
rendereye-mcp setup
```

`setup`は`/usr/bin`、`/usr/local/bin`、`~/.local/bin`から`qrenderdoc`を探し、
拡張機能を`~/.local/share/qrenderdoc/extensions/rendereye/`にインストールして、
`export RENDEREYE_ENV_FILE=...`という行を表示します。その行をシェルのプロファイルに
追加し、新しいターミナルを開いてエージェントを再起動してください。

## RenderDoc拡張機能を有効にする

RenderDocはユーザー拡張機能を一度有効にするまで読み込みません。

1. RenderDocを起動します。
2. **Tools → Manage Extensions**を開きます。
3. 一覧で**RenderEyeMCP**を選び、**Load**をクリックして**Always Load**にチェックを
   入れます。

*Always Load*を有効にすると、UnityやUnreal Engineから開かれたウィンドウを含め、
すべてのRenderDocウィンドウで拡張機能が起動します。

拡張機能は`127.0.0.1:37020`のRenderEyeMCP共有サービスに接続します。共有サービスは、
`rendereye-mcp serve`を起動した最初のコーディングエージェントが自動で立ち上げます。
RenderDocが先に起動していても、拡張機能がバックグラウンドで再接続を試みる
(最大30秒間隔)ため、起動順は気にしなくて構いません。

## インストールの確認

順番に確認してください。各ステップは前のステップでは確認できない部分を確かめます。

1. **インストールと設定**

   ```powershell
   rendereye-mcp doctor
   ```

   Version、Executable、`.env` file、`RENDEREYE_ENV_FILE`、RenderDoc executable、
   RenderDoc extensionが`[✓]`になっていればOKです。エージェントが起動していない間は
   *Shared service*の警告が出ても正常です。

2. **MCPサーバーが起動し、エージェントからToolが見える** —
   [設定 → 接続の確認](configuration.md#接続の確認)を参照してください。たとえば
   `claude mcp get rendereye`が`Connected`と表示されればOKです。

3. **共有サービスが動いている** — エージェント起動後に:

   ```powershell
   rendereye-mcp service status
   ```

   `Service: running`と`Listening: 127.0.0.1:37020`が表示されればOKです。

4. **RenderDocが検出される** — RenderDocを(拡張機能を有効にして)起動し、
   エージェントに頼みます。

   > RenderEyeMCPから見えるRenderDocセッションを一覧表示してください。

   `connection_state: connected`のセッションが含まれていればOKです。

5. **読み込み済みのCaptureを調査できる** — `.rdc`ファイルを開いてDrawCallを選択し、
   次のように頼みます。

   > RenderDocで開いているCaptureと、選択中のEventを教えてください。

プロセスが起動しただけでは、すべてがつながっている証拠にはなりません。拡張機能・
サービス・MCPサーバーのすべてが関わるのはステップ4からです。

## アップデート

```powershell
cd RenderEyeMCP; git pull; uv tool install --force .   # ソースのチェックアウト
uv tool install --force .\rendereye_mcp-<new>-py3-none-any.whl   # wheel
rendereye-mcp service stop     # 共有サービスを新しいバージョンで再起動させる
rendereye-mcp setup            # RenderDoc拡張機能を更新(.envはそのまま)
```

更新した拡張機能を読み込ませるためRenderDocを再起動し、コーディングエージェントも
再起動してください。実行ファイルのパスが変わらなければ、エージェントの設定ファイルを
変更する必要はありません。

## アンインストール

```powershell
rendereye-mcp setup-agent claude-code --remove   # 設定したエージェントごとに実行
rendereye-mcp service stop
rendereye-mcp uninstall-setup                    # 拡張機能とRENDEREYE_ENV_FILEを削除
uv tool uninstall rendereye-mcp                  # またはvenvフォルダーを削除
```

`uninstall-setup`は`%LOCALAPPDATA%\RenderEyeMCP\`(`.env`)と
`%APPDATA%\rendereye_mcp\`のデータベースを残します。すべて削除したい場合は、
これらのフォルダーを手動で削除してください。

## テストした内容

| 方法 | 環境 | 結果 |
|------|------|------|
| `uv tool install .`(ソース) | Windows 11、uv 0.12、独立したツールフォルダー | 成功 |
| `uv tool install <wheel>` | Windows 11、`uv build`でビルドしたwheel | 成功 |
| 新規venvへの`pip install <wheel>` | Windows 11、Python 3.12.6、uvなし | 成功 |
| `rendereye-mcp setup`(2回) | Windows 11、`%LOCALAPPDATA%`/`%APPDATA%`を分離、レジストリ書き込みはスタブ化 | 成功: `.env`作成後に保持、RenderDoc検出、拡張機能6ファイルをインストール |
| `uv tool install --force .`(アップデート)、`uninstall-setup` | Windows 11、独立したフォルダー | 成功: 拡張機能を削除し、`.env`は保持 |
| クリーンなvenvへの`pip install <wheel>` | CI: WindowsとUbuntu、Python 3.11/3.12 | CIで実行 |
| クリーンなWindowsマシン/VM | — | **未実施**。開発マシン上で独立したフォルダーを使ってテスト |
| RenderDocを使ったLinuxでのエンドツーエンド | — | **未実施** |
