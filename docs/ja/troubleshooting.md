[English](../en/troubleshooting.md) | [日本語](troubleshooting.md)

# トラブルシューティング

まず各レイヤーを確認します。

```powershell
rendereye-mcp version          # バイナリが動いているか
rendereye-mcp service          # サービスを手動で起動してログを確認
```

次に、どのレイヤーで失敗しているかを切り分けます。**エージェント ↔ MCPサーバー**(stdio)、
**MCPサーバー ↔ 共有サービス**(TCP)、**サービス ↔ RenderDoc拡張機能**(TCP)、
**拡張機能 ↔ リプレイ**(RenderDoc)。以下の節はこの順に並んでいます。

## インストールの問題

### `rendereye-mcp`が見つからない

バイナリはフルパスで実行してください。[設定](configuration.md)の説明どおり、
コーディングエージェントの設定に`rendereye-mcp.exe`へのフルパスを指定してください。
ターミナルから実行したい場合は、バイナリのあるディレクトリをPATHに追加することもできます。

### RenderDocのバージョンが1.46より古い

拡張機能は`minimum_renderdoc: 1.46`を宣言しているため、古いRenderDocでは読み込まれません。
RenderDocを更新してください。

### `RENDEREYE_ENV_FILE`が未設定 / 別の場所を指している

バイナリと同じディレクトリにある`.env`ファイルを`RENDEREYE_ENV_FILE`環境変数で指定します。
設定を変えた後は、サービスプロセスを終了してエージェントを再起動してください。

## 接続の問題

### エージェントが「サーバーの起動に失敗した」と言う

1. エージェント設定の`command`のパスが存在するか確認します(`Test-Path <path>`)。
2. そのパスで`rendereye-mcp version`を実行してバイナリが動くか確認します。
3. Claude Codeでは`claude --debug`でサーバーのstderrを確認できます。Codexはそのログを
   確認します。

### Toolは見えるが、RenderDocセッションが見つからない

`list_renderdoc_sessions`が空、または`get_current_capture`が`no_renderdoc_connected`を
返す場合:

1. 拡張機能は有効ですか? RenderDoc → **Tools → Manage Extensions** → RenderEyeMCPが
   **Loaded**かつ**Always Load**になっているか確認します。RenderDocのログ
   (`%TEMP%\RenderDoc\RenderDoc_*.log`)に
   `Automatically loading extension "rendereye"`が出ているはずです。
2. 拡張機能はこのユーザー向けにインストールされていますか?
   `%APPDATA%\qrenderdoc\extensions\rendereye\`に`__init__.py`と`extension.json`が
   あるか確認してください。
3. 最大30秒待ってください。拡張機能は間隔を空けながら再接続します。
4. ポート: `RENDEREYE_IPC_PORT`を変えた場合は、RenderDoc自身の環境変数にも同じ値が
   必要です([設定](configuration.md#環境変数の設定)を参照)。
5. ファイアウォールやセキュリティソフトが、ポート37020のループバックTCPを遮断していないか。

### 共有サービスが使えない

エージェントが`Shared service failed to start within 30s`と報告する場合:

- 他のプログラムがポート37020を使っている可能性があります。
  `netstat -ano | findstr :37020`で確認してください。
- サービスをフォアグラウンドで動かすとログが見られます。

  ```powershell
  $env:RENDEREYE_LOG_LEVEL = "debug"
  rendereye-mcp service
  ```

  そのまま動かしておき、エージェントを起動すると、このサービスに接続します。

### 複数のエージェントが競合する

本来は競合しません。すべてのエージェントが1つのサービスを共有します。エージェントごとに
別のポートを設定しないでください。いずれかが固まった場合は、`rendereye-mcp service`プロセスを
終了してエージェントを再起動します。

### RenderDocを再起動すると接続が切れる

想定どおりの動作です。古いセッションは`disconnected`(`last_known_capture`付き)になり、
新しいRenderDocウィンドウは新しい`instance_id`の新しいセッションとして登録されます。
もう一度頼むか、新しい`instance_id`を指定してください。

## Captureの問題

### RenderDocには接続しているが、Captureが読み込まれていない

`status: no_capture_loaded` — そのRenderDocウィンドウでCaptureを開いてください。大きな
Captureでは、少しの間`capture_loading`になることがあります。

### Captureを開いているのに、エージェントが「ない」と言う

- 拡張機能のないRenderDocウィンドウ(別のRenderDocインストールなど)で開いています。
  `list_renderdoc_sessions`で確認してください。
- 2つのRenderDocウィンドウが接続していて、エージェントが違う方を選んでいます。
  セッション一覧を出してもらい、正しい`instance_id`を使うよう頼んでください。

### 複数のRenderDocセッションが見つかる

`status: ambiguous`になります。どちらを使うかエージェントに伝えてください。例:
「`my_scene.rdc`を開いているRenderDocセッションを使ってください。」

### リソースIDが使えなくなった

IDは、それを取得したときに開いていたCaptureに属します。Captureを切り替えたり
開き直したりした後は、エージェントにもう一度調べ直してもらってください。

### エージェントが選択したものと違うEventを報告する

1. 「get_selected_eventを呼んでください。」と頼み、`selected_event_id`とRenderDocの
   Event BrowserのEIDを比べます。
2. 接続中のRenderDocウィンドウでクリックしたか確認します(`list_renderdoc_sessions`の
   `process_id`で確認できます)。
3. それでもIDが違う場合は、RenderDocのバージョン、Captureの開き方、RenderEyeMCPの
   ログを添えて報告してください。

### `event_not_selected`

選択中のEventとは違う`event_id`で`get_pipeline_state`が呼ばれました。そのEventを
RenderDocで選択してください。RenderEyeMCPが選択を変更することはありません。

## 調査時の問題

| 症状 | 原因 / 対処 |
|------|-------------|
| `shader_not_bound` | 選択中のEventにそのステージのShaderがない(マーカーや深度のみのDrawなど)。DrawCallを選択する |
| `depth_stencil`が注意書きしか返さない | Depth/Stencilステートは取得できない。比較関数や書き込みマスクはRenderDocのPipeline Stateパネルで確認する |
| `resource_not_found` | IDの誤り、または前のCaptureのID |
| `read_buffer_data`の`range_too_large` | 1回あたり最大16384バイト。`offset`で分けて読む |
| `image_too_large` | `max_dim`を`required_max_dim`以上にするか、`suggested_mip`を指定する |
| `result_too_large` | 応答が16 MiBを超えた。小さいMipや`max_dim`を使う |
| `timeout` | RenderDocが処理中(長いリプレイ)、またはモーダルダイアログが開いている。閉じて再試行する |
| `extension_error` / `unsupported` | RenderDocがエラーを返した。`message`に説明がある。RenderDocのバージョンとGraphics APIを添えて報告する |
| 対応していないGraphics API | ToolはRenderDocのAPI共通インターフェースを使う。実機検証したのはD3D12のみ。違いがあれば報告する |
| Pixel値が見た目の色と違う | 正常。RenderDocのビューアーは範囲調整と表示変換をかける。`get_pixel_value`は格納された値(`R32_UINT`のIDや線形floatの深度など)を返す |
| Render Targetが「真っ黒」 | `get_texture_statistics`を確認する。maxが0より大きければ、表示範囲外にデータがある |

## 診断情報

**ログの出力先**

| コンポーネント | ログ |
|----------------|------|
| MCPサーバー(`rendereye-mcp`) | stderr。エージェントが取得する(`claude --debug`、Codexのログ) |
| 共有サービス | 自動起動時はファイルに書かれない。ターミナルで`rendereye-mcp service`を実行すると見られる |
| RenderDoc拡張機能とRenderDoc | `%TEMP%\RenderDoc\RenderDoc_*.log` |

詳しいログが必要なら`.env`で`RENDEREYE_LOG_LEVEL=debug`を設定し、サービスプロセスを
終了してからエージェントを再起動してください。

**レイヤーの見分け方**

- エージェントがサーバーを起動できない → 設定 / MCPレイヤー
- `no_renderdoc_connected` → 拡張機能またはIPCレイヤー
- `no_capture_loaded`、`shader_not_bound`、`resource_not_found` → Captureについての
  通常の回答
- `extension_error`、`unsupported`、`timeout` → RenderDoc内部のリプレイレイヤー

**バグ報告に含めてほしいもの:** OSのバージョン、RenderDocのバージョン、
`rendereye-mcp version`の出力、コーディングエージェントとそのバージョン、CaptureのGraphics API、
失敗したプロンプトまたはTool呼び出しとその結果、関連するログの抜粋。

## セキュリティとプライバシー

Captureやログには、アプリケーションのパス、リソース名やShader名、Shaderソース、
未発表コンテンツの描画結果が含まれることがあります。共有する前に内容を確認し、機密情報を
取り除いてください。権限のないまま、プロプライエタリなCaptureを公開Issueに添付しないで
ください。IPCサービスは`127.0.0.1`でのみ待ち受け、起動ごとのトークンを要求します。
他のマシンに公開しないでください。
