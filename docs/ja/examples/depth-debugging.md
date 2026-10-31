[English](../../en/examples/depth-debugging.md) | [日本語](depth-debugging.md)

# シナリオE — 深度テストの問題

## 問題

手前にあるはずのオブジェクトが奥のものに隠れる、ちらつく(Z-fighting)、特定の視点でだけ
消える、といった症状です。

## 準備

誤って隠れているオブジェクトのDrawCallを選択します。

## プロンプト例

**クイック調査:**
> 選択中のDrawCallの深度の状態と、関連するDepth Textureを調べてください。深度比較関数、
> 深度書き込み、関係する深度のPixel値を確認してください。

比較関数と深度書き込みは**取得できない**ため(制限事項を参照)、エージェントはそのことを
伝えるはずです。それ以外の確認でも有用な根拠が得られます。

**詳細な調査:**
> 選択中のオブジェクトが他のジオメトリの前にあるはずなのに表示されていません。
> バインドされているDepth Render Targetを調べてください: フォーマット、サイズ、
> Color TargetおよびViewportと一致しているか確認してください。ViewportのDepth範囲を
> 読んでください。オブジェクト上とその周囲の複数のPixel座標で深度値をサンプリングし、
> Reversed-Zか標準深度規約と一致しているか説明してください。オブジェクトが棄却されている
> 可能性のある異常を特定してください。

## 調査内容

- バインドされているDepth Render Target: リソースID、フォーマット(D32_FLOATやR32_TYPELESSなど)、Color TargetおよびViewportと次元が一致しているか
- Viewportの深度範囲(min_depthとmax_depth)
- Depth Target全体の深度統計 — 存在する最小・最大深度値
- オブジェクト上とその周囲の特定のPixel座標でサンプリングした深度値

## 期待される結果

- Color TargetやViewportとサイズが一致する(または一致しない)Depth Target
- Viewportの深度範囲。通常は`0.0 – 1.0`
- 深度統計値。例: `min 0.0, max 0.025` — Reversed-Zでよく見られる狭い範囲
- 特定のPixelの深度値。例: オブジェクト中央で`0.00107`

## 結果の解釈

- 深度テストを前提とするオブジェクトなのに**Depth Targetが未Bind** → パスの設定ミス。
- Depth TargetとColor Target/Viewportの**サイズ不一致** → 間違った領域に対して
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

## 制限事項

- 深度比較関数、深度書き込みの有効/無効、Stencil、Depth Boundsのステートは取得
  できません(RenderDocのAPI共通インターフェースが提供していないため)。
- Pixel Historyは未実装です。
- Typelessの深度フォーマット(`R32_TYPELESS`)は格納されたまま報告されます。32ビット
  floatの深度では、`float`チャンネルに深度値が入っています。

## 関連ツール

`get_pipeline_state`、`get_render_targets`、`get_texture_info`、
`get_texture_statistics`、`get_pixel_value` — [Toolリファレンス](../tools.md)を参照。
