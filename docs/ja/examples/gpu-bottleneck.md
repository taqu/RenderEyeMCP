[English](../../en/examples/gpu-bottleneck.md) | [日本語](gpu-bottleneck.md)

# シナリオJ — このDrawCallがGPUで遅い原因を調査する

## 問題

特定のDrawCallがGPUで異常に時間を消費しています。パイプライン統計、Shader、
Render Target、リソースBindingを確認して、計測された根拠に基づいてボトルネックの
仮説を立てたい状況です。

## 準備

1. RenderEyeMCP拡張機能を有効にしたRenderDocが起動している。
2. 対象のCaptureがロード済みで、調査対象のDrawCallがRenderDocで選択済みである。
3. `list_renderdoc_sessions`でセッションを確認し、`session_id`を控えておく。

## プロンプト例

> このDrawCallがGPUで遅い原因を調査してください。パイプライン統計、Shader、
> Render Target、リソースBindingを確認してください。計測で確認できた事実と
> 仮説(推測)は必ず分けて報告してください。

## 調査の流れ

### 1. 選択中のEventを確認する

```json
{
  "tool": "get_selected_event",
  "arguments": { "session_id": "..." }
}
```

`event_id`、`num_indices`、`num_instances`を確認します。

### 2. 計測を実行する

```json
{
  "tool": "list_gpu_counters",
  "arguments": { "session_id": "..." }
}
```

タイミング系および統計系カウンターの`counter_id`を確認してから計測します。

```json
{
  "tool": "collect_gpu_counters",
  "arguments": {
    "session_id": "...",
    "counter_ids": [1, 2, 3, 4, 5],
    "repeats": 3
  }
}
```

### 3. 対象DrawCallのパイプライン統計を確認する

```json
{
  "tool": "get_pipeline_statistics",
  "arguments": {
    "measurement_id": "meas_...",
    "event_id": 1234
  }
}
```

`vertex_invocations`、`clipping_primitives`、`pixel_shader_invocations`など
を確認します。

### 4. パイプライン設定を確認する

```json
{
  "tool": "get_pipeline_state",
  "arguments": {
    "session_id": "...",
    "section": "summary"
  }
}
```

```json
{
  "tool": "get_pipeline_state",
  "arguments": {
    "session_id": "...",
    "section": "rasterizer"
  }
}
```

Viewport、Scissor、ラスタライザの設定を確認します。

### 5. ShaderとリソースBindingを確認する

```json
{
  "tool": "list_shaders",
  "arguments": { "session_id": "..." }
}
```

```json
{
  "tool": "get_shader_reflection",
  "arguments": {
    "session_id": "...",
    "stage": "Pixel",
    "section": "all"
  }
}
```

```json
{
  "tool": "get_shader_bindings",
  "arguments": {
    "session_id": "...",
    "stage": "Pixel"
  }
}
```

### 6. Render Targetを確認する

```json
{
  "tool": "get_render_targets",
  "arguments": { "session_id": "..." }
}
```

BindされているColor TargetとDepth Targetのサイズ、フォーマット、MipLevel、
配列スライスを確認します。

### 7. テクスチャリソースを確認する

重いShaderがテクスチャを多数サンプリングしている場合、Textureの情報を確認します。

```json
{
  "tool": "get_texture_info",
  "arguments": {
    "session_id": "...",
    "resource_id": 512
  }
}
```

解像度、MipLevel数、フォーマットを確認します。

### 8. 逆アセンブルでShaderの複雑さを確認する

```json
{
  "tool": "get_shader_disassembly",
  "arguments": {
    "session_id": "...",
    "stage": "Pixel"
  }
}
```

命令数の多さ、テクスチャサンプル数、ループの有無などを確認します。

## 確認できること

- `pixel_shader_invocations` — ピクセルシェーダーが何回呼び出されたか。
- `vertex_invocations` — 頂点シェーダーの呼び出し数。
- `clipping_primitives` — クリッピング後のプリミティブ数。
- Pixel ShaderにBindされているテクスチャの解像度とフォーマット。
- Render Targetのサイズとフォーマット。
- Shaderの命令数(逆アセンブルから)。

## 解釈 — 事実と仮説を区別する

GPUボトルネックの調査では、**計測で確認できた事実**と**推測による仮説**を必ず
区別してください。

### 確認できた事実の例

- `pixel_shader_invocations`が4,096,000回である
  (1920×2160 = 4,147,200ピクセルに対して約99%)
- Pixel Shaderに6枚の2048×2048テクスチャがBind済み
- Render TargetのフォーマットがR32G32B32A32_FLOATである(帯域幅コスト大)
- Shaderの逆アセンブルに380命令含まれている

### 仮説の例(測定だけでは確定できないもの)

- テクスチャサンプル数が多く、テクスチャキャッシュミスが発生している可能性がある
- 高精度フォーマット(R32G32B32A32_FLOAT)による帯域幅がボトルネックになっている
  可能性がある
- Shaderの命令数が多く、Arithmetic Limitedになっている可能性がある

### 一般的なボトルネックパターンと根拠の例

| ボトルネックの種類 | 計測根拠 | 仮説 |
|---------------------|----------|------|
| オーバードロー | PSInvocations >> 解像度 × ピクセル数 | 深度プリパスなし、アルファテストが多い |
| テクスチャ帯域幅 | 大解像度テクスチャが多数Bind | キャッシュミスによる遅延 |
| Render Target帯域幅 | 高精度フォーマット(R32F、RGBA32F) | 書き込みコスト過多 |
| Shader複雑度 | 逆アセンブルの命令数が多い | Arithmetic Limitedの可能性 |
| 頂点処理過多 | VertexInvocations >> プリミティブ数 × 3 | 高ポリゴンメッシュ、LODなし |

### このツールで確認できないボトルネック

以下は計測だけでは判断できません。RenderDocのUIやGPUプロファイラーと組み合わせて
確認してください。

- GPU内部のメモリ帯域幅の飽和状況
- テクスチャキャッシュのヒット率
- WavefrontのOccupancy
- GPU温度によるサーマルスロットリング

## 制限

- カウンター可用性はGPU/ドライバー/APIによって異なります。カウンターが取得できない
  場合、その結果は0ではなく省かれます。
- 計測はリプレイベースです。ライブ実行時のフレームタイムとは一致しない場合があります。
- CullモードやBlendステートはRenderEyeMCPでは取得できません。
  RenderDocのPipeline Stateパネルで確認してください。
- 個々のShaderスレッドのデバッグや波面解析はできません。

## 関連Tool

`get_selected_event`、`list_gpu_counters`、`collect_gpu_counters`、
`get_gpu_timings`、`get_performance_summary`、`get_pipeline_statistics`、
`get_pipeline_state`、`list_shaders`、`get_shader_reflection`、
`get_shader_bindings`、`get_shader_disassembly`、`get_render_targets`、
`get_texture_info` —
[パフォーマンス分析ガイド](../performance.md)および
[Toolリファレンス](../tools.md)を参照。
