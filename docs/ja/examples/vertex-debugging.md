[English](../../en/examples/vertex-debugging.md) | [日本語](vertex-debugging.md)

# シナリオ D4 — 頂点シェーダーデバッグ

## 問題

変換後にメッシュの頂点が間違った位置に現れています。特定の頂点の頂点シェーダーを
ステップ実行して MVP 行列乗算の結果を確認し、変換がどこで間違っているかを
突き止めます。

## 準備

1. RenderEyeMCP 拡張機能を有効にした状態で RenderDoc が起動していること。
2. キャプチャがロードされていること。`get_current_capture` で確認してください。
3. 位置がずれたメッシュのドローコールが選択済みまたは把握されていること。

## プロンプト例

> ドローイベント 310 の頂点 0 が間違ったクリップ空間位置になっています。
> 頂点シェーダーをステップ実行して変換がどこで壊れているか見つけてください。

---

## 調査ワークフロー

### 1. ジオメトリ情報を取得して頂点インデックスを確認する

```json
{ "tool": "get_draw_geometry_info", "event_id": 310 }
```

レスポンス例 (説明用):

```json
{
  "event_id": 310,
  "draw_type": "indexed",
  "topology": "triangle_list",
  "index_count": 360,
  "instance_count": 1,
  "first_index": 0,
  "base_vertex": 0
}
```

インデックス付きドローの場合、デバッグしたい頂点の `idx` (生のインデックスバッファ値) が
必要です。`get_mesh_vertices` で相互参照します:

```json
{
  "tool": "get_mesh_vertices",
  "event_id": 310,
  "first_vertex": 0,
  "count": 5,
  "attributes": ["POSITION"]
}
```

### 2. 入力位置を確認する

```json
{
  "tool": "get_mesh_vertices",
  "event_id": 310,
  "first_vertex": 0,
  "count": 1,
  "attributes": ["POSITION", "NORMAL"]
}
```

レスポンス例 (説明用):

```json
{
  "vertices": [
    { "vertex_id": 0,
      "attributes": {
        "POSITION": [0.0, 1.0, 0.0],
        "NORMAL":   [0.0, 1.0, 0.0]
      }
    }
  ]
}
```

オブジェクト空間の位置は `(0, 1, 0)` — 単位オブジェクトの上部です。

### 3. Post-VS 位置を確認する

```json
{
  "tool": "get_post_vs_geometry",
  "event_id": 310,
  "stage": "vs_out",
  "max_vertices": 5
}
```

レスポンス例 (説明用 — 間違っている場合):

```json
{
  "vertices": [
    { "vertex_id": 0,
      "clip_pos": [0.0, 1000.0, 4.9, 5.0],
      "ndc_pos":  [0.0, 200.0, 0.98]
    }
  ]
}
```

NDC y = 200 は `[-1, 1]` を大きく超えています。頂点は画面外です。Y 座標が
1000 倍されています — モデル行列のスケールバグです。

### 4. 頂点シェーダーデバッグトレースを収集する

```json
{
  "tool": "debug_vertex_shader",
  "event_id": 310,
  "vert_id": 0,
  "inst_id": 0,
  "idx": 0
}
```

レスポンス例 (説明用):

```json
{
  "debug_id": "dbg_a1b2c300",
  "stage": "vertex",
  "event_id": 310,
  "step_count": 38,
  "truncated": false
}
```

### 5. トレースをステップ実行する

```json
{
  "tool": "get_shader_debug_trace",
  "debug_id": "dbg_a1b2c300",
  "first_step": 0,
  "count": 50
}
```

レスポンス例 (説明用 — 主要ステップ):

```json
{
  "steps": [
    { "step": 0,  "changes": [] },
    { "step": 8,  "changes": [
        { "before": { "name": "pos_ws", "value": [0.0, 0.0, 0.0, 0.0] },
          "after":  { "name": "pos_ws", "value": [0.0, 1000.0, 0.0, 1.0] } }
    ]},
    { "step": 22, "changes": [
        { "before": { "name": "pos_cs", "value": [0.0, 0.0, 0.0, 0.0] },
          "after":  { "name": "pos_cs", "value": [0.0, 1000.0, 4.9, 5.0] } }
    ]}
  ]
}
```

モデル→ワールド変換 (ステップ 8) の後、`pos_ws.y = 1000.0` — 明らかに間違っています。
モデル行列の Y 軸にスケール係数 1000 があります。

### 6. ステップ 8 で変数を検査する

```json
{
  "tool": "get_shader_debug_variables",
  "debug_id": "dbg_a1b2c300",
  "step": 8,
  "variable_names": ["pos_ws", "model_matrix"]
}
```

レスポンス例 (説明用):

```json
{
  "variables": {
    "model_matrix": {
      "name": "model_matrix",
      "rows": 4, "columns": 4,
      "type": "float",
      "value": [
        [1.0,    0.0,    0.0, 0.0],
        [0.0, 1000.0,    0.0, 0.0],
        [0.0,    0.0,    1.0, 0.0],
        [0.0,    0.0,    0.0, 1.0]
      ]
    },
    "pos_ws": { "name": "pos_ws", "value": [0.0, 1000.0, 0.0, 1.0] }
  }
}
```

`model_matrix[1][1] = 1000.0`。モデル行列の Y スケールが 1 ではなく 1000 です。
アプリケーションが間違ったスケール値をアップロードしているか、行列を誤って計算しています。

---

## 根本原因まとめ

| ステップ | 観察 |
|---|---|
| Post-VS クリップ: NDC y = 200 | 頂点が Y 方向に 200 倍ずれている |
| 頂点シェーダーステップ 8: `pos_ws.y = 1000` | モデル→ワールド変換が Y を 1000 倍している |
| `model_matrix[1][1] = 1000.0` | 確認: モデル行列アップロードの Y スケールが間違っている |

修正: モデル行列が計算またはアップロードされる箇所を見つけて Y スケールを修正します。

---

## 制限事項

- `debug_vertex_shader` は単一頂点呼び出しのみをデバッグします。他の頂点は異なる
  値を持つ場合があります; 必要に応じて追加の頂点に対して繰り返してください。
- インデックス付きドローの場合はインデックスバッファの値を `idx` として渡します。
  非インデックスドローの場合は `idx = vert_id + base_vertex` です。
- API またはドライバーが頂点シェーダーデバッグをサポートしない場合は
  `error: debug_vertex_unsupported` を返します。

## 関連ツール

`get_draw_geometry_info`, `get_mesh_vertices`, `get_post_vs_geometry`,
`debug_vertex_shader`, `get_shader_debug_trace`, `get_shader_debug_variables` —
[高度なデバッグガイド](../advanced-debugging.md) および
[ツールリファレンス](../tools.md#高度なデバッグピクセル履歴--シェーダーデバッグ)。
