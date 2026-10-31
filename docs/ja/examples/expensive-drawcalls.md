[English](../../en/examples/expensive-drawcalls.md) | [日本語](expensive-drawcalls.md)

# シナリオP1 — 最もコストの高いDrawCallを特定する

## 問題

特定のFrameでGPU時間がかかりすぎています。どのDrawCallがボトルネックになっているかを
特定し、パイプラインの設定に問題がないか確認したい状況です。

## 準備

1. RenderEyeMCP拡張機能を有効にしたRenderDocが起動している。
2. 対象のCaptureがロード済みである。

## プロンプト例

**クイック調査:**
> このCaptureで最もGPU時間を消費しているDrawCallを上位10件挙げてください。
> 最もコストの高いDrawCallのパイプライン設定、Shader、Render Targetを調べてください。

**詳細な調査:**
> このCaptureの全EventのGPU時間を計測し、最もコストの高いDrawCallを上位10件、
> EventのID・名前・時間・全体に占める割合とともに一覧してください。最もコストの高い
> DrawCallについて、パイプライン統計を収集し、VertexおよびPixel Shaderを特定し、
> バインドされたRender Target(フォーマット、解像度、サンプル数)を調べ、Pixel Shaderの
> Textureバインディングを一覧してください。確認できた事実と、コストが高い理由の仮説を
> 分けて報告してください。

## 調査内容

- 全EventのGPU時間を計測してランキングし、コスト上位10件を特定する
- 最もコストの高いDrawCallのパイプラインステートを確認: DrawCount、Topology、ラスタライザ設定
- バインドされているVertex ShaderとPixel Shaderのエントリポイントを特定する
- そのDrawでバインドされているRender Target: フォーマット、解像度、MSAAサンプル数
- 利用可能な場合はパイプライン統計を収集: 頂点呼び出し数、PS呼び出し数、ラスタライズされたプリミティブ数

## 期待される結果

通常、1〜2件のEventがGPU時間の大半を占めます。オープンワールドや屋外シーンではGround、
密な植生、またはキャラクターバッチがよく上位に来ます。最もコストの高いEventは通常G-bufferか
シャドウパスに含まれます。Render Targetの解像度とMSAAサンプル数だけで、Shader分析なしに
コストの大部分を説明できることが多いです。

## 結果の解釈

- テレインDrawCallで`percent_of_total: 23.0`なら、テレインがGPUの主なコスト要因です。
- Pixel Shader呼び出し数が表示可能なPixel数よりはるかに多い場合、オーバードローや画面外の
  多くのPixelを生成する大きなトライアングル数が原因の可能性があります。
- 4×MSAAの高解像度Render Targetは1×に比べてPixel Shaderの処理量を4倍にします。
- 高呼び出し回数のDrawCallで複雑なPixel Shader(多数のTexture Sample、ライティングの繰り返し)は
  古典的なボトルネックです。命令数については逆アセンブルを確認してください。
- GPU時間はリプレイベースです。キャプチャ時とリプレイ時のサーマル状態が異なる場合、
  絶対値はライブアプリケーションの計測値とわずかに異なる場合があります。
- 10件未満しか返ってこない場合、一部のEventはカウンターに記録されていません(欠損はゼロではなく省略されます)。

## 制限事項

- GPU時間はリプレイベースです。キャプチャ時とリプレイ時のサーマル状態の違いにより、
  絶対値がライブアプリケーションの計測値とわずかに異なる場合があります。
- 10件未満しか返ってこない場合、一部のEventはカウンターに記録されていません
  (欠損値はゼロではなく省略されます)。

## 関連ツール

`get_current_capture`、`list_gpu_counters`、`collect_gpu_counters`、
`get_gpu_measurement_status`、`get_performance_summary`、`get_pipeline_state`、
`get_current_shaders`、`get_render_targets`、`get_pipeline_statistics` —
[パフォーマンス分析ガイド](../performance.md)および
[Toolリファレンス](../tools.md#gpuパフォーマンス分析)を参照。
