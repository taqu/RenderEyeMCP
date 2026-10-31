[English](../en/troubleshooting.md) | [日本語](troubleshooting.md)

# トラブルシューティング

まず次を実行します。

```powershell
rendereye-mcp doctor                      # インストール、.env、RenderDoc、拡張機能、サービス
rendereye-mcp doctor --agent claude-code  # 指定したエージェントの設定も確認
rendereye-mcp service status              # 共有サービスが待ち受けているか
```

次に、どのレイヤーで失敗しているかを切り分けます。**エージェント ↔ MCPサーバー**(stdio)、
**MCPサーバー ↔ 共有サービス**(TCP)、**サービス ↔ RenderDoc拡張機能**(TCP)、
**拡張機能 ↔ リプレイ**(RenderDoc)。以下の節はこの順に並んでいます。

## インストールの問題

### `rendereye-mcp`が見つからない

- uv: `uv tool update-shell`を実行し、新しいターミナルを開きます。
- pip/venv: フルパスで呼び出します。
  `& "$env:LOCALAPPDATA\RenderEyeMCP\venv\Scripts\rendereye-mcp.exe"`

### setupで`RenderDoc not found`と表示される

setupが探すのは`%ProgramFiles%\RenderDoc`と`%ProgramFiles(x86)%\RenderDoc`だけです。
`.env`にパスを設定してください(`RENDEREYE_RENDERDOC_EXE=D:\Tools\RenderDoc\qrenderdoc.exe`)。
自分で開いたCaptureを調べるだけなら、この設定は関係ありません。

### RenderDocのバージョンが1.46より古い

拡張機能は`minimum_renderdoc: 1.46`を宣言しているため、古いRenderDocでは読み込まれません。
RenderDocを更新してください。

### `RENDEREYE_ENV_FILE`が未設定 / 別の場所を指している

`rendereye-mcp setup`を再実行し、新しいターミナルを開いて、**エージェントも再起動**して
ください。setupより前に起動したプロセスには、新しいユーザー環境変数が見えません。

### インストール時のPythonエラー

RenderEyeMCPにはPython 3.11以上が必要です。uvなら自動で用意されます。pipの場合は
venv内で`python --version`を確認してください。

### コマンド出力で`UnicodeEncodeError`が出る

`rendereye-mcp`コマンドについては今回のリリースで修正済みです。UTF-8以外のコンソール
(cp932など)でRenderEyeMCPのモジュールを直接スクリプトから使う場合は、
`PYTHONIOENCODING=utf-8`を設定してください。

## 接続の問題

### エージェントが「サーバーの起動に失敗した」と言う

1. エージェント設定の`command`のパスが存在するか確認します(`Test-Path <path>`)。
2. `rendereye-mcp doctor --agent <agent>`を実行します。
3. Claude Codeでは`claude --debug`でサーバーのstderrを確認できます。Codexはそのログを
   確認します。
4. 別のインストールから`setup-agent`を実行していませんか? 実際に使う`rendereye-mcp`で
   `setup-agent`を再実行してください(エントリを置き換えるには`--force`)。

### Toolは見えるが、RenderDocセッションが見つからない

`list_renderdoc_sessions`が空、または`get_current_capture`が`no_renderdoc_connected`を
返す場合:

1. 拡張機能は有効ですか? RenderDoc → **Tools → Manage Extensions** → RenderEyeMCPが
   **Loaded**かつ**Always Load**になっているか確認します。RenderDocのログ
   (`%TEMP%\RenderDoc\RenderDoc_*.log`)に
   `Automatically loading extension "rendereye"`が出ているはずです。
2. 拡張機能はこのユーザー向けにインストールされていますか? `doctor`がフォルダーを表示します。
3. 最大30秒待ってください。拡張機能は間隔を空けながら再接続します。
4. ポート: `RENDEREYE_IPC_PORT`を変えた場合は、RenderDoc自身の環境変数にも同じ値が
   必要です([設定](configuration.md#環境設定env)を参照)。
5. ファイアウォールやセキュリティソフトが、ポート37020のループバックTCPを遮断していないか。

### 共有サービスが使えない

`rendereye-mcp service status`が`not running`を返す、またはエージェントが
`Shared service failed to start within 30s`と報告する場合:

- 他のプログラムがポート37020を使っている可能性があります。
  `netstat -ano | findstr :37020`で確認してください。
- サービスをフォアグラウンドで動かすとログが見られます。

  ```powershell
  rendereye-mcp service stop
  $env:RENDEREYE_LOG_LEVEL = "DEBUG"
  rendereye-mcp service run
  ```

  そのまま動かしておき、エージェントを起動すると、このサービスに接続します。
- `status`が*stale ready file*と表示する場合は、以前のサービスが後始末をせずに終了して
  います。`rendereye-mcp service stop`で削除できます。

### 複数のエージェントが競合する

本来は競合しません。すべてのエージェントが1つのサービスを共有します。エージェントごとに
別のポートを設定しないでください。いずれかが固まった場合は、`rendereye-mcp service stop`
を実行してエージェントを再起動します。

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
3. それでもIDが違う場合は、検証中に1回観測された既知の未解決事項です。RenderDocの
   バージョン、Captureの開き方、RenderEyeMCPのログを添えて報告してください。

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
| MCPサーバー(`rendereye-mcp serve`) | stderr。エージェントが取得する(`claude --debug`、Codexのログ) |
| 共有サービス | 自動起動時はファイルに書かれない。上記のとおりターミナルで`rendereye-mcp service run`を実行すると見られる |
| RenderDoc拡張機能とRenderDoc | `%TEMP%\RenderDoc\RenderDoc_*.log` |

詳しいログが必要なら`.env`で`RENDEREYE_LOG_LEVEL=DEBUG`を設定し、
`rendereye-mcp service stop`の後にエージェントを再起動してください。

**レイヤーの見分け方**

- エージェントがサーバーを起動できない → 設定 / MCPレイヤー
- `no_renderdoc_connected` → 拡張機能またはIPCレイヤー
- `no_capture_loaded`、`shader_not_bound`、`resource_not_found` → Captureについての
  通常の回答
- `extension_error`、`unsupported`、`timeout` → RenderDoc内部のリプレイレイヤー

**バグ報告に含めてほしいもの:** OSのバージョン、RenderDocのバージョン、
`rendereye-mcp --version`、コーディングエージェントとそのバージョン、CaptureのGraphics API、
`rendereye-mcp doctor`の出力、失敗したプロンプトまたはTool呼び出しとその結果、関連する
ログの抜粋。

## セキュリティとプライバシー

Captureやログには、アプリケーションのパス、リソース名やShader名、Shaderソース、
未発表コンテンツの描画結果が含まれることがあります。共有する前に内容を確認し、機密情報を
取り除いてください。権限のないまま、プロプライエタリなCaptureを公開Issueに添付しないで
ください。IPCサービスは`127.0.0.1`でのみ待ち受け、起動ごとのトークンを要求します。
他のマシンに公開しないでください。
