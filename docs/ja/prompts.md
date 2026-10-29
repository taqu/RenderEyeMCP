[English](../en/prompts.md) | [日本語](prompts.md)

# プロンプト例

調べたい内容ごとに、そのまま使えるプロンプトをまとめました。どれも**RenderDocで選択中の**
CaptureとEventを対象にするので、先に正しいEventを選択しておいてください。

## 良いプロンプトの条件

- **観察した症状**を書く(「キャラクターが表示されない」「ターゲットが真っ黒」など)
- IDを推測させず、RenderDocで**選択中の**Eventを指す
- 値、Binding、フォーマットなどの**根拠**を求める
- 原因を決めつけ**ない**
- Toolにできないこと(Pixel History、Shaderのステップ実行、プロファイリング、選択の
  変更)を頼ま**ない**

どのプロンプトにも「観察した事実と推測を分けて書いてください。」と添えると効果的です。

## 接続の確認

> RenderDocセッションを一覧表示してください。

> RenderDocで今読み込まれているCaptureは何ですか?

> 選択中のDrawCallとそのPipeline Stateを見せてください。

## 全般的な調査

> RenderDocで現在選択しているDrawCallを調査し、重要なPipeline Stateをまとめてください。

## Resource Binding

> 現在選択しているPixel ShaderにBindされているTextureとBufferを確認し、未設定のBindingが
> ないか調べてください。

## Constant Buffer

> 現在選択しているDrawCallで使用されているConstant Bufferを調査し、変換行列とMaterial
> Parameterの値を確認してください。

(エージェントは、変数名とオフセットを`get_shader_reflection`で、値を`read_buffer_data`で
取得して組み合わせます。)

## Render Target

> 現在のRender Targetを表示し、問題がある領域のPixel値を調べてください。

座標がわかっていれば添えてください。「…x=640, y=360の周辺です。」

## Compute Dispatch

> 現在選択しているCompute Dispatchを調査し、出力Bufferの値を確認してください。

## Captureの中を探す

> このCaptureのDispatchを、スレッドグループ数と一緒に一覧表示してください。

> 最初の50個のDrawCallを一覧し、インデックス数が10,000を超えるものを教えてください。

## (まだ)うまくいかない依頼

| 依頼 | 理由 |
|------|------|
| 「Event 1200を選択して調べてください。」 | RenderEyeMCPは選択を変更しない。RenderDocで選択する |
| 「(100, 200)のPixel Historyを見せてください。」 | Pixel Historyは未実装 |
| 「このPixelでPixel Shaderをステップ実行してください。」 | Shaderデバッグは未実装 |
| 「一番遅いパスはどれですか?」 | GPUの計測/プロファイリング用Toolはない |
| 「深度比較関数は何ですか?」 | Depth/Stencilステートは取得できない |
