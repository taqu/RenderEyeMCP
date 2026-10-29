[English](../../en/examples/README.md) | [日本語](README.md)

# デバッグシナリオ

各シナリオは描画の問題から出発し、コーディングエージェントとRenderEyeMCPでどう調べるかを
示します。どれも同じ構成です: 問題 → 準備 → プロンプト例 → 調査の流れ → 確認できること →
解釈 → 制限 → 関連Tool。

| シナリオ | こんなときに |
|----------|--------------|
| [A. 開いているCaptureを調べる](active-capture.md) | 最初の一歩: どのCapture、どのAPI、どのEventか |
| [B. オブジェクトが表示されない](missing-object.md) | 何かを描画するはずのDrawCallなのに何も表示されない |
| [C. Textureやマテリアルの値がおかしい](shader-resources.md) | マテリアルが違うTextureを使っている、定数が想定外 |
| [D. Render Targetが黒い/色がおかしい](render-target.md) | ターゲットが真っ黒、飽和している、色が想定外 |
| [E. 深度テストの問題](depth-debugging.md) | オブジェクトが消える、誤って隠れる |
| [F. Compute Shaderの出力がおかしい](compute-dispatch.md) | Dispatchが想定外の結果を書き込む |

**検証状況。** すべてのシナリオで使うToolは、Windows 11上のRenderDoc 1.46で実際のD3D12
Captureに対して実行済みです。シナリオ自体は考え方のガイドであり、1回のエージェント
セッションをそのまま記録したものではありません。エージェントが出した結論は、必ず
あなた自身で確認してください。
