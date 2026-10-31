[English](../../en/examples/render-pass-performance.md) | [日本語](render-pass-performance.md)

# シナリオH — レンダーパスごとのGPUコストを比較する

## 問題

Shadow、GBuffer、Lighting、PostProcessなど、複数のレンダーパスのGPUコストを比較して、
どのパスが最も重いかを把握したい状況です。

## 準備

1. RenderEyeMCP拡張機能を有効にしたRenderDocが起動している。
2. 対象のCaptureがロード済みである。エンジン側でデバッグマーカー(`PIXBeginEvent`、
   `vkCmdBeginDebugUtilsLabelEXT`など)が設定されていると、階層構造で集計できます。
3. `list_renderdoc_sessions`でセッションを確認し、`session_id`を控えておく。

## プロンプト例

> Shadow、GBuffer、Lighting、PostProcessの各レンダーパスのGPUコストを比較してください。
> どのパスが最も重く、改善の余地があるか教えてください。

## 調査の流れ

### 1. 利用可能なカウンターを確認する

```json
{
  "tool": "list_gpu_counters",
  "arguments": { "session_id": "..." }
}
```

タイミング系カウンターの`counter_id`を確認します。

### 2. 計測を実行する

```json
{
  "tool": "collect_gpu_counters",
  "arguments": {
    "session_id": "...",
    "counter_ids": [1],
    "repeats": 3
  }
}
```

### 3. レンダーパスごとの集計を取得する

```json
{
  "tool": "get_render_pass_performance",
  "arguments": {
    "measurement_id": "meas_..."
  }
}
```

レスポンスにはデバッグマーカーの階層が含まれ、各パスの`aggregated_duration`が
示されます。

### 4. 重いパスのイベント詳細を確認する

コストが高いパスが特定できたら、そのパス内のイベントを個別に確認します。

```json
{
  "tool": "get_gpu_timings",
  "arguments": {
    "measurement_id": "meas_...",
    "sort_by": "duration_desc",
    "limit": 30,
    "offset": 0
  }
}
```

対象パスの`event_id`範囲に絞ることで、パス内で最も重いDrawCallを特定できます。

### 5. パス間でパイプライン統計を比較する

```json
{
  "tool": "get_pipeline_statistics",
  "arguments": {
    "measurement_id": "meas_..."
  }
}
```

各パスの頂点数やピクセルシェーダー呼び出し数を比較して、処理量の違いを把握します。

## `aggregated_duration` の意味

`aggregated_duration`は**葉イベント(子を持たないイベント)の計測値の合計**です。
GPUがそのパス全体に費やした実際の経過時間(ウォールクロック)とは異なります。

具体例で説明します。

```
GBuffer (aggregated_duration: 4.2ms)
├── DrawCall A  (1.1ms) ← 葉イベント
├── DrawCall B  (2.0ms) ← 葉イベント
└── DrawCall C  (1.1ms) ← 葉イベント
```

この場合、GBufferの`aggregated_duration`は`1.1 + 2.0 + 1.1 = 4.2ms`です。
ただしGPUが実際にGBufferパスにかけた経過時間は、コマンドキューの並列実行や
オーバーラップにより異なる場合があります。

次のような場合、合計が実際より小さくなることがあります。

- 葉でない中間イベントが計測対象に含まれていない。
- 一部のDrawCallのカウンターが取得できなかった(欠損はゼロではなく省かれます)。

## 確認できること

| パス | aggregated_duration | 主なDrawCall数 |
|------|---------------------|----------------|
| Shadow | 1.8ms | 45 |
| GBuffer | 4.2ms | 183 |
| Lighting | 2.1ms | 12 |
| PostProcess | 0.9ms | 8 |

このような比較から、GBufferが最も重いことがわかります。

## 解釈

- **GBufferが重い** — 描画するオブジェクト数(DrawCall数)が多いか、各DrawCallの
  ピクセルシェーダーが複雑な可能性があります。`get_performance_summary`で上位の
  DrawCallを確認してください。
- **Shadowが重い** — シャドウキャスターの数が多すぎるか、ShadowMap解像度が高すぎる
  可能性があります。
- **Lightingが相対的に重い** — 光源数が多いか、ライティングシェーダーが複雑な
  可能性があります。
- **パスの`aggregated_duration`がゼロ、またはパスが表示されない** — デバッグマーカーが
  設定されていないか、カウンターが取得できなかった可能性があります。

## 制限

- デバッグマーカーが設定されていないCaptureでは、パス階層が表示されません。
  その場合は`get_gpu_timings`でイベント単位のタイミングを確認してください。
- `aggregated_duration`はウォールクロック経過時間ではないため、パス間の合計が
  Frameの総GPU時間と一致しない場合があります。
- カウンター可用性はGPU/ドライバー/APIによって異なります。

## 関連Tool

`list_gpu_counters`、`collect_gpu_counters`、`get_render_pass_performance`、
`get_gpu_timings`、`get_performance_summary`、`get_pipeline_statistics` —
[パフォーマンス分析ガイド](../performance.md)および
[Toolリファレンス](../tools.md#gpuパフォーマンス分析)を参照。
