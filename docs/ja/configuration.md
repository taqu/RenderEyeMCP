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

どのエージェントも、stdio経由で同じコマンドを起動します。

```text
<rendereye-mcp実行ファイルのパス> serve
```

`rendereye-mcp setup-agent <agent>`がこの設定を書き込みます。このコマンドは:

- 実行に使った`rendereye-mcp`実行ファイルの絶対パスを使います。
- ターミナルに`RENDEREYE_ENV_FILE`が設定されていれば、それを設定エントリに追加します。
- `rendereye`エントリだけを編集し、他の設定はすべて保持します。壊れたファイルは
  変更せず、書き込み前に元のファイルを`.bak`(以降`.bak.1`、…)として保存します。

便利なオプション: `--dry-run`(プレビューのみ)、`--scope project --project-path <dir>`、
`--force`(異なる内容の既存`rendereye`エントリを置き換え)、`--remove`。
詳細は[設定の安全性](../agent_configuration_safety.md)(英語)を参照してください。

> `setup-agent`は**`rendereye-mcp setup`の後に開いた新しいターミナル**で実行して
> ください。そうすると`RENDEREYE_ENV_FILE`がエントリに含まれます。含まれなくても、
> エージェント自体をsetup後に起動していれば動作します。

## Claude Codeを接続する

**前提:** Claude Codeがインストール済みで、`rendereye-mcp setup`が完了していること。

```powershell
rendereye-mcp setup-agent claude-code                 # ユーザースコープ: ~/.claude.json
rendereye-mcp setup-agent claude-code --scope project # プロジェクトスコープ: カレントディレクトリの.mcp.json
```

手動で設定する場合(ユーザースコープ、`~/.claude.json`の`mcpServers`)。パスは自分の
環境に合わせて置き換えてください。実行ファイルのパスは`where.exe rendereye-mcp`で
確認できます。

```json
{
  "mcpServers": {
    "rendereye": {
      "type": "stdio",
      "command": "C:\\Users\\<you>\\.local\\bin\\rendereye-mcp.exe",
      "args": ["serve"],
      "env": {
        "RENDEREYE_ENV_FILE": "C:\\Users\\<you>\\AppData\\Local\\RenderEyeMCP\\.env"
      }
    }
  }
}
```

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

**前提:** Codex CLIがインストール済みで、`rendereye-mcp setup`が完了していること。

```powershell
rendereye-mcp setup-agent codex                  # ユーザースコープ: ~/.codex/config.toml(CODEX_HOMEを考慮)
rendereye-mcp setup-agent codex --scope project  # <project>/.codex/config.toml
```

手動で設定する場合(TOMLではバックスラッシュをエスケープします):

```toml
[mcp_servers.rendereye]
command = "C:\\Users\\<you>\\.local\\bin\\rendereye-mcp.exe"
args = ["serve"]

[mcp_servers.rendereye.env]
RENDEREYE_ENV_FILE = "C:\\Users\\<you>\\AppData\\Local\\RenderEyeMCP\\.env"
```

確認:

```powershell
codex mcp list
```

`rendereye`が一覧に出ればOKです。Codex固有の注意:

- プロジェクトスコープの設定は、信頼済み(trusted)にしたプロジェクトでのみ読み込まれます。
- `setup-agent code`はCodexの別名です。VS Code用ではありません(VS Codeは`vscode`)。

## その他のMCPクライアント

`setup-agent`は`cursor`、`vscode`(GitHub Copilot)、`gemini`向けの設定も書き込めます。
これらの設定ファイルは自動テストで生成・検証していますが、今回のリリースでは実際の
クライアントでは**確認していません**。上記のコマンドでstdioサーバーを起動できるMCP
クライアントなら動作するはずです。結果をぜひ報告してください。

## 接続の確認

レイヤーごとに確認します。

| 確認内容 | コマンドまたはプロンプト | 期待される結果 |
|----------|--------------------------|----------------|
| エージェントの設定が正しい | `rendereye-mcp doctor --agent claude-code`(または`codex`) | `✗`の行がない |
| エージェントがサーバーを起動できる | `claude mcp get rendereye` / `codex mcp list` | Connected / 一覧に表示 |
| Toolが認識されている | 「server_statusを呼んでください。」 | `server_name: RenderEyeMCP`と`server_version` |
| RenderDocに届く | 「RenderDocセッションを一覧表示してください。」 | `connection_state: connected`のセッション |
| Captureが見える | 「RenderDocで今読み込まれているCaptureは何ですか?」 | `status: loaded`と`.rdc`のパス |

これらのプロンプトは普通の自然言語による依頼です。どのMCP Tool
(`server_status`、`list_renderdoc_sessions`、`get_current_capture`など)を呼ぶかは
エージェントが判断するので、Tool名を入力する必要はありません。エージェントが
違うToolを選ぶ場合は、プロンプトでTool名を挙げるとヒントになります。

## 複数のエージェントを同時に使う

RenderEyeMCPは、ユーザーセッションごとに1つの**共有IPCサービス**を動かします。
各エージェントはそれぞれ小さな`rendereye-mcp serve`プロセスを起動し、それらがすべて
同じサービスに接続します。RenderDocと通信するのはサービスだけです。

```text
Claude Code ──stdio── rendereye-mcp serve ─┐
                                            ├─ TCP 127.0.0.1:37020 ─ 共有サービス ─ RenderDoc拡張機能
Codex ───────stdio── rendereye-mcp serve ─┘
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

サービスはエージェント終了後も動き続けます。`rendereye-mcp service stop`で停止でき、
必要になれば再び自動で起動します。

## 環境設定(.env)

設定は`RENDEREYE_ENV_FILE`が指す`.env`ファイルから読み込まれます。優先順位は:

1. プロセスにすでに設定されている環境変数(最優先)
2. `.env`ファイルの値
3. 組み込みの既定値

`RENDEREYE_ENV_FILE`が未設定の場合は、カレントディレクトリに`.env`があればそれを
使います(開発用)。ほとんどのユーザーは`.env`を編集する必要はありません。

| 変数 | 既定値 | 意味 |
|------|--------|------|
| `RENDEREYE_RENDERDOC_EXE` | setupが検出 | `qrenderdoc.exe`のフルパス(状態チェックと`capture_open`で使用) |
| `RENDEREYE_LOG_LEVEL` | `INFO` | `DEBUG`、`INFO`、`WARNING`、`ERROR`、`CRITICAL` |
| `RENDEREYE_IPC_HOST` | `127.0.0.1` | サービスのアドレス。ループバックのみで、`0.0.0.0`は拒否されます |
| `RENDEREYE_IPC_PORT` | `37020` | サービスのポート(下の注意を参照) |
| `RENDEREYE_CONNECTION_TIMEOUT` | `10.0` | IPC接続のタイムアウト(秒) |
| `RENDEREYE_STORAGE_PATH` | `%APPDATA%\rendereye_mcp\captures.db` | Captureレジストリとセッション用のSQLiteデータベース |
| `RENDEREYE_CAPTURE_ENABLED` | `true` | `.rdc`ファイルの検出を有効にする |
| `RENDEREYE_CAPTURE_DIRS` | 空 | `.rdc`ファイルを監視するフォルダー。Windowsは`;`、Linuxは`:`で区切る |
| `RENDEREYE_CAPTURE_SCAN_INTERVAL` | `10.0` | バックグラウンドの再スキャン間隔(秒) |
| `RENDEREYE_CAPTURE_STABILITY_SECONDS` | `2.0` | 新しいファイルを「準備完了」とみなすまで、変化がないことを待つ時間 |

注意:

- **変更は共有サービスの再起動時に反映されます。** `rendereye-mcp service stop`を実行し、
  エージェントを再起動してください。
- **ポートを変更する場合:** RenderDoc拡張機能は`.env`を読みません。RenderDoc自身の
  環境変数から`RENDEREYE_IPC_PORT`を読みます。ポートを変える場合はユーザー環境変数にも
  同じ値を設定してRenderDocに引き継がせ、RenderDocを再起動してください。
- `RENDEREYE_CAPTURE_DIRS`はCaptureレジストリ用のTool(`capture_list`、`capture_latest`
  など)でのみ必要です。RenderDocで開いているCaptureの調査には使いません。
