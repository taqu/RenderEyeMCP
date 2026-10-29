[English](../../en/examples/missing-mesh.md) | [日本語](missing-mesh.md)

# シナリオ G1 — メッシュが表示されない

## 問題

レンダリング結果にオブジェクトが表示されないが、キャプチャ内にそのドローコールは
存在しています。頂点データが無効なのか、変換後の位置がビューフラスタムの外にある
のかを調査します。

## 準備

1. RenderEyeMCP 拡張機能を有効にした状態で RenderDoc が起動していること。
2. キャプチャがロードされていること。`get_current_capture` で確認してください。
3. 表示されないオブジェクトのドローコールを選択 (または特定) する。

## プロンプト例

> 現在選択されているドローコールのジオメトリを調査してください。頂点バッファと
> インデックスバッファ、入力レイアウト、頂点シェーダー後の位置を確認し、オブジェクト
> が表示されない原因となりそうな不審な値を特定してください。

---

## 調査ワークフロー

### 1. キャプチャのロードを確認する

```json
{ "tool": "get_current_capture" }
```

レスポンス例 (説明用):

```json
{
  "status": "loaded",
  "path": "C:/captures/game_frame_0123.rdc",
  "api": "D3D12",
  "frame_number": 123
}
```

### 2. ドローコールのジオメトリ構成を取得する

```json
{ "tool": "get_draw_geometry_info" }
```

確認ポイント:
- `draw_type` が `indexed` または `non_indexed` かどうか。`indirect` の場合は
  メタデータのみ読み取れます。
- `index_count` または `vertex_count` がゼロでないか。ゼロならジオメトリが
  送信されていないためオブジェクトは描画できません。
- `vertex_buffers` がバインドされているか。未バインドの VB スロットがあると
  頂点をフェッチできません。
- インデックスドローで `index_buffer` が存在するか。

レスポンス例 (説明用):

```json
{
  "event_id": 712,
  "draw_type": "indexed",
  "topology": "triangle_list",
  "index_count": 2400,
  "instance_count": 1,
  "first_index": 0,
  "base_vertex": 0,
  "first_instance": 0,
  "vertex_buffers": [
    { "slot": 0, "resource_id": "0x0000a3f1", "byte_offset": 0, "byte_stride": 32 }
  ],
  "index_buffer": { "resource_id": "0x0000a3f2", "byte_offset": 0, "format": "uint16" }
}
```

### 3. 頂点入力レイアウトを調べる

```json
{ "tool": "get_vertex_input_layout" }
```

確認ポイント:
- `POSITION` が存在し、有効な VB スロットにバインドされているか。
- コンポーネント型と数が正しいか (通常は `Float`、3 コンポーネント)。
- ストライド 32 バイトに対して各属性の `byte_offset` が妥当か。

レスポンス例 (説明用):

```json
{
  "attributes": [
    { "name": "POSITION", "location": 0, "comp_type": "Float", "comp_count": 3,
      "comp_byte_width": 4, "vertex_buffer": 0, "byte_offset": 0,  "per_instance": false },
    { "name": "NORMAL",   "location": 1, "comp_type": "Float", "comp_count": 3,
      "comp_byte_width": 4, "vertex_buffer": 0, "byte_offset": 12, "per_instance": false },
    { "name": "TEXCOORD", "location": 2, "comp_type": "Float", "comp_count": 2,
      "comp_byte_width": 4, "vertex_buffer": 0, "byte_offset": 24, "per_instance": false }
  ]
}
```

POSITION はオフセット 0、NORMAL は 12 (3×4 バイト)、TEXCOORD は 24 (6×4 バイト)。
合計ストライド 32 バイトで VB のストライドと一致します。問題なし。

### 4. 頂点位置のサンプルを読む

```json
{
  "tool": "get_mesh_vertices",
  "first_vertex": 0,
  "count": 10,
  "attributes": ["POSITION"]
}
```

最初の 10 頂点を確認します:
- コンポーネントに NaN や無限大がないか。
- すべてゼロでないか (オブジェクトが未初期化？)。
- スケールが妥当か (キャラクターメッシュなら ~1–2 m、0.001 や 10 000 ではない)。

レスポンス例 (説明用 — 問題ありのケース):

```json
{
  "vertices": [
    { "vertex_id": 0, "attributes": { "POSITION": [0.0, 0.0, 0.0] } },
    { "vertex_id": 1, "attributes": { "POSITION": [0.0, 0.0, 0.0] } },
    { "vertex_id": 2, "attributes": { "POSITION": [0.0, 0.0, 0.0] } }
  ]
}
```

頂点シェーダー前の位置がすべてゼロであれば、VB がアップロードされていないか
クリアされたことを強く示唆します。リソース初期化バグのサインです。

### 5. ジオメトリ統計を確認する

```json
{
  "tool": "get_mesh_statistics",
  "max_vertices": 200
}
```

レスポンス例 (説明用 — NaN 位置):

```json
{
  "vertex_count": 2400,
  "index_count": 2400,
  "instance_count": 1,
  "topology": "triangle_list",
  "sampled": true,
  "bounding_box": null,
  "nan_inf_count": 2400,
  "degenerate_primitives": null
}
```

`nan_inf_count: 2400` はサンプルしたすべてのコンポーネントが NaN または無限大で
あることを意味します。頂点バッファにゴミデータが入っています。有限値がないため
`bounding_box: null` になっています。

### 6. Post-VS ジオメトリを取得する

頂点バッファデータが妥当に見えるのにオブジェクトが表示されない場合、頂点シェーダーの
変換が間違っている可能性があります。

```json
{
  "tool": "get_post_vs_geometry",
  "stage": "vs_out",
  "max_vertices": 20
}
```

レスポンスの `clip_pos` と `ndc_pos` を確認します。画面内に表示される三角形では:
- `w > 0`
- NDC の `x` と `y` が `[-1, 1]` 内
- NDC の `z` が `[0, 1]` (D3D) または `[-1, 1]` (GL/Vulkan) 内

レスポンス例 (説明用 — 画面外):

```json
{
  "vertices": [
    { "vertex_id": 0, "clip_pos": [1500.2, 200.1, 0.5, 1.0],
      "ndc_pos":  [1500.2, 200.1, 0.5] },
    { "vertex_id": 1, "clip_pos": [1502.8, 201.5, 0.5, 1.0],
      "ndc_pos":  [1502.8, 201.5, 0.5] }
  ]
}
```

NDC `x` が 1500 は `[-1, 1]` を大幅に超えています。オブジェクト空間のジオメトリは
正しいですが、ビュー/射影行列が間違っており、メッシュがクリップ空間の遠方に変換
されています。

### 7. シェーダー定数との相関

頂点シェーダーにバインドされたビュープロジェクション行列を確認します。

```json
{ "tool": "get_current_shaders", "event_id": 712 }
```

MVP 行列に期待外の値 (非単位行列が必要なのに単位行列、前のフレームの行列など) が
含まれていれば、それが画面外 NDC 位置の原因です。

---

## 診断フローチャート

```
get_draw_geometry_info
├── index_count == 0 または vertex_count == 0  →  ジオメトリが送信されていない (CPU バグ)
├── vertex_buffers が未バインド               →  ドローコール前に VB が未設定
└── 問題なし → 頂点データを確認

get_mesh_vertices (POSITION)
├── すべてゼロ                               →  VB 未アップロード / クリアされた
├── NaN または無限大                          →  VB に無効データが含まれている
└── 妥当な値 → Post-VS を確認

get_post_vs_geometry
├── ndc_pos が [-1,1]² の外                  →  変換行列が間違っている
├── w ≤ 0                                    →  カメラ後方または射影行列が縮退
└── ndc_pos が範囲内                          →  ジオメトリは可視; ラスタライザ/カリングを確認
```

---

## 想定される観察結果

- メッシュが表示されない最も一般的な原因: 頂点数ゼロ、未バインド頂点バッファ、
  無効 (NaN/Inf/ゼロ) な頂点データ、不正な変換行列。
- `get_mesh_statistics` はすべての頂点を読まずに NaN/Inf を素早く検出できます。
- 頂点バッファの位置 (オブジェクト空間) と Post-VS クリップ位置を比較することで、
  シェーダーステップなしに変換チェーンを観察できます。

---

## 制限事項

- `get_post_vs_geometry` はドローコールをリプレイします。大きなメッシュでは
  コストを抑えるために `max_vertices` を小さく (10–20) 設定してください。
- `get_mesh_vertices` が読む頂点バッファの値は変換前 (オブジェクト空間) です。
  クリップ空間の Post-VS 位置と直接比較しないでください。
- インダイレクトドローはメタデータを報告しますが、実際の頂点数は実行時に決まります。
  バッファが読み取り可能であれば NaN 検出は機能します。

## 関連ツール

`get_current_capture`, `get_draw_geometry_info`, `get_vertex_input_layout`,
`get_mesh_vertices`, `get_mesh_statistics`, `get_post_vs_geometry`,
`get_current_shaders` — [ジオメトリガイド](../geometry.md) および
[ツールリファレンス](../tools.md#ジオメトリメッシュ調査) を参照してください。
