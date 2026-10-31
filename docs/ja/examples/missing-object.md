[English](../../en/examples/missing-object.md) | [日本語](missing-object.md)

# シナリオB — オブジェクトが表示されない

## 問題

Frameに表示されるはずのオブジェクトが見当たりません。

## 準備

1. そのオブジェクトを描画するはずのDrawCallを探します(Event Browserでマーカー名や
   メッシュ名を検索します。*Texture Viewer → Overlay → Highlight Drawcall*も便利です)。
2. そのDrawCallを選択します。オブジェクトのDrawCallがどこにも見つからない場合、問題は
   このFrameのPipelineではなく、もっと手前(エンジン側のカリングや描画登録)にあります。

## プロンプト例

**クイック調査:**
> このオブジェクトがFrameに表示されません。選択中のDrawCallについて、頂点入力、Shader、
> ラスタライザの状態、深度の状態、Render Targetを調べ、怪しい設定を挙げてください。
> 確認できた事実と、考えられる原因は分けて書いてください。

**詳細な調査:**
> 選択中のDrawCallが表示されるはずのオブジェクトを描画していません。パイプラインの各ステージを
> 系統的に調べてください: DrawがゼロでないVertex/Index数を送信しているか確認し、頂点バッファの
> バインドとStrideを確認し、ViewportとScissorが期待する画面領域を覆っているか確認し、バインドされた
> Render Targetをフォーマットとサイズとともに一覧し、Shader Reflectionの不一致を特定してください。
> 各疑わしい発見について、確認済みか考えられる原因かを明記してください。

## 調査内容

- DrawCallがジオメトリを送信しているか(Index数、Vertex数、Instance数)
- Vertex BufferとIndex Bufferのバインディング: バインドされているかとStrideの確認
- Vertex Shaderが期待する入力属性とPipelineで宣言されているものの比較
- ViewportとScissor: ゼロ以外でオブジェクトが表示されるはずの領域を覆っているか
- Render Target: どのColorおよびDepth Targetがバインドされているか、サイズとフォーマット

## 期待される結果

| 確認項目 | 怪しい値 |
|----------|----------|
| `num_indices` / `num_instances` | 0 |
| Topology | メッシュに合わない(`TriangleList`のはずが`LineList`など) |
| Vertex Buffer | ない、Strideが頂点レイアウトと違う、オフセットが想定外 |
| Viewport/Scissor | サイズ0、オブジェクトがあるはずの領域を覆っていない |
| Render Target | 何もBindされていない、想定外のターゲット、Viewportとサイズが合わない |
| デコードした座標 | すべて0、NaN、極端に大きい |

## 結果の解釈

- Viewport/Scissorのサイズが0、インスタンス数が0、Render Targetが未Bind — これらは
  表示されない理由を直接説明する**確認済みの事実**です。
- Strideの不一致や想定外のTopologyは有力な**原因候補**です。エンジンの頂点レイアウトを
  確認してください。
- すべてもっともらしく見える場合、原因はRenderEyeMCPでは見えない状態(カリング、
  深度テスト、ブレンド)か、変換行列にある可能性が高いです。
  [シナリオE](depth-debugging.md)に進み、Constant Bufferも調べてください
  ([シナリオC](shader-resources.md))。

DrawCall 1つだけで、表示されない*理由*を証明できることはまれです。結果は診断ではなく、
事実と手がかりの一覧として扱ってください。

## 制限事項

- Cullモード、Fillモード、Depth/Stencilステート、Blendステートは取得**できません**。
  RenderDocのPipeline Stateパネルで確認してください。
- 頂点入力レイアウト(属性のフォーマットとオフセット)は取得できません。Shaderが何を
  期待しているかは、Vertex Shaderの入力シグネチャでわかります。
- 頂点変換後のジオメトリ(Mesh Viewerの出力)は取得できません。

## 関連ツール

`get_selected_event`、`get_pipeline_state`、`list_shaders`、`get_shader_reflection`、
`get_render_targets`、`read_buffer_data`、`get_texture_image` —
[Toolリファレンス](../tools.md)を参照。
