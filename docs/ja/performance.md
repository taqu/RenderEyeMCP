[English](../en/performance.md) | [日本語](performance.md)

# GPUパフォーマンス分析

## GPUパフォーマンス分析とは

RenderEyeMCPのパフォーマンス計測は**リプレイベース**です。RenderDocはキャプチャした
Frameをオフラインで再生し、そのときにGPUカウンターの値を収集します。ライブ実行中の
フレームタイムを計測するものではありません。

これは次のことを意味します。

- 計測にはRenderDocにCaptureがロードされている必要があります。
- 計測結果はキャプチャ時点のFrameを反映しており、その後の変更は反映されません。
- GPUリプレイを何度も再実行せずに、同じ計測結果を繰り返し分析できます。

## 前提条件

1. RenderEyeMCP拡張機能を有効にしたRenderDocが起動している。
2. 分析したいCaptureがRenderDocウィンドウに**ロード済み**である。
3. エージェントからRenderDocセッションに接続できる(`list_renderdoc_sessions`で確認)。

## カウンターを探索する — `list_gpu_counters`

利用できるGPUカウンターは、GPUの種類、ドライバーのバージョン、Graphics API
(D3D12/Vulkanなど)によって異なります。ハードコードされた一覧はありません。
まず`list_gpu_counters`で現在の環境で取得できるカウンターを確認してください。

```json
{
  "tool": "list_gpu_counters",
  "arguments": { "session_id": "..." }
}
```

レスポンスには各カウンターの`counter_id`、名前、説明、単位が含まれます。
`category`や`name`でフィルタリングして必要なカウンターを絞り込んでください。
同じカウンター名でも`counter_id`は環境ごとに異なる場合があります。

## 計測を実行する — `collect_gpu_counters`

カウンター一覧を確認したら、`collect_gpu_counters`でGPUリプレイを実行して計測します。
この操作はGPUに対して**明示的なリクエスト**であり、暗黙的には実行されません。

```json
{
  "tool": "collect_gpu_counters",
  "arguments": {
    "session_id": "...",
    "counter_ids": [1, 2, 5],
    "repeats": 3
  }
}
```

`counter_ids`は`list_gpu_counters`で得たIDを指定します。`repeats`(1〜5)を指定すると、
GPUリプレイを複数回実行して平均値を算出します。ばらつきが大きいカウンター(タイミング系など)
では`repeats: 3`以上を推奨します。

計測には数秒〜十数秒かかる場合があります。完了すると`measurement_id`が返ります。
この`measurement_id`は後続の分析ツールすべてで使用します。

> **注意**: `collect_gpu_counters`は比較的コストの高い操作です。同じカウンター群を
> 分析する場合は、一度取得した`measurement_id`を再利用してください。

## 計測のライフサイクル — `get_gpu_measurement_status`

計測には次の状態があります。

| 状態 | 意味 |
|------|------|
| `pending` | 収集キュー待ち |
| `running` | GPUリプレイ実行中 |
| `complete` | 分析可能 |
| `failed` | エラー(詳細は`error`フィールドを参照) |

`collect_gpu_counters`は通常は完了まで待機して返りますが、長時間かかる場合は
`get_gpu_measurement_status`でポーリングできます。

```json
{
  "tool": "get_gpu_measurement_status",
  "arguments": { "measurement_id": "meas_..." }
}
```

## 計測結果を分析する

`measurement_id`が得られたら、以下のツールで何度でも再分析できます。GPUリプレイの
再実行は不要です。

### `get_gpu_timings` — イベントごとのタイミング

Frameの全イベント(またはフィルタ済みイベント)の計測値を取得します。

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

`sort_by`には`duration_desc`(時間の長い順)、`duration_asc`(時間の短い順)、
`event_id_asc`(イベント順)が使えます。`limit`と`offset`でページネーションできます。

### `get_performance_summary` — コストの高いイベントのランキング

上位N件のコストの高いイベントをまとめて返します。

```json
{
  "tool": "get_performance_summary",
  "arguments": {
    "measurement_id": "meas_...",
    "top_n": 10
  }
}
```

ボトルネックの素早い特定に便利です。

### `get_render_pass_performance` — レンダーパスごとの集計

デバッグマーカーの階層(Shadow、GBuffer、Lighting、PostProcessなど)ごとにコストを
集計して返します。

```json
{
  "tool": "get_render_pass_performance",
  "arguments": {
    "measurement_id": "meas_..."
  }
}
```

**重要**: `aggregated_duration`は**葉イベント(子を持たないイベント)の実行時間の合計**
です。GPUがそのパスに費やした実際の経過時間(ウォールクロック)ではありません。
オーバーラップ実行や、葉でないイベントが計測されなかった場合、合計は実際より小さく
なることがあります。

### `get_pipeline_statistics` — パイプライン統計カウンター

頂点インボケーション数、ピクセルシェーダー呼び出し数、クリッピングプリミティブ数など、
パイプライン統計に関するカウンターだけをフィルタリングして返します。

```json
{
  "tool": "get_pipeline_statistics",
  "arguments": {
    "measurement_id": "meas_...",
    "event_id": 1234
  }
}
```

`event_id`を省略すると全イベントが対象になります。

## ページネーションとソートオプション

`get_gpu_timings`は大量のイベントを返す場合があります。`limit`と`offset`で
ページネーションを活用してください。

```
最初の50件: limit=50, offset=0
次の50件:   limit=50, offset=50
```

`sort_by: "duration_desc"`で最もコストの高いイベントから確認するのが一般的です。

## 計測のばらつきと `repeats`

GPUタイミングは実行ごとにばらつく場合があります。特に以下の状況で顕著です。

- GPUのクロック状態が不安定なとき
- サーマルスロットリングが発生しているとき
- Frameが短く、ノイズの影響が相対的に大きいとき

`repeats: 3`以上を指定すると複数回実行して平均を取ります。高精度が必要な場合や
ばらつきが気になる場合に使用してください。`repeats: 1`(デフォルト)は速度優先です。

## このツールで分からないこと

GPUパフォーマンスツールは次のことは計測**しません**。

- **CPU時間** — CPUのコマンド構築・サブミット時間はわかりません。
- **ライブフレームタイム** — リプレイベースのため、ゲーム実行中のフレームタイムとは
  異なります。
- **温度・電力** — GPU温度や消費電力は取得できません。
- **ドライバー内部のオーバーヘッド** — ドライバー処理時間は含まれません。
- **コマンドキューの待機時間** — マルチキュー間の同期待ちは見えません。

## マルチエージェント: `measurement_id` の共有

計測結果はサーバー側のメモリに保存されます。`measurement_id`を別のエージェントや
別のツール呼び出しに渡すことで、GPUリプレイを再実行せずに結果を共有できます。

計測はRenderDocセッションが続く限り保持されます。セッションが閉じると破棄されます。

## 既知の制限事項

- **カウンター可用性はGPUと環境によって異なります。** 同じカウンター名でも
  他の環境では使えない、またはIDが異なる場合があります。
- **カウンターが取得できなかった場合、その結果は0ではなく、結果セットから
  省かれます。** 欠損と0は別物として扱ってください。
- **`aggregated_duration`は壁時計経過時間ではありません。** 葉イベントの
  計測値の合計であり、パス全体のGPU経過時間とは一致しません。
- `collect_gpu_counters`はGPUリプレイを実行するため、キャプチャが正常にロードされ、
  RenderDocが再生可能な状態である必要があります。
- カウンターによっては特定のAPIやGPUベンダーでのみ取得できます。

## 関連Tool

`list_gpu_counters`、`collect_gpu_counters`、`get_gpu_measurement_status`、
`get_gpu_timings`、`get_performance_summary`、`get_render_pass_performance`、
`get_pipeline_statistics` —
[Toolリファレンス](tools.md#gpuパフォーマンス分析)を参照。
