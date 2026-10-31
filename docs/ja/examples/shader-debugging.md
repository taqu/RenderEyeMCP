[English](../../en/examples/shader-debugging.md) | [日本語](shader-debugging.md)

# シナリオ D2 — ピクセルシェーダーデバッグ

## 問題

あるドローコールが画面上で予期しない色を生成していますが、ピクセル履歴では
そのピクセルに触れるフラグメントが 1 つしかありません。バグはピクセルシェーダー
自体の中にあります — 間違ったテクスチャサンプル、誤ったライティング計算式、または
初期化されていない変数です。

## 準備

1. RenderEyeMCP 拡張機能を有効にした状態で RenderDoc が起動していること。
2. キャプチャがロードされていること。`get_current_capture` で確認してください。
3. ピクセル履歴で問題のあるピクセルを担当する event_id が特定されていること
   ([シナリオ D1](pixel-history.md) を参照)。

## プロンプト例

> イベント 244 だけがピクセル (640, 400) に触れていますが、出力色は (0.0, 0.0, 0.0)
> です。ピクセルシェーダーをステップ実行して黒色がどこから来るかを見つけてください。

---

## 調査ワークフロー

### 1. ピクセルシェーダーデバッグトレースを収集する

```json
{
  "tool": "debug_pixel_shader",
  "x": 640,
  "y": 400,
  "event_id": 244
}
```

レスポンス例 (説明用):

```json
{
  "debug_id": "dbg_7c3e1f00",
  "stage": "pixel",
  "event_id": 244,
  "step_count": 67,
  "truncated": false
}
```

トレースはサーバー側に保存されます。以降の呼び出しには `debug_id` を使用します。

### 2. 最初のバッチのステップを取得する

```json
{
  "tool": "get_shader_debug_trace",
  "debug_id": "dbg_7c3e1f00",
  "first_step": 0,
  "count": 50
}
```

レスポンス例 (説明用 — ステップは省略):

```json
{
  "debug_id": "dbg_7c3e1f00",
  "first_step": 0,
  "count": 50,
  "total_steps": 67,
  "steps": [
    { "step": 0, "next_instruction": 0, "flags": 0, "generated_nan_or_inf": false,
      "changes": [] },
    { "step": 5, "next_instruction": 12, "flags": 0, "generated_nan_or_inf": false,
      "changes": [
        { "before": { "name": "v_texcoord", "rows": 1, "columns": 2,
                      "type": "float", "value": [0.0, 0.0] },
          "after":  { "name": "v_texcoord", "rows": 1, "columns": 2,
                      "type": "float", "value": [0.312, 0.748] } }
      ]
    },
    { "step": 18, "next_instruction": 31, "flags": 0, "generated_nan_or_inf": false,
      "changes": [
        { "before": { "name": "sampled_color", "rows": 1, "columns": 4,
                      "type": "float", "value": [0.0, 0.0, 0.0, 0.0] },
          "after":  { "name": "sampled_color", "rows": 1, "columns": 4,
                      "type": "float", "value": [0.72, 0.45, 0.21, 1.0] } }
      ]
    },
    { "step": 35, "next_instruction": 52, "flags": 0, "generated_nan_or_inf": false,
      "changes": [
        { "before": { "name": "diffuse", "rows": 1, "columns": 4,
                      "type": "float", "value": [0.0, 0.0, 0.0, 0.0] },
          "after":  { "name": "diffuse", "rows": 1, "columns": 4,
                      "type": "float", "value": [0.0, 0.0, 0.0, 1.0] } }
      ]
    }
  ]
}
```

ステップ 18 のテクスチャサンプルは妥当な色 `(0.72, 0.45, 0.21)` を返しています。
しかしステップ 35 で `diffuse` 変数が `(0.0, 0.0, 0.0, 1.0)` — アルファ最大の黒
— になっています。ライティング乗算が色をゼロにしてしまったようです。

### 3. 重要なステップで変数状態を検査する

```json
{
  "tool": "get_shader_debug_variables",
  "debug_id": "dbg_7c3e1f00",
  "step": 35
}
```

レスポンス例 (説明用):

```json
{
  "debug_id": "dbg_7c3e1f00",
  "step": 35,
  "variables": {
    "sampled_color": { "name": "sampled_color", "rows": 1, "columns": 4,
                       "type": "float", "value": [0.72, 0.45, 0.21, 1.0] },
    "n_dot_l":       { "name": "n_dot_l",       "rows": 1, "columns": 1,
                       "type": "float", "value": [0.0] },
    "diffuse":       { "name": "diffuse",       "rows": 1, "columns": 4,
                       "type": "float", "value": [0.0, 0.0, 0.0, 1.0] }
  }
}
```

`n_dot_l` (法線と光の方向の内積) が `0.0` です。ディフューズライティング項は
`sampled_color * n_dot_l` なので、ゼロに評価されて黒い出力になっています。

### 4. 残りのステップを確認する

```json
{
  "tool": "get_shader_debug_trace",
  "debug_id": "dbg_7c3e1f00",
  "first_step": 50,
  "count": 50
}
```

最後のステップを確認して最終出力レジスタの値を確認します。

### 5. 変数名でフィルタリングする

ライティング関連の変数だけに絞って調べる場合:

```json
{
  "tool": "get_shader_debug_variables",
  "debug_id": "dbg_7c3e1f00",
  "step": 60,
  "variable_names": ["n_dot_l", "diffuse", "ambient", "final_color"]
}
```

---

## 根本原因の分析

| ステップ | 変数 | 値 | 観察 |
|---|---|---|---|
| 18 | `sampled_color` | (0.72, 0.45, 0.21, 1.0) | テクスチャサンプルは正しい |
| 35 | `n_dot_l`       | 0.0                     | 光が面に垂直 |
| 35 | `diffuse`       | (0.0, 0.0, 0.0, 1.0)   | n_dot_l がゼロで色がゼロに |

`n_dot_l = 0` は以下を意味する可能性があります:
- 法線ベクトルがゼロベクトル (アップロード時に正規化されていない)。
- この正確なピクセルで光の方向が法線に垂直 (面全体に均一に影響する場合は考えにくい
  — 壊れた法線の方が可能性が高い)。
- 間違った法線属性が読み取られている (UV の代わりに法線、または間違ったセマンティクス)。

次のステップ: `get_mesh_vertices` で頂点データの法線ベクトルを検査し、
`get_post_vs_geometry` を使って Post-VS 出力と比較します。

---

## 制限事項

- シェーダーデバッグには GPU サポートが必要です。利用できない場合は
  `error: debug_pixel_unsupported` を返します。
- トレースは `max_steps` (デフォルト 200、最大 500) で打ち切られます。
  `truncated: true` を確認してください。
- キャプチャにシェーダーデバッグ情報がない場合、変数名はソースレベルの名前ではなく
  レジスタ名 (`r0`、`v1` など) になります。
- `DebugStore` は最大 10 個のトレースを保持します。削除後は新しいトレースを収集してください。

## 関連ツール

`get_pixel_history`, `debug_pixel_shader`, `get_shader_debug_trace`,
`get_shader_debug_variables`, `get_shader_debug_status`, `get_mesh_vertices`,
`get_post_vs_geometry` —
[高度なデバッグガイド](../advanced-debugging.md) および
[ツールリファレンス](../tools.md#高度なデバッグピクセル履歴--シェーダーデバッグ)。
