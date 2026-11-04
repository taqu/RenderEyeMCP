[English](../en/index.md) | [日本語](index.md)

# RenderEyeMCP

**RenderDocで開いているCaptureを、そのままAIコーディングエージェントに調べてもらう。**

RenderEyeMCPは、Claude CodeやCodexなどのAIコーディングエージェントと
[RenderDoc](https://renderdoc.org/) GUIをつなぐ
[Model Context Protocol](https://modelcontextprotocol.io/)(MCP)サーバーです。
Frameのキャプチャやリプレイは、これまでどおりRenderDocで行います。
エージェントはRenderDocが表示している内容(読み込み中のCapture、選択中のEvent、
Pipeline State、Shader、Bindされたリソース、Buffer、Render Target、Pixel値)を読み取ります。

RenderDocを日常的に使うグラフィックス/エンジンプログラマーが、描画バグの調査で
エージェントに証拠集めを手伝ってもらうためのツールです。

## はじめに

| ガイド | 内容 |
|--------|------|
| [クイックスタート](quickstart.md) | 5分でCaptureを調べる |
| [インストール](installation.md) | WindowsまたはLinuxへのセットアップ |
| [設定](configuration.md) | Claude Code、Codex、他のエージェントを接続する |

## グラフィックスデバッグのユースケース

各シナリオは実際の描画の問題から出発しています。プロンプトのテンプレートとして使うか、
自分の調査を組み立てる際の参考にしてください。すべてのシナリオの一覧と使いどころは
[シナリオ一覧](examples/README.md)を参照してください。

### Captureとイベントの確認

- [開いているCaptureを調べる](examples/active-capture.md)
  — エージェントがRenderDocで開いているCaptureを読み取れることを確認し、API・Frame・選択中のEventを把握する。

### 表示されない・おかしいレンダリング

- [オブジェクトが表示されない](examples/missing-object.md)
  — DrawCallが実行されているのに画面に何も表示されない。
- [メッシュが表示されない](examples/missing-mesh.md)
  — 頂点は送られているのにメッシュが見えないか変形している; 頂点データと変換後の位置を確認する。
- [Textureやマテリアルの値がおかしい](examples/shader-resources.md)
  — マテリアルに違うTextureやデフォルトのTexture、想定外の定数値が使われている。
- [Render Targetが黒い・色がおかしい](examples/render-target.md)
  — Render Targetが真っ黒、飽和している、または想定外の色になっている。

### Render Target・Pixel・深度

- [Pixelの色が間違っている](examples/pixel-history.md)
  — 特定のPixelの書き込み履歴を追って、最後に変更したDrawCallと原因を特定する。
- [深度テストの問題](examples/depth-debugging.md)
  — 手前にあるはずのオブジェクトが奥に隠れたり、ちらついたりしている(Z-fighting)。
- [深度テスト棄却](examples/depth-rejection.md)
  — Pixel Historyではフラグメントが存在しているが、深度テストで常に棄却されている。

### Shaderのデバッグ

- [ピクセルシェーダーのデバッグ](examples/shader-debugging.md)
  — 問題のPixelに触れるフラグメントが1つだけ; Pixel Shader内部のバグを追う。
- [頂点シェーダーのデバッグ](examples/vertex-debugging.md)
  — 変換後にメッシュの頂点が間違った位置に現れる; 頂点シェーダーをステップ実行する。
- [Compute Shaderの出力がおかしい](examples/compute-dispatch.md)
  — Dispatchが想定外の結果(0、ゴミ値、途中までしか埋まっていないBuffer)を書き込む。
- [Compute ShaderのNaN](examples/compute-debugging.md)
  — Compute ShaderがNaNまたはInfを出力し、下流のPixelを破壊している。

### ジオメトリと頂点の検査

- [頂点フォーマットの不一致](examples/vertex-layout.md)
  — ジオメトリが歪んで表示される; 頂点入力レイアウトのミスマッチを疑う。
- [頂点変換の調査](examples/post-vs-inspection.md)
  — オブジェクトが間違った位置に表示されるか予期しないクリッピングが起きる; VS前後の位置を比較する。
- [ジオメトリとパフォーマンス](examples/geometry-performance.md)
  — 重いDrawCallが特定できた; そのコストが過剰なジオメトリに起因するか調べる。

### GPUパフォーマンス分析

- [最もコストの高いDrawCallを特定する](examples/expensive-drawcalls.md)
  — GPU時間でDrawCallを順位付けし、最も重いDrawCallのパイプラインを調べる。
- [Render PassごとのGPUコストを比較する](examples/render-pass-performance.md)
  — Shadow・G-buffer・Lighting・PostProcessのコストを比較してボトルネックのPassを探す。
- [最もコストの高いCompute Dispatchを特定する](examples/compute-performance.md)
  — GPU時間でCompute Dispatchを順位付けし、最上位のShaderを調べる。
- [GPUボトルネックを診断する](examples/gpu-bottleneck.md)
  — 1つのDrawCallのパイプライン統計・Shader・Render Target・リソースBindingを収集して根拠に基づいた仮説を立てる。

## リファレンス

| ドキュメント | 内容 |
|------------|------|
| [MCP Tool](tools.md) | パラメータと戻り値を含む完全なToolリファレンス |
| [アーキテクチャ](architecture.md) | RenderEyeMCPの内部構造 |
| [トラブルシューティング](troubleshooting.md) | よくある問題と解決方法 |
| [高度なデバッグ](advanced-debugging.md) | マルチステップのデバッグワークフロー |
| [GPUパフォーマンス分析](performance.md) | GPUカウンターの収集とプロファイリングガイド |
