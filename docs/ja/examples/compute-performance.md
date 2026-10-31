[English](../../en/examples/compute-performance.md) | [日本語](compute-performance.md)

# シナリオI — 最もコストの高いコンピュートディスパッチを特定し、シェーダーとリソースバインディングを調査する

## 問題

コンピュートワークロード(ポストプロセス、物理シミュレーション、カリング、スキニングなど)が
GPU時間を大きく消費しています。どのDispatchが重いか特定し、Shaderとリソースの
Bindingを確認して最適化の手がかりをつかみたい状況です。

## 準備

1. RenderEyeMCP拡張機能を有効にしたRenderDocが起動している。
2. 対象のCaptureがロード済みである。
3. `list_renderdoc_sessions`でセッションを確認し、`session_id`を控えておく。

## プロンプト例

> このCaptureで最もGPU時間を消費しているCompute Dispatchを上位5件挙げてください。
> それぞれのDispatchについて、Shaderのエントリポイント、スレッドグループ数、
> リソースBindingを確認し、最適化の観点から気になる点を教えてください。

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
    "counter_ids": [1, 2],
    "repeats": 3
  }
}
```

### 3. 上位のコストの高いイベントを確認する

```json
{
  "tool": "get_performance_summary",
  "arguments": {
    "measurement_id": "meas_...",
    "top_n": 20
  }
}
```

Dispatchイベント(名前に`Dispatch`を含むもの、またはイベント種別が`dispatch`のもの)
を探します。

### 4. タイミングの詳細を確認する

```json
{
  "tool": "get_gpu_timings",
  "arguments": {
    "measurement_id": "meas_...",
    "sort_by": "duration_desc",
    "limit": 50,
    "offset": 0
  }
}
```

DrawCallとDispatchが混在している場合、Dispatchを絞り込んで確認します。

### 5. 対象DispatchのShaderを確認する

コストの高いDispatchを選択した状態で、Compute Shaderの情報を取得します。

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
    "stage": "Compute"
  }
}
```

### 6. Shaderのリフレクションを確認する

```json
{
  "tool": "get_shader_reflection",
  "arguments": {
    "session_id": "...",
    "stage": "Compute",
    "section": "all"
  }
}
```

入力リソース(SRV)、出力リソース(UAV)、Constant Bufferのレイアウトを確認します。

### 7. リソースBindingを確認する

```json
{
  "tool": "get_shader_bindings",
  "arguments": {
    "session_id": "...",
    "stage": "Compute"
  }
}
```

各スロットに何がBindされているか確認します。UnbindのスロットやNullリソースが
ないかチェックしてください。

### 8. スレッドグループの設定を確認する

```json
{
  "tool": "get_selected_event",
  "arguments": { "session_id": "..." }
}
```

`dispatch_dimension`からX、Y、Zのスレッドグループ数を確認します。
`numthreads`宣言と組み合わせて、実際に処理するスレッド数を計算できます。

```json
{
  "tool": "get_shader_disassembly",
  "arguments": {
    "session_id": "...",
    "stage": "Compute",
    "search": "numthreads"
  }
}
```

### 9. 必要に応じてConstant Bufferを確認する

```json
{
  "tool": "read_buffer_data",
  "arguments": {
    "session_id": "...",
    "resource_id": 1401,
    "byte_offset": 0,
    "byte_size": 256,
    "decode_layout": [
      { "name": "element_count", "type": "uint32" },
      { "name": "stride", "type": "uint32" }
    ]
  }
}
```

処理件数(`element_count`)やStrideが正しいか確認します。

## 確認できること

- GPU時間でソートされたDispatchの一覧と`event_id`。
- 各DispatchのCompute Shaderのエントリポイントとシェーダーエンコーディング。
- `dispatch_dimension`(スレッドグループ数 X、Y、Z)。
- 入力/出力リソースのBinding状況(バインド済み/未バインド/Nullリソース)。
- Constant Bufferのデコード済み定数値。

## 解釈

- **Dispatchの次元はスレッドグループ数です。** 実際のスレッド数は
  `グループ数 × numthreads`です。処理対象のデータサイズに対してグループ数が
  少なすぎると、末尾データが処理されません。
- **UAVが未BindまたはNullリソース** — 出力が書き込まれていない可能性があります。
- **Constant Bufferの`element_count`が0** — 早期リターンしてなにも処理されていない
  可能性があります。
- **スレッドグループ数が1** — GPU並列度が活かせていない可能性があります。
  処理量に応じてグループ数を増やすことを検討してください。
- **同じShaderが多数のDispatchで実行されている** — バッチ処理に統合できないか
  検討してください。

## 制限

- 個々のスレッドのステップ実行や内部状態の検査はできません(Shaderデバッグなし)。
- Structured Bufferの読み取りには要素の構造体に合った`decode_layout`が必要です
  (1回の読み出しは100要素・16384バイトまで。`offset`でページ送り)。
- Indirect Dispatchの引数は特別扱いでデコードしません。引数Bufferを
  `read_buffer_data`で読んでください。
- 計測はリプレイベースです。ライブ実行時とは異なるGPUクロック状態になる場合があります。

## 関連Tool

`list_gpu_counters`、`collect_gpu_counters`、`get_performance_summary`、
`get_gpu_timings`、`get_selected_event`、`list_capture_events`、
`list_shaders`、`get_shader_info`、`get_shader_reflection`、
`get_shader_bindings`、`get_shader_disassembly`、`read_buffer_data` —
[パフォーマンス分析ガイド](../performance.md)および
[Toolリファレンス](../tools.md)を参照。
