[English](../../en/examples/render-target.md) | [日本語](render-target.md)

# シナリオD — Render Targetが黒い/色がおかしい

## 問題

Render Targetが真っ黒に見える、飽和している、または想定外の色になっています。

## 準備

そのターゲットに書き込むDrawCall(または怪しいパスの最後のDraw)を選択します。

## プロンプト例

> 選択中のDrawCallにBindされているRender Targetを調べてください。内容を表示し、
> フォーマットとサイズを確認して、代表的なPixel値を調べてください。

## 調査の流れ

1. `get_render_targets` — BindされたColorターゲットとDepthターゲット: `resource_id`、
   サイズ、フォーマット、Mip/Slice。
2. `get_texture_statistics` — ターゲットのチャンネルごとの最小/最大値(必要なら
   `hist_min`/`hist_max`を想定範囲に合わせてヒストグラムも)。
3. `get_pixel_value`をいくつかの`coords`で(中央、四隅、内容があるはずの点。1回16点まで)。
4. `get_texture_image` — PNGプレビュー。`max_dim`はTextureの最大辺以上にします
   (エラーが`required_max_dim`を教えてくれます)。

## 確認できること

- フォーマットとサイズ。例: `R16G16B16A16_FLOAT`、1920×1080。
- `max.float = [0.0, 0.0, 0.0, 1.0]`(本当に色が空)や、
  `max.float = [24.3, 18.1, 9.7, 1.0]`(1.0を大きく超えるHDR値)といった統計値。
- `float`、`uint`、`sint`の各形式での正確なPixel値。

## 解釈

**画像が黒いからといって、値が0とは限りません。**

- floatのターゲット(HDR、ライティングバッファ)は、1.0をはるかに超える値や0に近い
  小さな値を持つことがよくあります。表示の変換によって白や黒に見えることがあるので、
  判断にはプレビューではなく統計値とPixel値を使ってください。
- 整数のターゲット(`R32_UINT`のID、`R8_UINT`のマスク)に入っているのは色ではなく数値です。
  プレビューには意味がないので、`uint`の値を読んでください。
- 全チャンネルでmin = max = 0なら、選択中のEvent(またはそれ以前)で何も書かれていません。
  Draw自体(シナリオB)、ブレンド、正しいターゲットがBindされているかを確認してください。
- NaN/Inf(結果では`"nan"`/`"inf"`)はポストプロセスで伝播し、画面全体が黒くなる原因に
  なりがちです。
- 内容は選択中のEvent時点のものです。後の書き込みを見るには後のEventを選択してください。

## 制限

- PNGは1つのMip/SliceをRenderDocが表示用に変換したもので、正確なデータではありません。
- 大きなTextureのPNGは大きくなり、結果は16 MiBに収まる必要があります。
  `result_too_large`になったら小さいMipを使ってください。
- MSAA: `get_pixel_value`は`sample`インデックスを受け取ります。画像と統計値は
  RenderDocの既定のresolve動作に従います。
- Pixel History(どのDrawがそのPixelを書いたか)は未実装です。

## 関連Tool

`get_render_targets`、`get_texture_info`、`get_texture_statistics`、`get_pixel_value`、
`get_texture_image` —
[Render Target、Texture、Pixel](../tools.md#render-targettexturepixel)を参照。
