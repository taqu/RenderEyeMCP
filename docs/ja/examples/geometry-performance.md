[English](../../en/examples/geometry-performance.md) | [日本語](geometry-performance.md)

# シナリオ G4 — ジオメトリとパフォーマンス

## 問題

Phase 13 の GPU パフォーマンス分析によってドローコールが高コストであることが判明
しました。その高コストが過剰なジオメトリ (頂点数・インデックス数・インスタンス数の
多さ) に起因するのか、シェーダーの複雑さやラスタライズ処理に起因するのかを調査します。

## 準備

1. RenderEyeMCP 拡張機能を有効にした状態で RenderDoc が起動していること。
2. キャプチャがロードされていること。`get_current_capture` で確認してください。
3. Phase 13 のタイミングカウンターとパイプライン統計カウンターが収集済みであること。
   未収集の場合は先に `collect_gpu_counters` を実行してください。

## プロンプト例

> この高コストなドローコールが処理しているジオメトリを分析してください。インデックス数、
> インスタンス数、頂点シェーダー呼び出し回数、および利用可能な GPU タイミング測定値を
> 比較し、潜在的な非効率を特定してください。

---

## 調査ワークフロー

### 1. Phase 13 で高コストなドローコールを特定する

既存の測定結果があれば上位イベントを取得します。

```json
{
  "tool": "get_performance_summary",
  "measurement_id": "meas_9a2c1f",
  "top_n": 10
}
```

レスポンス例 (説明用):

```json
{
  "total_measured_seconds": 0.012,
  "top_events": [
    { "event_id": 880, "event_name": "DrawIndexedInstanced() — foliage_batch",
      "duration_seconds": 0.0042, "percent_of_total": 35.0 },
    { "event_id": 440, "event_name": "DrawIndexed() — terrain_hi",
      "duration_seconds": 0.0021, "percent_of_total": 17.5 }
  ]
}
```

イベント 880 (`foliage_batch`) が 35 % と突出して高コストです。

### 2. ドローコールのジオメトリ構成を取得する

```json
{
  "tool": "get_draw_geometry_info",
  "event_id": 880
}
```

レスポンス例 (説明用):

```json
{
  "event_id": 880,
  "draw_type": "indexed",
  "topology": "triangle_list",
  "index_count": 18000,
  "instance_count": 250,
  "first_index": 0,
  "base_vertex": 0,
  "first_instance": 0,
  "vertex_buffers": [
    { "slot": 0, "byte_stride": 48, "resource_id": "0x0000b1a2" },
    { "slot": 1, "byte_stride": 64, "resource_id": "0x0000b1a3", "per_instance": true }
  ]
}
```

重要な観察点:
- 250 インスタンス × 18 000 インデックス = **450 万回のインデックス読み取り**。
- スロット 1 はインスタンスごとのバッファ (トランスフォーム、マテリアル)。
- 35 % の GPU 時間を占めており、フレーム内の主要なコストです。

### 3. パイプライン統計を取得する (利用可能な場合)

```json
{
  "tool": "get_pipeline_statistics",
  "measurement_id": "meas_9a2c1f",
  "event_id": 880
}
```

レスポンス例 (説明用):

```json
{
  "event_id": 880,
  "vs_invocations": 3960000,
  "ps_invocations": 1500000,
  "ia_vertices": 4500000,
  "ia_primitives": 1500000,
  "clipping_invocations": 6000000,
  "clipping_primitives": 1200000
}
```

450 万回のインデックス読み取りに対して 396 万回の VS 呼び出し (後段のキャッシュに
よる再利用あり)。クリッピング後は 150 万プリミティブ中 120 万が生き残り (~80 %)
— 部分的にフラスタムからはみ出す植生としては妥当です。

### 4. メッシュのジオメトリ統計を取得する

```json
{
  "tool": "get_mesh_statistics",
  "event_id": 880,
  "max_vertices": 500
}
```

レスポンス例 (説明用):

```json
{
  "vertex_count": 18000,
  "index_count": 18000,
  "instance_count": 250,
  "topology": "triangle_list",
  "sampled": false,
  "bounding_box": { "min": [-0.5, 0.0, -0.5], "max": [0.5, 2.0, 0.5] },
  "nan_inf_count": 0,
  "degenerate_primitives": 12
}
```

6 000 プリミティブ (18 000 / 3) 中 12 の縮退三角形はわずかです。バウンディングボックス
`[-0.5, 0.5] × [0, 2] × [-0.5, 0.5]` は幅 1 m、高さ 2 m の植生カード (木のビルボード
メッシュ) を示しています。

### 5. 頂点入力レイアウトを確認する

```json
{
  "tool": "get_vertex_input_layout",
  "event_id": 880
}
```

インスタンスごとのスロットを確認します。各インスタンスが 64 バイトのトランスフォーム
(4×float4) を持つのは通常通りです。不必要に大きいインスタンスごとのデータや、
VB 帯域幅を削減するためにテクスチャにエンコードできるインスタンスごとの属性が
ないか確認します。

### 6. 頂点サンプルを調べる

```json
{
  "tool": "get_mesh_vertices",
  "event_id": 880,
  "first_vertex": 0,
  "count": 10,
  "attributes": ["POSITION"]
}
```

位置が妥当かを確認します。NaN なし、異常に大きな値なし、妥当なメッシュサイズ。

### 7. 結果を解釈して非効率を特定する

調査結果をまとめます:

| 観察 | 考えられる説明 |
|---|---|
| 250 インスタンス × 18 000 インデックス = 450 万回読み取り | 同一メッシュの高インスタンス数; 同じマテリアルを共有する場合はマージを検討 |
| 12 の縮退三角形 | 軽微; パフォーマンスへの影響は無視できる |
| クリッピング後 80 % のプリミティブが生き残る | 広いフラスタムまたは密な植生配置; インスタンスカリングを検討 |
| インスタンスごとの 64 バイト VB スロット | 4×4 トランスフォーム行列として正常 |

### 8. オプション — VS 入力と出力の比較

```json
{
  "tool": "get_post_vs_geometry",
  "event_id": 880,
  "stage": "vs_out",
  "max_vertices": 20
}
```

Post-VS 頂点で `w ≤ 0` や NDC が `[-1, 1]` 外のものが多い場合、それらのインスタンスは
完全に画面外にあります。CPU またはコンピュートパスでのインスタンスカリングで VS 呼び出し
回数を大幅に削減できます。

---

## パフォーマンス相関まとめ

| メトリクス | ソース | 値 (説明用) |
|---|---|---|
| GPU 所要時間 | Phase 13 タイミングカウンター | 4.2 ms (フレームの 35 %) |
| VS 呼び出し回数 | パイプライン統計 | 396 万 |
| PS 呼び出し回数 | パイプライン統計 | 150 万 |
| インデックス読み取り | `get_draw_geometry_info` | 450 万 |
| インスタンス数 | `get_draw_geometry_info` | 250 |
| 縮退プリミティブ | `get_mesh_statistics` | 12 / 6 000 |
| クリッピング後の生存率 | パイプライン統計 | 80 % |

1 PS 呼び出しに対して約 2.6 VS 呼び出しが発生しており、ボトルネックはピクセル
シェーダーではなく VS スループットまたはラスタライズ (プリミティブ数) にある可能性が
高いです。

---

## 制限事項

- GPU 所要時間はリプレイベースであり、ライブキャプチャと異なる可能性があります。
  サーマル状態の変化が測定値に影響します。
- `get_mesh_statistics` はバウンディングボックスのために最大 `max_vertices` 個を
  サンプルします。縮退プリミティブのカウントはインデックスバッファ全体 (最大
  `_MAX_INDEX_READ` インデックス) を対象とします。
- `get_post_vs_geometry` にはリプレイコストがかかります。VS 出力の検査が特に必要な
  場合のみ呼び出してください。

## 関連ツール

`get_current_capture`, `list_gpu_counters`, `collect_gpu_counters`,
`get_gpu_measurement_status`, `get_performance_summary`, `get_pipeline_statistics`,
`get_draw_geometry_info`, `get_vertex_input_layout`, `get_mesh_statistics`,
`get_post_vs_geometry` — [ジオメトリガイド](../geometry.md)、
[GPU パフォーマンスガイド](../performance.md)、および
[ツールリファレンス](../tools.md#ジオメトリメッシュ調査) を参照してください。
