[English](../../en/examples/README.md) | [日本語](README.md)

# デバッグシナリオ

各シナリオは目に見える描画の問題から出発し、コーディングエージェントにそのまま貼り付けられる
自然言語プロンプトを提供します。RenderDocでCaptureを開き、準備ステップに従い、
プロンプト例をClaude Code、Codexや他のMCP対応エージェントに貼り付けてください。
RenderEyeMCPがCaptureデータへのアクセスを自動的に提供します。

## 基本的な調査

| シナリオ | こんなときに |
|----------|--------------|
| [A. 開いているCaptureを調べる](active-capture.md) | 最初の一歩: どのCapture、どのAPI、どのEventが選択されているか |

## オブジェクトが表示されない・見えない

| シナリオ | こんなときに |
|----------|--------------|
| [B. オブジェクトが表示されない](missing-object.md) | DrawCallはあるはずなのに何も表示されない |
| [G1. メッシュが表示されない](missing-mesh.md) | DrawCallは存在するがメッシュが見えない; 頂点データと変換を確認 |

## 色やTextureがおかしい

| シナリオ | こんなときに |
|----------|--------------|
| [C. Textureやマテリアルの値がおかしい](shader-resources.md) | マテリアルが違うTextureを使っている、定数が想定外 |
| [D. Render Targetが黒い/色がおかしい](render-target.md) | ターゲットが真っ黒、飽和している、色が想定外 |
| [D1. ピクセルの色が間違っている](pixel-history.md) | 特定のPixelが間違った色を表示している; どのDrawが原因か追跡 |
| [D2. ピクセルシェーダーデバッグ](shader-debugging.md) | Pixel Historyでフラグメントが1つなのにShaderの出力がおかしい |

## 深度とジオメトリ

| シナリオ | こんなときに |
|----------|--------------|
| [E. 深度テストの問題](depth-debugging.md) | オブジェクトが消える、誤って隠れる |
| [D3. 深度テスト棄却](depth-rejection.md) | フラグメントは存在するが常に深度テストで棄却される |
| [G2. 頂点フォーマットの不一致](vertex-layout.md) | ジオメトリが歪んでいる; 頂点レイアウトのミスマッチが疑われる |
| [G3. 頂点変換の調査](post-vs-inspection.md) | オブジェクトが間違った位置に表示される、予期しないクリッピングが発生 |
| [D4. 頂点シェーダーデバッグ](vertex-debugging.md) | 頂点シェーダーをステップ実行して間違った行列や変換を見つける |

## パフォーマンス

| シナリオ | こんなときに |
|----------|--------------|
| [P1. 最もコストの高いDrawCallを特定する](expensive-drawcalls.md) | どのDrawCallがGPUフレーム時間を支配しているか特定する |
| [P2. レンダーパスのGPUコストを比較する](render-pass-performance.md) | Shadow、GBuffer、Lighting、PostProcessのパスコストを比較する |
| [P3. 最もコストの高いコンピュートDispatch](compute-performance.md) | コストの高いコンピュートDispatchを特定・分析する |
| [P4. GPUボトルネックを診断する](gpu-bottleneck.md) | コストの高いDrawCallをパイプライン統計とBindingで深く分析する |
| [G4. ジオメトリとパフォーマンス](geometry-performance.md) | DrawCallのコストが過剰なジオメトリから来ているか確認する |

## 高度なデバッグ

| シナリオ | こんなときに |
|----------|--------------|
| [F. Compute Shaderの出力がおかしい](compute-dispatch.md) | DispatchがGarbage値・ゼロ・途中までしか埋まっていないBufferを書き込む |
| [D5. コンピュートシェーダーのNaN](compute-debugging.md) | コンピュートパスがNaN/Infを生成して下流の結果を破壊している |
| [G1. メッシュが表示されない](missing-mesh.md) | 頂点・インデックスデータ、ジオメトリ統計、Post-VS位置を調査する |

**注意:** シナリオはコーディングエージェントを使ったグラフィクスの問題解決の考え方を示すガイドです。
1回のエージェントセッションをそのまま記録したものではなく、エージェントが出した結論は
必ずあなた自身で確認してください。
