[English](../../en/examples/gpu-bottleneck.md) | [日本語](gpu-bottleneck.md)

# シナリオP4 — 特定のDrawCallのGPUボトルネックを診断する

## 問題

特定のDrawCallがGPUで異常に時間を消費しています。パイプライン統計、Shader、
Render Target、リソースBindingを確認して、計測された根拠に基づいてボトルネックの
仮説を立てたい状況です。

## 準備

1. RenderEyeMCP拡張機能を有効にしたRenderDocが起動している。
2. 対象のCaptureがロード済みで、調査対象のDrawCallがGPUタイミング分析などにより
   特定済みである。そのevent_idがわかっていること。

## プロンプト例

**クイック調査:**
> イベント 1042 (`terrain_patch_00`) が 3.41 ms (GPU フレーム時間の23%) かかっています。
> パイプライン統計を収集し、Shaderと Render Targetを調べて、ボトルネックがどこにあるか
> 教えてください。

**詳細な調査:**
> イベント 1042 (`terrain_patch_00`) が 3.41 ms (GPU時間の23%) かかっています。
> なぜコストが高いか調査してください。そのEventのパイプライン統計を収集してください。
> Pixel Shaderを特定し、バインドされているTextureをフォーマットと次元とともに一覧し、
> Render Targetを調べてください。その後、(1)確認できた計測値、(2)それに基づくボトルネック
> の仮説、(3)さらなるプロファイリングが必要な問い、の3つに分けた構造化された分析を
> 出力してください。

## 調査内容

- この特定のDrawCallのGPU時間を確認してコストを確認する
- パイプライン統計: 頂点呼び出し数、Pixel Shader呼び出し数、ラスタライズされたプリミティブ数
- Pixel Shaderのエントリポイントと逆アセンブルから推定できる命令数
- Pixel Stageの全Textureバインディング: フォーマット、次元、数
- そのDrawでバインドされているRender Target: フォーマット、解像度、MSAAサンプル数
- Vertex Stageのバインディング: 大きなStructured BufferをVertex Shaderが読んでいないか

## 期待される結果

完全な調査では、計測された事実と推論を分けて報告します:

**計測で確認できた事実:**
- 3.41 ms GPU時間(Frameの23%)、3回リプレイの平均
- 8,847,360 Pixel Shader呼び出し数
- 1回の呼び出しあたり推定487命令
- Pixel StageにバインドされたTexture SRVが6スロット

**仮説(ボトルネックの可能性):**
- ALUヘビーなPixel Shader: 487命令 × 880万呼び出し = 非常に大きな計算バジェット
- Textureキャッシュ圧力: Pixel Shaderに6枚の4096×4096 Textureがバインドされている

**さらなるプロファイリングが必要:**
- ALUバウンドかメモリレイテンシーバウンドかを判断するにはキャッシュミスまたは帯域幅カウンターが必要

## 結果の解釈

- テレインDrawCallはオープンワールドゲームで最も重い単一DrawCallになりがちです。大きなトライアングル数、
  複数テクスチャレイヤーのPBRマテリアル、広い画面カバレッジが組み合わさるためです。
- PS呼び出し数とラスタライズプリミティブ数の比率はオーバードロー/カバレッジの簡易シグナルです。
- Pixel StageのTexture サイズが大きいことは、明示的なキャッシュミスカウンターが利用できない場合でも
  キャッシュ圧力の一貫した指標です。
- 逆アセンブルからの命令数推定値は近似値です。実際のGPUサイクルはdual-issue、述語実行、
  メモリレイテンシー隠蔽に依存します。
- カウンターが取得できない場合、その結果は欠損(ゼロではない)として扱ってください。

## 制限事項

- 仮説レベルの結論は追加のカウンターデータがないと確認できません。レポートでは
  仮説として明記してください。
- 逆アセンブルからの推定命令数は近似値です。実際のGPUサイクルはdual-issue、述語実行、
  メモリレイテンシー隠蔽に依存します。
- カウンター値が取得できない場合、結果はゼロではなく欠損として返されます。パイプライン
  統計がそのEventのデータを返さない場合、ドライバーがそのAPI/GPUでカウンターを
  提供していません。

## 関連ツール

`list_gpu_counters`、`collect_gpu_counters`、`get_gpu_measurement_status`、
`get_gpu_timings`、`get_pipeline_statistics`、`get_current_shaders`、
`get_shader_bindings`、`get_render_targets`、`get_pipeline_state` —
[パフォーマンス分析ガイド](../performance.md)および
[Toolリファレンス](../tools.md#gpuパフォーマンス分析)を参照。
