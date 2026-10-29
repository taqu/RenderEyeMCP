[English](../../en/examples/vertex-layout.md) | [日本語](vertex-layout.md)

# シナリオ G2 — 頂点フォーマットの不一致

## 問題

レンダリングされたジオメトリが歪んで表示されたり、色が崩れて表示されたりしています。
パイプラインステートの頂点バッファレイアウトが頂点シェーダーの期待する入力と一致して
いないという、古典的な入力レイアウトのミスマッチが疑われます。

## 準備

1. RenderEyeMCP 拡張機能を有効にした状態で RenderDoc が起動していること。
2. キャプチャがロードされていること。`get_current_capture` で確認してください。
3. レイアウトのミスマッチが疑われるドローコールを選択する。

## プロンプト例

> 選択されているドローコールの頂点入力レイアウトと頂点シェーダー入力シグネチャを
> 比較してください。属性のフォーマット、オフセット、バインディングが一致しているか
> 確認してください。

---

## 調査ワークフロー

### 1. 頂点入力レイアウトを取得する

```json
{ "tool": "get_vertex_input_layout" }
```

パイプラインステートで宣言された属性を返します: 名前、ロケーション、コンポーネント型、
コンポーネント数、バイトオフセット、VB スロット。

レスポンス例 (説明用):

```json
{
  "event_id": 340,
  "attributes": [
    { "name": "POSITION", "location": 0, "comp_type": "Float", "comp_count": 3,
      "comp_byte_width": 4, "vertex_buffer": 0, "byte_offset": 0,  "per_instance": false },
    { "name": "COLOR",    "location": 1, "comp_type": "UNorm", "comp_count": 4,
      "comp_byte_width": 1, "vertex_buffer": 0, "byte_offset": 12, "per_instance": false },
    { "name": "TEXCOORD", "location": 2, "comp_type": "Float", "comp_count": 2,
      "comp_byte_width": 4, "vertex_buffer": 0, "byte_offset": 16, "per_instance": false }
  ]
}
```

計算ストライド: `0 + 3×4 + 4×1 + 2×4 = 12 + 4 + 8 = 24 バイト`。

### 2. 頂点シェーダー入力シグネチャを取得する

```json
{ "tool": "get_current_shaders" }
```

アクティブなシェーダーを返します。レスポンス内の頂点シェーダー入力シグネチャを確認
します (詳細シグネチャは `get_shader_reflection` で取得可能)。

頂点シェーダーシグネチャ例 (説明用):

```json
{
  "vertex_shader": {
    "entry_point": "VSMain",
    "input_signature": [
      { "name": "POSITION", "location": 0, "comp_type": "Float", "comp_count": 3 },
      { "name": "COLOR",    "location": 1, "comp_type": "Float", "comp_count": 4 },
      { "name": "TEXCOORD", "location": 2, "comp_type": "Float", "comp_count": 2 }
    ]
  }
}
```

### 3. レイアウトとシェーダーシグネチャを比較する

ロケーション番号で並べます。

| ロケーション | レイアウト型 | シェーダーが期待する型 | 一致？ |
|---|---|---|---|
| 0 (POSITION) | `Float ×3` | `Float ×3` | ✓ |
| 1 (COLOR) | `UNorm8 ×4 ×1バイト` | `Float ×4` | **✗** |
| 2 (TEXCOORD) | `Float ×2` | `Float ×2` | ✓ |

ロケーション 1 がミスマッチです。パイプラインは `COLOR` を `UNorm8 × 4`
(4バイトのパックカラー、0–255 → 0.0–1.0 に正規化) として宣言していますが、
頂点シェーダーは 32ビット浮動小数点数の `float4` として読み取ろうとしています。
ハードウェアはその 4 バイトを 1 つの `float32` と解釈するため、無意味な浮動小数点
値が生成されます。

### 4. デコードされた頂点データで検証する

最初の数頂点をデコードして問題を確認します。

```json
{
  "tool": "get_mesh_vertices",
  "first_vertex": 0,
  "count": 5,
  "attributes": ["COLOR"]
}
```

ツールはレイアウト宣言のフォーマット (UNorm8×4) でデコードするため、
COLOR の値は正常に見えます。

```json
{
  "vertices": [
    { "vertex_id": 0, "attributes": { "COLOR": [1.0, 0.5, 0.25, 1.0] } },
    { "vertex_id": 1, "attributes": { "COLOR": [0.0, 1.0, 0.0,  1.0] } }
  ]
}
```

`get_mesh_vertices` の結果は正常に見えますが、頂点シェーダーは同じバイト列を
`float4` コンポーネントとして読み取るため、ゴミ値を受け取ります。

### 5. ドローコールのジオメトリ構成でストライドを確認する

```json
{ "tool": "get_draw_geometry_info" }
```

```json
{
  "vertex_buffers": [
    { "slot": 0, "byte_stride": 32 }
  ]
}
```

ストライドは 32 ですが、計算したレイアウトの合計は 24 バイトです。この 8 バイトの
差はパディングか、レイアウト宣言が間違っていてオフセットが誤った位置を指している
ことを意味します。`byte_offset` の値を調整して再計算してください。

### 6. ジオメトリ統計の健全性確認

```json
{ "tool": "get_mesh_statistics" }
```

```json
{
  "vertex_count": 1200,
  "index_count": 1800,
  "topology": "triangle_list",
  "bounding_box": { "min": [-1.0, 0.0, -1.0], "max": [1.0, 2.0, 1.0] },
  "nan_inf_count": 0,
  "degenerate_primitives": 0
}
```

NaN なし、縮退なし。問題は純粋にフォーマットのミスマッチであり、ジオメトリ自体は
正常です。

---

## よくあるミスマッチパターン

| パターン | 症状 | 診断 |
|---|---|---|
| `UNorm8` 宣言、シェーダーが `float` で読む | 色が異常または極端な値 | COLOR/TANGENT/BONEWEIGHT 属性のフォーマット型ミスマッチ |
| オフセットが 4 または 8 バイトずれている | 位置がせん断または傾いて見える | ある属性の `byte_offset` が間違っている |
| バインディングスロットが間違っている | 属性が常にゼロ | 未バインドの VB スロットを参照している |
| ストライドが小さすぎる | 2 頂点目以降で壊れる | 計算したレイアウトが宣言ストライドより大きい |
| per_instance フラグが間違っている | オブジェクトが間違ったトランスフォームを使う | 頂点ごとであるべき属性が `per_instance` になっている |

---

## 想定される観察結果

- フォーマットのミスマッチはパックされたカラーや法線属性 (UNorm/SNorm 8bit) で
  頻繁に発生します。シェーダーが 32 ビット浮動小数点数を期待してコンパイルされた
  場合です。
- オフセットのエラーは目に見えるせん断として現れ、すべてのオフセットを表にして
  単調増加を確認すれば特定しやすいです。
- ストライドのエラーは最初の頂点以降のすべての頂点に影響します。

---

## 制限事項

- `get_mesh_vertices` はレイアウトで宣言されたフォーマットでデコードします。
  レイアウトとシェーダーの差異は 2 つのレスポンスを手動で比較することでのみ
  確認できます。
- コンポーネントのバイト幅は個別コンポーネントのものです。属性全体のサイズは
  `comp_count × comp_byte_width` となります。

## 関連ツール

`get_current_capture`, `get_vertex_input_layout`, `get_current_shaders`,
`get_mesh_vertices`, `get_draw_geometry_info`, `get_mesh_statistics` —
[ジオメトリガイド](../geometry.md) および
[ツールリファレンス](../tools.md#ジオメトリメッシュ調査) を参照してください。
