[English](../en/configuration.md) | [日本語](configuration.md)

# コーディングエージェントとRenderEyeMCPの設定

- [エージェントとRenderEyeMCPのつながり方](#エージェントとrendereyemcpのつながり方)
- [Claude Codeを接続する](#claude-codeを接続する)
- [Codexを接続する](#codexを接続する)
- [その他のMCPクライアント](#その他のmcpクライアント)
- [接続の確認](#接続の確認)
- [複数のエージェントを同時に使う](#複数のエージェントを同時に使う)
- [環境設定(.env)](#環境設定env)

## エージェントとRenderEyeMCPのつながり方

どのエージェントも、stdio経由で`rendereye-mcp`実行ファイルを起動します。サブコマンドは
不要で、デフォルトモードがMCPブリッジです。

```text
<rendereye-mcp実行ファイルのパス>
```

この設定をエージェントのMCPサーバー設定に追加し、エージェントを再起動してください。

## Claude Codeを接続する

`~/.claude.json`(ユーザースコープ)またはプロジェクトの`.mcp.json`(プロジェクトスコープ)
に追加します。

```json
{
  "mcpServers": {
    "rendereye": {
      "command": "C:\\Users\\<ユーザー名>\\AppData\\Local\\RenderEyeMCP\\rendereye-mcp.exe"
    }
  }
}
```

パスは`rendereye-mcp.exe`の実際の場所に置き換えてください。インストーラーの既定では
`%LOCALAPPDATA%\RenderEyeMCP\rendereye-mcp.exe`に配置されます。LinuxやmacOSでは
`which rendereye-mcp`で確認したパスを使ってください。

Claude Codeを再起動して確認します。

```powershell
claude mcp get rendereye
```

`Status: ✓ Connected`と表示されればOKです。セッション内では`/mcp`で`rendereye`と
そのToolが一覧できます。

Claude Code固有の注意:

- `.mcp.json`によるプロジェクトスコープのサーバーは、そのフォルダーでClaude Codeを初めて
  起動したときに承認が必要です。承認前は`claude mcp get`が*Pending approval*と表示します。
- サーバーが*Failed*になる場合は、`claude --debug`でサーバーのstderrログを確認できます。

## Codexを接続する

`~/.codex/config.toml`(ユーザースコープ)または`<project>/.codex/config.toml`
(プロジェクトスコープ)に追加します。

```toml
[mcp_servers.rendereye]
command = "C:\\Users\\<ユーザー名>\\AppData\\Local\\RenderEyeMCP\\rendereye-mcp.exe"
```

確認:

```powershell
codex mcp list
```

`rendereye`が一覧に出ればOKです。

- プロジェクトスコープの設定は、信頼済み(trusted)にしたプロジェクトでのみ読み込まれます。

## その他のMCPクライアント

stdioサーバーを起動できるMCPクライアントなら動作します。コマンドとして`rendereye-mcp`
実行ファイルのパスを引数なしで指定してください。Claude CodeとCodex以外のクライアントで
の結果をぜひ報告してください。

## 接続の確認

レイヤーごとに確認します。

| 確認内容 | コマンドまたはプロンプト | 期待される結果 |
|----------|--------------------------|----------------|
| バイナリが動作する | `rendereye-mcp version` | バージョン行 |
| エージェントがサーバーを起動できる | `claude mcp get rendereye` / `codex mcp list` | Connected / 一覧に表示 |
| Toolが認識されている | 「server_statusを呼んでください。」 | `server_name: RenderEyeMCP`と`server_version` |
| RenderDocに届く | 「RenderDocセッションを一覧表示してください。」 | `connection_state: connected`のセッション |
| Captureが見える | 「RenderDocで今読み込まれているCaptureは何ですか?」 | `status: loaded`と`.rdc`のパス |

これらのプロンプトは普通の自然言語による依頼です。どのMCP Tool
(`server_status`、`list_renderdoc_sessions`、`get_current_capture`など)を呼ぶかは
エージェントが判断するので、Tool名を入力する必要はありません。エージェントが
違うToolを選ぶ場合は、プロンプトでTool名を挙げるとヒントになります。

## 複数のエージェントを同時に使う

RenderEyeMCPは、ユーザーセッションごとに1つの**共有IPCサービス**を動かします。各エージェント
はそれぞれ`rendereye-mcp`プロセス(MCPブリッジ)を起動し、それらがすべて同じサービスに
接続します。RenderDocと通信するのはサービスだけです。

```text
Claude Code ──stdio── rendereye-mcp ─┐
                                     ├─ TCP 127.0.0.1:37020 ─ rendereye-mcp service ─ RenderDoc拡張機能
Codex ───────stdio── rendereye-mcp ─┘
```

追加の設定は不要です。上記のとおり両方のエージェントを設定し、好きな順番で起動して
ください。例:

1. RenderDocでCaptureを開き、DrawCallを選択します。
2. Claude Codeで「選択中のDrawCallのPipeline Stateを要約してください。」と頼みます。
3. 同時にCodexで「選択中のPixel ShaderにBindされているTextureを一覧してください。」と
   頼みます。

どちらの回答も同じRenderDocセッションから得られます。調査用のToolはすべて読み取り
専用なので、同時に使っても干渉しません。エージェントごとに別のポートを割り当てる
必要はありません。

サービスは停止するかマシンを再起動するまで動き続けます。停止するには`rendereye-mcp service`
プロセスを強制終了してください。次回エージェント起動時に自動で再起動します。

## 環境設定(.env)

設定は`.env`ファイルから読み込まれます。ブリッジは`RENDEREYE_ENV_FILE`環境変数が指す
パス(設定されている場合)、なければカレントディレクトリの`.env`を読み込みます。
優先順位は:

1. プロセスにすでに設定されている環境変数(最優先)
2. `.env`ファイルの値
3. 組み込みの既定値

既定の設定(ホスト`127.0.0.1`、ポート`37020`)は`.env`を編集しなくても動作します。
ほとんどのユーザーは`.env`を編集する必要はありません。

| 変数 | 既定値 | 意味 |
|------|--------|------|
| `RENDEREYE_IPC_HOST` | `127.0.0.1` | サービスのアドレス。ループバックのみで、`0.0.0.0`は拒否されます |
| `RENDEREYE_IPC_PORT` | `37020` | サービスのポート |
| `RENDEREYE_LOG_LEVEL` | `info` | `debug`、`info`、`warn`、`error` |

注意:

- **変更はサービスの再起動時に反映されます。** `rendereye-mcp service`プロセスを強制
  終了し、エージェントを再起動してください。
- **ポートを変更する場合:** RenderDoc拡張機能は`.env`を読みません。RenderDoc自身の
  環境変数から`RENDEREYE_IPC_PORT`を読みます。ポートを変える場合はユーザー環境変数にも
  同じ値を設定してRenderDocに引き継がせ、RenderDocを再起動してください。
