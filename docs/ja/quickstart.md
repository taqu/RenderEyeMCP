[English](../en/quickstart.md) | [日本語](quickstart.md)

# クイックスタート: RenderDocで開いているCaptureを調べる

RenderEyeMCPのインストールが済んでいれば、5分ほどで試せます。ここで紹介するのは
メインの使い方です。いつもどおりRenderDocでCaptureを開き、それをエージェントが調べます。
エージェントがCaptureを開いたり、開き直したりすることはありません。

## 1. インストールしてエージェントを接続する

[インストール](installation.md)と[設定](configuration.md)の手順に従ってください。
次の状態になっていればOKです。

- `rendereye-mcp doctor`に`✗`の行がない
- RenderDocでRenderEyeMCP拡張機能が有効(**Tools → Manage Extensions**、*Always Load*)
- Claude CodeまたはCodexが設定済みで、再起動してある

## 2. RenderDocを起動してCaptureを開く

次のどの方法でも構いません。

- *File → Open Capture*で`.rdc`ファイルを選ぶ
- Unity、Unreal Engine、自作アプリケーションでFrameをキャプチャしてRenderDocで開く
- `.rdc`ファイルをダブルクリックする

## 3. DrawCallを選択する

RenderDocの**Event Browser**で、調べたいオブジェクトを描画しているDrawCall
(たとえば`DrawIndexedInstanced`)をクリックします。*Pipeline State*や
*Texture Viewer*がそのEventの内容に切り替わったことを確認してください。

RenderEyeMCPが調べるのは常に**GUIで選択中のEvent**です。エージェントは選択を変更
できないので、別のEventを見たいときはRenderDocで選択し直してから、もう一度頼んで
ください。

## 4. エージェントに頼む

> RenderDocで今開いているCaptureを調査して、選択中のDrawCallを特定し、
> そのPipeline Stateを要約してください。

## 5. エージェントの動き

エージェントはおおむね次のように動きます(Tool名は参考として示しています。入力する
必要はありません)。

| ステップ | Tool | 確認できること |
|----------|------|----------------|
| RenderDocセッションとCaptureを見つける | `get_current_capture` | `status: loaded`と`.rdc`のパス |
| Captureのメタデータ | `get_current_capture_info` | API(例: `D3D12`)、Frame番号、Event・DrawCall・Dispatchの数 |
| 選択中のEvent | `get_selected_event` | `selected_event_id`とAPI呼び出し名(例: `DrawIndexedInstanced()`) |
| Pipelineの概要 | `get_pipeline_state`(`section: summary`) | Topology、Shaderステージ、Render Target数、Depth Target |
| 必要に応じて詳細 | `get_pipeline_state`(`input_assembly`、`rasterizer`、`output_merger`、`resources`)、`list_shaders`、`get_render_targets` | Buffer、Viewport、ターゲット、Binding |

最後にエージェントが要約します。良い要約は、**観察した事実**(Toolが返した値)と、
それが何を意味するかという**仮説**を分けて書いています。

## 6. 結果の読み方

- **リソースID**は`ResourceId::805`のような形式です。今開いているCaptureの中でのみ
  有効で、Captureを開き直したり切り替えたりすると変わることがあります。
- **Event ID**(EID)はRenderDocのEvent Browserに表示される番号と同じです。
- `depth_stencil`はステートの代わりに注意書きを返します。深度比較関数や深度書き込みの
  フラグは、RenderDocのAPI共通インターフェースでは取得できません。Bindされている
  Depth *Target*は`output_merger`と`get_render_targets`で確認できます。
- ViewportとScissorの配列には全スロットが含まれます。使っていないスロットはサイズ0です。

## 次のステップ

- [デバッグシナリオ](examples/README.md)を試す
- [プロンプト例](prompts.md)からコピーして使う
- [MCP Toolリファレンス](tools.md)でパラメーターを調べる

## 検証状況

この流れは、Windows 11上のRenderDoc 1.46でD3D12 Captureを使い、MCP stdioサーバー
経由で実行しました(38個のToolを認識。DrawCallを選択した状態で`get_current_capture`、
`get_current_capture_info`、`get_selected_event`、`get_pipeline_state`の全セクション、
`list_shaders`、`get_render_targets`がデータを返しました)。Eventの選択はRenderDocの
Python APIで行いました。それ以前の手動テストでは、GUIでDrawCallをクリックした後も
拡張機能が読み込み直後のEventを返し続けたことが1回あり、現在調査中です
([リリース準備状況](../release_readiness.md)、英語)。エージェントが選択したものと
違うEventを報告する場合は、
[トラブルシューティング](troubleshooting.md#エージェントが選択したものと違うeventを報告する)
を参照してください。
