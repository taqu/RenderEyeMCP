[English](../../en/examples/compute-performance.md) | [日本語](compute-performance.md)

# シナリオP3 — 最もコストの高いコンピュートディスパッチを特定する

## 問題

コンピュートワークロード(ポストプロセス、物理シミュレーション、カリング、スキニングなど)が
GPU時間を大きく消費しています。どのDispatchが重いか特定し、Shaderとリソースの
Bindingを確認して最適化の手がかりをつかみたい状況です。

## 準備

1. RenderEyeMCP拡張機能を有効にしたRenderDocが起動している。
2. 対象のCaptureがロード済みで、コンピュートDispatchが含まれている。
   Captureの統計でDispatch数を確認する。

## プロンプト例

**クイック調査:**
> このFrameで最もGPU時間を消費しているCompute Dispatchを特定してください。
> 最も重いDispatchについて、Shaderのエントリポイント、スレッドグループ数、
> 読み書きするBufferとTextureを教えてください。

**詳細な調査:**
> このCaptureの全EventのGPU時間を計測し、最もコストの高いCompute Dispatchを上位5件
> 挙げてください。最もコストの高いDispatchについて、EventのIDと名前、計測されたGPU時間と
> 全体に占める割合、Shaderのエントリポイント、スレッドグループ数とサイズ、バインドされた
> 全入力Texture・出力UAVとそのフォーマット・サイズを報告してください。大きなTexture・高い
> スレッド数・帯域幅への影響など、ボトルネックの可能性についても考察してください。

## 調査内容

- 全EventのGPU時間を計測し、最もコストの高いDispatchを抽出する
- 対象Dispatchのスレッドグループ数とスレッドグループサイズ(numthreads)から総スレッド数を推計する
- Compute Shaderのエントリポイントを特定し、可能なら命令数を確認する
- バインドされた全入力リソース(SRV)と出力リソース(UAV)のフォーマットとサイズを一覧する
- 入力としてバインドされている特に大きなTextureが存在するか確認する(テクスチャキャッシュ圧力の原因になる)

## 期待される結果

Deferredレンダラーでは、Deferred Lightingのディスパッチが4.48ms(総GPU時間の30.2%)を
消費し、約200万スレッドを実行し、4枚のフルレゾリューションGBufferTextureと大きな
4096×4096シャドウアトラスを読み取る、といった結果が得られます。シャドウアトラスは32MBで
GPU L2テクスチャキャッシュ(一般的に2〜8MB)を大きく上回るため、キャッシュ圧力の候補です。

## 結果の解釈

- Shaderの命令数は逆アセンブルからの推定値です。実際のGPUサイクルはILPとメモリレイテンシーに
  依存し、命令数だけでは決まりません。
- Deferredレンダラーでは、Deferred LightingのDispatchが通常最もコストの高い単一Dispatchで、
  GPU フレーム時間の20〜40%を占めることが多いです。
- SSAOとブルームは通常もっと軽いですが、フルレゾリューション実装では重くなることがあります。
- 大きな読み取り専用リソース(シャドウアトラス、環境マップ、GIキャッシュ)はキャッシュ圧力の
  よくある原因です。
- スレッド数・命令数・Textureサイズの観察を組み合わせて仮説を立てますが、帯域幅/ALU
  ボトルネックの結論は専用カウンターデータが必要な仮説として明記してください。

## 制限事項

- 命令数は逆アセンブルからの推定値です。実際のGPUサイクルはILPとメモリレイテンシーに依存します。
- キャッシュミスカウンターは一部のGPU(AMD、Intel)では利用可能ですが、すべての
  NVIDIA/D3D12構成では利用できません。
- バインドされたリソースは報告されますが、アクセスパターンは報告されません。ほとんど
  サンプリングされないバインドされたTextureもリストに表示されます。

## 関連ツール

`list_gpu_counters`、`collect_gpu_counters`、`get_gpu_measurement_status`、
`get_performance_summary`、`get_pipeline_state`、`get_current_shaders`、
`get_shader_bindings` —
[パフォーマンス分析ガイド](../performance.md)および
[Toolリファレンス](../tools.md#gpuパフォーマンス分析)を参照。
