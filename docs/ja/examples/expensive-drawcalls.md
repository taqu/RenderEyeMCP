[English](../../en/examples/expensive-drawcalls.md) | [日本語](expensive-drawcalls.md)

# シナリオG — 最もコストの高いドローコールを特定し、パイプライン設定を分析する

## 問題

特定のFrameでGPU時間がかかりすぎています。どのDrawCallがボトルネックになっているかを
特定し、パイプラインの設定に問題がないか確認したい状況です。

## 準備

1. RenderEyeMCP拡張機能を有効にしたRenderDocが起動している。
2. 対象のCaptureがロード済みである。
3. `list_renderdoc_sessions`でセッションを確認し、`session_id`を控えておく。

## プロンプト例

> このCaptureで最もGPU時間を消費しているDrawCallを上位10件挙げてください。
> それぞれのパイプライン設定(Shader、頂点入力、Topology)を確認し、
> 計測された根拠とともにボトルネックの仮説を示してください。

## 調査の流れ

### 1. 利用可能なカウンターを確認する

```json
{
  "tool": "list_gpu_counters",
  "arguments": { "session_id": "..." }
}
```

タイミング系カウンター(`duration`、`time`、`GPU time`を含む名前)の`counter_id`を
控えておきます。

### 2. 計測を実行する

```json
{
  "tool": "collect_gpu_counters",
  "arguments": {
    "session_id": "...",
    "counter_ids": [1, 2],
    "repeats": 3
  }
}
```

`repeats: 3`でばらつきを抑えます。返ってきた`measurement_id`を次のステップで使います。

### 3. 上位10件のコストの高いイベントを取得する

```json
{
  "tool": "get_performance_summary",
  "arguments": {
    "measurement_id": "meas_...",
    "top_n": 10
  }
}
```

各エントリには`event_id`、イベント名、計測値が含まれます。

### 4. 個々のDrawCallのパイプライン設定を確認する

コストの高いDrawCallの`event_id`を選択してRenderDoc上で選択し、
パイプライン設定を取得します。

```json
{
  "tool": "get_pipeline_state",
  "arguments": {
    "session_id": "...",
    "section": "summary"
  }
}
```

続けてShaderと頂点入力も確認します。

```json
{
  "tool": "list_shaders",
  "arguments": { "session_id": "..." }
}
```

```json
{
  "tool": "get_shader_info",
  "arguments": {
    "session_id": "...",
    "stage": "Vertex"
  }
}
```

### 5. パイプライン統計カウンターを確認する

```json
{
  "tool": "get_pipeline_statistics",
  "arguments": {
    "measurement_id": "meas_...",
    "event_id": 1234
  }
}
```

頂点インボケーション数(`vertex_invocations`)、クリッピング後のプリミティブ数
(`clipping_primitives`)、ピクセルシェーダー呼び出し数(`pixel_shader_invocations`)
などを確認します。

### 6. タイミングの詳細を確認する

```json
{
  "tool": "get_gpu_timings",
  "arguments": {
    "measurement_id": "meas_...",
    "sort_by": "duration_desc",
    "limit": 20,
    "offset": 0
  }
}
```

## 確認できること

- GPU時間でソートされた上位DrawCallの一覧とそれぞれの`event_id`。
- 各DrawCallの`topology`、`vertex_buffer`のStrideとバインド状況。
- Vertex ShaderおよびPixel ShaderのシェーダーIDとエントリポイント。
- パイプライン統計(頂点数、プリミティブ数、PSの呼び出し回数)。

## 解釈

- **頂点インボケーション数が極端に多い** — メッシュのLODが適切か確認してください。
  遠距離オブジェクトに高ポリゴンメッシュが使われていると無駄が生じます。
- **ピクセルシェーダー呼び出し数がRenderTargetの解像度より著しく多い** — アルファ
  テストや深度プリパスなしのオーバードローが疑われます。
- **パイプライン統計カウンターが取得できない** — GPU/ドライバーが対応していない場合が
  あります。欠損はゼロではなく「未取得」として扱ってください。
- コストの高いDrawCallが特定できたら、[シナリオH — GPUボトルネック調査](gpu-bottleneck.md)
  に進んで詳しく分析してください。

## 制限

- 計測はリプレイベースです。ライブ実行時のフレームタイムとは一致しません。
- カウンター可用性はGPU/ドライバー/APIによって異なります。
- `get_performance_summary`が返すのはDrawCall単位の時間であり、CPU時間や
  ドライバーオーバーヘッドは含まれません。

## 関連Tool

`list_gpu_counters`、`collect_gpu_counters`、`get_gpu_measurement_status`、
`get_performance_summary`、`get_gpu_timings`、`get_pipeline_statistics`、
`get_pipeline_state`、`list_shaders`、`get_shader_info` —
[パフォーマンス分析ガイド](../performance.md)および
[Toolリファレンス](../tools.md#gpuパフォーマンス分析)を参照。
