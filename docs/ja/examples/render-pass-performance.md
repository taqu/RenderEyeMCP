[English](../../en/examples/render-pass-performance.md) | [日本語](render-pass-performance.md)

# シナリオP2 — レンダーパスごとのGPUコストを比較する

## 問題

Shadow、GBuffer、Lighting、PostProcessなど、複数のレンダーパスのGPUコストを比較して、
どのパスが最も重いかを把握したい状況です。

## 準備

1. RenderEyeMCP拡張機能を有効にしたRenderDocが起動している。
2. 対象のCaptureがロード済みである。エンジン側でデバッグマーカー(`PIXBeginEvent`、
   `vkCmdBeginDebugUtilsLabelEXT`など)が設定されていると、階層構造で集計できます。
   Eventリストにマーカーエントリがあるか確認してください。

## プロンプト例

**クイック調査:**
> Shadow、GBuffer、Lighting、PostProcessの各レンダーパスのGPUコストを比較してください。
> どのパスが最も重く、そのパス内の個別EventのタイミングはどうなっているかをEvent名と
> 時間とともに教えてください。

**詳細な調査:**
> このCaptureのGPU時間を計測し、名前付き各レンダーパスのコストを比較してください。
> 各パスの集計GPU時間、Event数、全体に占める割合を報告してください。最もコストの高い
> パスについては、内部のEventをコスト順にソートして一覧し、そのパス内で最もコストが高い
> 単一のEventを特定してください。

## 調査内容

- 全EventのGPU時間を計測し、デバッグマーカーグループを使ってレンダーパスごとに集計する
- 各パス: 名前、集計された合計時間、Event数、全体に占める割合
- 最もコストの高いパス: そのパス内の個別Eventをコスト順にソートして支配的なEventを特定する

## 期待される結果

Deferredレンダラーの典型的な結果: Lighting 42.6%、GBuffer 33.0%、PostProcessing 14.7%、
ShadowMap 7.6%。Lightingパス内では、Deferred Lighting Compute Dispatchだけでそのパスの
時間の71%を占めることもあります。

## `aggregated_duration` の意味

`aggregated_duration`は**パスグループ内の葉EventのGPU時間の合計**であり、そのパスの
GPUウォールクロック経過時間ではありません。この違いが重要になる2つのケース:

- **イベントのオーバーラップ**: タイルGPUや非同期対応GPUでは、パス内のEventがハードウェア上で
  オーバーラップする場合があります。それらを合算すると実際の経過時間を過大評価します。
- **カウンター値の欠損**: パス内のEventの一部がカウンター結果を生成しなかった場合、それらのEventは
  欠損(ゼロではない)として扱われます。この場合、集計値は過小評価になります。

非同期コンピュートなしのD3D12またはVulkanのほとんどのデスクトップGPUキャプチャでは、
葉の合計はほぼ経過時間に近い値になります。

- LightingパスとGBufferパスがDeferredレンダラーでは通常支配的です。
- 単一のコンピュートDispatchがLightingパスのコストの大部分を占めることが多いです。
- PostProcessingパスは通常速いですが、フルレゾリューションのブラーチェーンやレイトレーシングを
  含む場合は重くなります。
- Shadowパスはカスケードを積極的にカリングしていれば速いですが、シャドウキャスティングライトが
  多い場合はスパイクします。

## 制限事項

- パスのグループ化はCaptureのデバッグマーカーに依存します。アプリケーションが
  `BeginEvent`/`EndEvent`を発行していない場合、全Eventがトップレベルに表示され、
  パスレベルのパフォーマンスはフラットなリストを返します。
- `aggregated_duration`はウォールクロックパス経過時間ではありません(上記を参照)。
- 計測されたEventが0件のパス(パスは実行したが全Eventでカウンターデータが欠損している場合)は
  結果に表示されません。

## 関連ツール

`list_gpu_counters`、`collect_gpu_counters`、`get_gpu_measurement_status`、
`get_render_pass_performance`、`get_gpu_timings` —
[パフォーマンス分析ガイド](../performance.md)および
[Toolリファレンス](../tools.md#gpuパフォーマンス分析)を参照。
