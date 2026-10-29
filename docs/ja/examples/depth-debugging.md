[English](../../en/examples/depth-debugging.md) | [日本語](depth-debugging.md)

# シナリオE — 深度テストの問題

## 問題

手前にあるはずのオブジェクトが奥のものに隠れる、ちらつく(Z-fighting)、特定の視点でだけ
消える、といった症状です。

## 準備

誤って隠れているオブジェクトのDrawCallを選択します。

## プロンプト例

> 選択中のDrawCallの深度の状態と、関連するDepth Textureを調べてください。深度比較関数、
> 深度書き込み、関係する深度のPixel値を確認してください。

比較関数と深度書き込みは**取得できない**ため(制限を参照)、エージェントはそのことを
伝えるはずです。それ以外の確認でも有用な根拠が得られます。

## 調査の流れ

1. `get_pipeline_state`の`depth_stencil` — Depth/Stencilステートは取得できない旨の
   注意書きが返る。
2. `get_render_targets`(または`output_merger`) — BindされたDepthターゲット:
   `resource_id`、フォーマット(`D32_FLOAT`、`R32_TYPELESS`など)、サイズ。
3. `get_pipeline_state`の`rasterizer` — Viewportの`min_depth`/`max_depth`。
4. Depthターゲットに`get_texture_statistics` — 深度の全体的な範囲。
5. オブジェクト上とその周囲の点を`coords`に指定して`get_pixel_value`。

## 確認できること

- ColorターゲットやViewportとサイズが一致する(または一致しない)Depthターゲット。
- Viewportの深度範囲。通常は`0.0 – 1.0`。
- 深度の統計値。例: `min 0.0, max 0.025` — Reversed-Zでよく見られる狭い範囲。
- 特定のPixelの深度値。例: オブジェクト中央で`0.00107`。

## 解釈

- 深度テストを前提とするオブジェクトなのに**Depthターゲットが未Bind** → パスの
  設定ミス。
- DepthターゲットとColorターゲット/Viewportの**サイズ不一致** → 間違った領域に対して
  深度テストしている。
- **Viewportの深度範囲**が`0..1`ではない(`0..0`など) → すべてが同じ深度になる。
- **深度値と規約:** Reversed-Z(手前 = 1、奥 = 0)ではシーンの大半が0付近になります。
  あなたの規約に照らして、オブジェクトの値が遮蔽物の値の「間違った側」にあるなら、
  比較関数か射影行列が有力な原因です。比較関数はRenderDocのPipeline Stateパネルで
  確認してください。
- 選択中のEventで読む深度値には、それ以前のDrawの結果がすでに含まれています。この
  Drawが何に対してテストするかを見るには、直前のEventを選択してください。

特定のフラグメントがなぜ棄却されたかを正確に突き止めるには、Pixel HistoryかShader
デバッグが必要ですが、RenderEyeMCPにはありません。最後の確認にはRenderDocのPixel
Historyを使ってください。

## 制限

- 深度比較関数、深度書き込みの有効/無効、Stencil、Depth Boundsのステートは取得
  できません(RenderDocのAPI共通インターフェースが提供していないため)。
- Pixel Historyは未実装です。
- Typelessの深度フォーマット(`R32_TYPELESS`)は格納されたまま報告されます。32ビット
  floatの深度では、`float`チャンネルに深度値が入っています。

## 関連Tool

`get_pipeline_state`、`get_render_targets`、`get_texture_info`、
`get_texture_statistics`、`get_pixel_value` — [Toolリファレンス](../tools.md)を参照。
