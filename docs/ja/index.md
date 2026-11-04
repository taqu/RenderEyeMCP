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

## よく使うデバッグシナリオ

| シナリオ | こんなときに |
|----------|------------|
| [開いているCaptureを調べる](examples/active-capture.md) | 最初の確認: Capture、API、Eventの把握 |
| [オブジェクトが表示されない](examples/missing-object.md) | DrawCallが実行されているのに何も表示されない |
| [メッシュ・ジオメトリが消えている](examples/missing-mesh.md) | 頂点は送られているのにメッシュが表示されないか変形している |
| [シェーダーのデバッグ](examples/shader-debugging.md) | シェーダーが間違った値を読んでいるか、予期しない出力を生成している |
| [GPUパフォーマンスのボトルネック](examples/gpu-bottleneck.md) | GPUに時間がかかっている; どこで時間を使っているか特定する |
| [Pixel Historyの調査](examples/pixel-history.md) | Pixelの色がおかしい; 書き込み履歴を追う |

すべてのシナリオは[デバッグシナリオ一覧](examples/README.md)を参照してください。

## リファレンス

| ドキュメント | 内容 |
|------------|------|
| [MCP Tool](tools.md) | パラメータと戻り値を含む完全なToolリファレンス |
| [アーキテクチャ](architecture.md) | RenderEyeMCPの内部構造 |
| [トラブルシューティング](troubleshooting.md) | よくある問題と解決方法 |
| [高度なデバッグ](advanced-debugging.md) | マルチステップのデバッグワークフロー |
| [GPUパフォーマンス分析](performance.md) | GPUカウンターの収集とプロファイリングガイド |
