[English](../../en/examples/README.md) | [日本語](README.md)

# デバッグシナリオ

各シナリオは描画の問題から出発し、コーディングエージェントとRenderEyeMCPでどう調べるかを
示します。プロンプトはテンプレートとして使い、自分のCaptureに合わせて調整してください。
エージェントの結論は最終答えではなく、あなた自身で確認する証拠として扱ってください。

どのシナリオも同じ構成です:
**問題 → 準備 → プロンプト例 → 調査の流れ → 確認できること → 解釈 → 制限 → 関連Tool。**

**検証状況。** すべてのシナリオで使うToolは、Windows 11上のRenderDoc 1.46で実際のD3D12
Captureに対して実行済みです。シナリオ自体は考え方のガイドであり、1回のエージェント
セッションをそのまま記録したものではありません。

---

## Captureとイベントの確認

| シナリオ | こんなときに |
|----------|--------------|
| [A. 開いているCaptureを調べる](active-capture.md) | 最初の一歩: エージェントがCaptureを読み取れることを確認し、API・Frame・選択Eventを把握する |

---

## 表示されない・おかしいレンダリング

| シナリオ | こんなときに |
|----------|--------------|
| [B. オブジェクトが表示されない](missing-object.md) | DrawCallが実行されているのに画面に何も表示されない |
| [G1. メッシュが表示されない](missing-mesh.md) | 頂点は送られているのにメッシュが見えないか変形している |
| [C. Textureやマテリアルの値がおかしい](shader-resources.md) | マテリアルに違うTextureやデフォルトのTexture、想定外の定数値が使われている |
| [D. Render Targetが黒い・色がおかしい](render-target.md) | Render Targetが真っ黒、飽和している、または想定外の色になっている |

---

## Render Target・Pixel・深度

| シナリオ | こんなときに |
|----------|--------------|
| [D1. Pixelの色が間違っている](pixel-history.md) | Pixelの色がおかしい; 最後に書き込んだDrawCallを追う |
| [E. 深度テストの問題](depth-debugging.md) | 手前にあるはずのオブジェクトが奥に隠れたり、ちらついたりしている(Z-fighting) |
| [D3. 深度テスト棄却](depth-rejection.md) | Pixel Historyではフラグメントが存在しているが、深度テストで常に棄却されている |

---

## Shaderのデバッグ

| シナリオ | こんなときに |
|----------|--------------|
| [D2. ピクセルシェーダーのデバッグ](shader-debugging.md) | 問題のPixelに触れるフラグメントが1つだけ; Pixel Shader内部のバグを追う |
| [D4. 頂点シェーダーのデバッグ](vertex-debugging.md) | 変換後にメッシュの頂点が間違った位置に現れる |
| [F. Compute Shaderの出力がおかしい](compute-dispatch.md) | Dispatchが想定外の結果(0、ゴミ値、途中までしか埋まっていないBuffer)を書き込む |
| [D5. Compute ShaderのNaN](compute-debugging.md) | Compute ShaderがNaNまたはInfを出力し、下流のPixelを破壊している |

---

## ジオメトリと頂点の検査

| シナリオ | こんなときに |
|----------|--------------|
| [G2. 頂点フォーマットの不一致](vertex-layout.md) | ジオメトリが歪んで表示される; 頂点入力レイアウトのミスマッチを疑う |
| [G3. 頂点変換の調査](post-vs-inspection.md) | オブジェクトが間違った位置に表示されるか予期しないクリッピングが起きる; VS前後の位置を比較する |
| [G4. ジオメトリとパフォーマンス](geometry-performance.md) | 重いDrawCallが特定できた; そのコストが過剰なジオメトリに起因するか調べる |

---

## GPUパフォーマンス分析

| シナリオ | こんなときに |
|----------|--------------|
| [P1. 最もコストの高いDrawCallを特定する](expensive-drawcalls.md) | GPU時間でDrawCallを順位付けし、最も重いDrawCallのパイプラインを調べる |
| [P2. Render PassごとのGPUコストを比較する](render-pass-performance.md) | Shadow・G-buffer・Lighting・PostProcessのコストを比較してボトルネックのPassを探す |
| [P3. 最もコストの高いCompute Dispatchを特定する](compute-performance.md) | GPU時間でCompute Dispatchを順位付けし、最上位のShaderを調べる |
| [P4. GPUボトルネックを診断する](gpu-bottleneck.md) | 1つのDrawCallのパイプライン統計・Shader・Render Target・リソースBindingを収集して根拠に基づいた仮説を立てる |
