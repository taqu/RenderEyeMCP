[English](README.md) | [日本語](README.ja.md)

# RenderEyeMCP

**RenderDocで開いているCaptureを、そのままAIコーディングエージェントに調べてもらう。**

RenderEyeMCPは、Claude CodeやCodexなどのAIコーディングエージェントと
[RenderDoc](https://renderdoc.org/) GUIをつなぐ
[Model Context Protocol](https://modelcontextprotocol.io/)(MCP)サーバーです。
Frameのキャプチャやリプレイは、これまでどおりRenderDocで行います。エージェントは
RenderDocが表示している内容(読み込み中のCapture、選択中のEvent、Pipeline State、
Shader、Bindされたリソース、Buffer、Render Target、Pixel値)を読み取ります。

```text
ゲームエンジン / Unity / Unreal / .rdcファイル
      |  Frameをキャプチャ
      v
RenderDoc GUI(調べたいDrawCallを選択)
      |  読み込み中のCapture + 選択中のEvent
      v
rendereye-mcp(MCPブリッジ)  ──┐
                              ├── rendereye-mcp service(共有IPCサービス)
rendereye-mcp(MCPブリッジ)  ──┘         │
                                        │ TCP 127.0.0.1:37020
                          RenderDoc Python拡張機能
      |  MCP Tool(全58種)
      v
AIコーディングエージェント  ->  根拠に基づくデバッグ支援
```

キャプチャとリプレイを担うのはあくまでRenderDocです。RenderEyeMCPは調査用の読み取り
専用ブリッジで、エージェントがCaptureを開き直す必要はなく、選択中のEventを変更する
こともありません。

## できること

- **RenderDocセッションの検出** — 拡張機能が読み込まれたRenderDoc GUIの一覧、各GUIで
  開いているCapture、接続状態。
- **CaptureとEvent** — Graphics API、Frame番号、Event数、ページ単位のEvent一覧、
  GUIで選択中のEvent。
- **Pipeline State** — Topology、Vertex/Index Buffer、Viewport/Scissor、Shader、
  Render Target、Depth Target、Resource Binding。
- **Shader** — Shader Reflection(入出力、Constant Buffer、リソース、Sampler)、宣言と
  実際のBindingの対応、ページ単位の逆アセンブル、埋め込みソース。
- **リソースとBuffer** — リソース一覧、Texture/Bufferのメタデータ、範囲を限定したBuffer
  読み出しと型付きデコード。
- **Render TargetとPixel** — Bindされたターゲット、TextureのPNGプレビュー、型付きの
  正確なPixel値、チャンネルごとの最小/最大値とヒストグラム。
- **複数エージェントの同時利用** — 複数のMCPブリッジが1つの共有IPCサービスを使うため、
  Claude CodeとCodexで同じRenderDocセッションを同時に調査できます。

先に知っておいてほしい制限:

- 調査対象は常に**RenderDoc GUIで選択中のEvent**です。先にRenderDocでDrawCallや
  Dispatchを選択してください。エージェントは選択を変更できません。
- 実機で検証したのはWindows上のRenderDoc 1.46とD3D12のみです。その他のAPIや
  プラットフォームは[対応プラットフォーム](#対応プラットフォーム)を参照してください。

## 対応プラットフォーム

| プラットフォーム | バイナリ | MCPブリッジ | IPCサービス | RenderDoc連携 |
|------------------|----------|-------------|-------------|--------------|
| Windows amd64 | ✓ | ✓ | ✓ | 検証済み (D3D12, RenderDoc 1.46) |
| Windows 10 | ✓ 見込み | 見込み | 見込み | 未検証 |
| Linux amd64 | ✓ | ✓ | ✓ | Linux版RenderDocが必要 |
| macOS arm64 | ✓ コンパイル済み | 見込み | 見込み | RenderDocなし |

Vulkan、D3D11、OpenGLのCaptureはRenderDocのAPI共通インターフェース経由で動作する見込み
ですが、実機では検証していません。

## 必要なもの

- **RenderDoc 1.46**以上。拡張機能の最小バージョンは1.46です。
- MCP対応のコーディングエージェント: **Claude Code** または **Codex**(両方テスト済み)。
- Python、pip、uv、Goツールチェーンは通常インストールには不要です。

RenderDoc拡張機能はRenderDoc内蔵のPythonで動作します。ユーザーが別途Pythonを
インストールする必要はありません。

## かんたんインストール(Windows)

1. [GitHub Releases](https://github.com/taqu/RenderEyeMCP/releases) から
   `rendereye-mcp_<version>_windows_amd64.zip` をダウンロードします。
2. アーカイブを展開します。
3. インストーラーを実行します(手動でのファイル配置については
   [インストール](docs/ja/installation.md)を参照):

   ```powershell
   .\install.ps1
   ```

4. RenderDocで **Tools → Manage Extensions** を開き、**RenderEyeMCP** を選んで
   **Always Load** を有効にします。

5. コーディングエージェントを設定します。Claude Codeの場合、`~/.claude.json` に追加:

   ```json
   {
     "mcpServers": {
       "rendereye": {
         "command": "C:\\Users\\<ユーザー名>\\AppData\\Local\\RenderEyeMCP\\rendereye-mcp.exe"
       }
     }
   }
   ```

6. コーディングエージェントを再起動します。

詳しい手順: [docs/ja/installation.md](docs/ja/installation.md)。

## 使ってみる

1. RenderDocでCaptureを開きます(エンジンから、または *File → Open Capture*)。
2. Event BrowserでDrawCallを選択します。
3. エージェントに頼みます。

   > RenderDocで今開いているCaptureを調査して、選択中のDrawCallを特定し、
   > そのPipeline Stateを要約してください。

手順の詳細は[クイックスタート](docs/ja/quickstart.md)にあります。

## ドキュメント

| 内容 | English | 日本語 |
|------|---------|--------|
| インストール | [installation.md](docs/en/installation.md) | [installation.md](docs/ja/installation.md) |
| エージェントの設定 | [configuration.md](docs/en/configuration.md) | [configuration.md](docs/ja/configuration.md) |
| クイックスタート | [quickstart.md](docs/en/quickstart.md) | [quickstart.md](docs/ja/quickstart.md) |
| デバッグシナリオ | [examples/](docs/en/examples/README.md) | [examples/](docs/ja/examples/README.md) |
| プロンプト例 | [prompts.md](docs/en/prompts.md) | [prompts.md](docs/ja/prompts.md) |
| MCP Toolリファレンス | [tools.md](docs/en/tools.md) | [tools.md](docs/ja/tools.md) |
| トラブルシューティング | [troubleshooting.md](docs/en/troubleshooting.md) | [troubleshooting.md](docs/ja/troubleshooting.md) |
| アーキテクチャ | [architecture.md](docs/en/architecture.md) | [architecture.md](docs/ja/architecture.md) |

開発者向け資料(英語): [開発ガイド](docs/development.md)、
[IPCプロトコル](docs/ipc_protocol.md)、[シングルバイナリアーキテクチャ](docs/development/single-binary.md)。

## トラブルシューティング

**エージェントがRenderDocセッションを見つけられない:**

- RenderDocでRenderEyeMCP拡張機能が有効になっているか確認します
  (**Tools → Manage Extensions**、*Always Load*)。
- 拡張機能を有効にした後、コーディングエージェントを再起動します。
- RenderDocにCaptureが開いているか確認します。

**共有IPCサービスが起動しない:**

- MCPブリッジが初回起動時にサービスを自動で立ち上げます。失敗する場合は、別のターミナルで
  `rendereye-mcp service` を実行してエラーを確認してください。
- ポート37020が他のプログラムで使われている場合は、実行ファイルと同じ場所の `.env` ファイルに
  `RENDEREYE_IPC_PORT` を別のポートで設定してください。

詳しくは[トラブルシューティング](docs/ja/troubleshooting.md)を参照してください。

## コントリビュート

[CONTRIBUTING.md](CONTRIBUTING.md)(英語)を参照してください。セキュリティに関する報告は
[SECURITY.md](SECURITY.md)へ。

```bash
# Go開発
go test ./...
go vet ./...
go build ./cmd/rendereye-mcp/

# Python拡張機能(RenderDoc拡張機能のみ)
uv sync
uv run pytest tests/
```

## ライセンス

[MIT](LICENSE)。RenderDocは独自のライセンスを持つ別プロジェクトであり、同梱していません。
