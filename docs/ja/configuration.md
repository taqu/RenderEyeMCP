[English](../en/configuration.md) | [日本語](configuration.md)

# コーディングエージェントとRenderEyeMCPの設定

- [エージェントとRenderEyeMCPのつながり方](#エージェントとrendereyemcpのつながり方)
- [Claude Codeを接続する](#claude-codeを接続する)
- [Codexを接続する](#codexを接続する)
- [その他のMCPクライアント](#その他のmcpクライアント)
- [接続の確認](#接続の確認)
- [複数のエージェントを同時に使う](#複数のエージェントを同時に使う)
- [環境変数の設定](#環境変数の設定)

## エージェントとRenderEyeMCPのつながり方

どのエージェントも、stdio経由で同じコマンドを起動します。

```text
<rendereye-mcp実行ファイルのフルパス>
```

サブコマンドは不要です。バイナリはMCPブリッジとして自動的に起動します。
また、`127.0.0.1:37020` の共有IPCサービスがまだ起動していなければ自動的に開始します。

エントリはエージェントのMCP設定ファイルに手動で追加するか、
インストーラー（`install.ps1` / `install.sh`）が出力するスニペットをコピーして使います。

## Claude Codeを接続する

`~/.claude.json`（ユーザースコープ）またはプロジェクトディレクトリの `.mcp.json`
（プロジェクトスコープ）に `rendereye` エントリを追加します。
パスは `rendereye-mcp.exe` の実際の場所に置き換えてください。

```json
{
  "mcpServers": {
    "rendereye": {
      "type": "stdio",
      "command": "C:\\Tools\\RenderEyeMCP\\rendereye-mcp.exe"
    }
  }
}
```

Claude Codeを再起動して確認します。

```powershell
claude mcp get rendereye
```

`Status: ✓ Connected` が表示されれば成功です。セッション内で `/mcp` を実行すると
`rendereye` とそのツール一覧が表示されます。

Claude Code固有の注意点:

- `.mcp.json` のプロジェクトスコープのサーバーは、そのフォルダーでClaude Codeを
  初めて起動したときに承認が必要です。承認前は `claude mcp get` に *Pending approval*
  と表示されます。
- サーバーが *Failed* と表示される場合は `claude --debug` を実行してサーバーの
  stderrログを確認してください。

## Codexを接続する

`~/.codex/config.toml`（ユーザースコープ）または
`<プロジェクト>/.codex/config.toml`（プロジェクトスコープ）に追加します。

```toml
[mcp_servers.rendereye]
command = "C:\\Tools\\RenderEyeMCP\\rendereye-mcp.exe"
```

確認:

```powershell
codex mcp list
```

`rendereye` がリストに表示されれば成功です。

## その他のMCPクライアント

stdioサーバーを上記のコマンドで起動できるMCPクライアントであれば動作します。
[examples](../examples/)ディレクトリにCursor、VS Code（GitHub Copilot）、
Gemini向けの設定スニペットがあります。

## 接続の確認

各レイヤーを順番に確認します。

| 確認項目 | 方法 | 期待される結果 |
|----------|------|----------------|
| バイナリの動作 | `rendereye-mcp.exe version` | バージョンとビルド日時が表示される |
| エージェントがサーバーを起動できる | `claude mcp get rendereye` / `codex mcp list` | Connected / リストに表示 |
| ツールが認識されている | 「rendereyeで使えるMCPツールを一覧表示して」 | `get_current_capture`などが表示される |
| RenderDocに接続できている | 「RenderEyeMCPが認識しているRenderDocのセッションを一覧表示して」 | `connection_state: connected`のセッション |
| キャプチャが見えている | 「RenderDocで現在読み込まれているキャプチャを教えて」 | `status: loaded`と`.rdc`のパス |

## 複数のエージェントを同時に使う

RenderEyeMCPは1台のマシンに対して**共有IPCサービス**を1つだけ起動します。
各エージェントは独自のMCPブリッジプロセスを起動し、すべてのブリッジが同じサービスに
接続します。サービスだけがRenderDoc拡張機能と通信します。

```text
Claude Code ──stdio── rendereye-mcp ─┐
                                     ├─ TCP 127.0.0.1:37020 ─ 共有サービス ─ RenderDoc拡張機能
Codex ───────stdio── rendereye-mcp ─┘
```

追加の設定は不要です。両方のエージェントを上記のように設定して、任意の順序で起動します。
すべての検査ツールは読み取り専用なので、同時使用による干渉はありません。

共有サービスを手動で停止するには:

```powershell
# Windows
taskkill /F /IM rendereye-mcp.exe
```

次にエージェントがブリッジを起動したとき、サービスは自動的に再起動します。

## 環境変数の設定

設定は環境変数から読み取られます。永続的に設定する場合は `.env` ファイルに記述し、
`RENDEREYE_ENV_FILE` でそのパスを指定します。

| 変数 | 既定値 | 意味 |
|------|--------|------|
| `RENDEREYE_IPC_HOST` | `127.0.0.1` | サービスのバインドアドレス。ループバックのみ。`0.0.0.0`は拒否されます。 |
| `RENDEREYE_IPC_PORT` | `37020` | サービスのTCPポート番号。 |
| `RENDEREYE_LOG_LEVEL` | `info` | ログレベル: `debug`、`info`、`warn`、`error`。 |
| `RENDEREYE_ENV_FILE` | (なし) | 起動時に読み込む `.env` ファイルのパス。 |

**ポートを変更する場合:** RenderDoc拡張機能は `RENDEREYE_IPC_PORT` をRenderDoc自身の
環境変数から読み取ります。ポートを変更した場合は、ユーザー環境変数としても設定してから
RenderDocを再起動してください。
