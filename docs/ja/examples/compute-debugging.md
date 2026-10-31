[English](../../en/examples/compute-debugging.md) | [日本語](compute-debugging.md)

# シナリオ D5 — コンピュートシェーダーの NaN

## 問題

ポストプロセス結果を生成するコンピュートシェーダーが NaN または Inf 値を出力し、
下流で破損したピクセルを引き起こしています。最初に NaN を生成した正確な命令と
原因となった変数を見つけます。

## 準備

1. RenderEyeMCP 拡張機能を有効にした状態で RenderDoc が起動していること。
2. キャプチャがロードされていること。`get_current_capture` で確認してください。
3. コンピュートシェーダーを含むディスパッチの event_id がわかっているか、
   GUI で選択されていること。

## プロンプト例

> イベント 550 のコンピュートディスパッチが出力バッファに NaN を生成しています。
> ワークグループ (0,0,0) のスレッド (0,0,0) をステップ実行して NaN を最初に
> 生成した命令を見つけてください。

---

## 調査ワークフロー

### 1. ディスパッチが選択されていることを確認する

```json
{ "tool": "get_current_capture" }
```

### 2. コンピュートシェーダーデバッグトレースを収集する

```json
{
  "tool": "debug_compute_shader",
  "event_id": 550,
  "group_x": 0, "group_y": 0, "group_z": 0,
  "thread_x": 0, "thread_y": 0, "thread_z": 0
}
```

レスポンス例 (説明用):

```json
{
  "debug_id": "dbg_ff00aa11",
  "stage": "compute",
  "event_id": 550,
  "step_count": 112,
  "truncated": false
}
```

### 3. すべてのステップで NaN フラグをスキャンする

`generated_nan_or_inf` フラグをスキャンするために大きなバッチを要求します:

```json
{
  "tool": "get_shader_debug_trace",
  "debug_id": "dbg_ff00aa11",
  "first_step": 0,
  "count": 200
}
```

返されたステップで `"generated_nan_or_inf": true` を探します。例 (説明用):

```json
{
  "steps": [
    { "step": 0,  "generated_nan_or_inf": false, "changes": [] },
    { "step": 10, "generated_nan_or_inf": false, "changes": [
        { "after": { "name": "luminance", "value": [0.0] } }
    ]},
    { "step": 47, "generated_nan_or_inf": true,  "changes": [
        { "before": { "name": "log_lum", "value": [0.0] },
          "after":  { "name": "log_lum", "value": ["Inf"] } }
    ]},
    { "step": 48, "generated_nan_or_inf": true,  "changes": [
        { "before": { "name": "tone_factor", "value": [0.0] },
          "after":  { "name": "tone_factor", "value": ["NaN"] } }
    ]}
  ]
}
```

ステップ 47 が **最初の** NaN/Inf です。変数 `log_lum` が `Inf` になっています。

### 4. NaN ステップで変数を検査する

```json
{
  "tool": "get_shader_debug_variables",
  "debug_id": "dbg_ff00aa11",
  "step": 47
}
```

レスポンス例 (説明用):

```json
{
  "variables": {
    "luminance":  { "name": "luminance",  "value": [0.0] },
    "log_lum":    { "name": "log_lum",    "value": ["Inf"] },
    "epsilon":    { "name": "epsilon",    "value": [0.0] }
  }
}
```

`log_lum` は `log(luminance + epsilon)` として計算されています。`luminance` と
`epsilon` の両方が `0.0` のため、`log(0.0) = -Inf` になります。`-Inf` に対する
後続の算術演算が `NaN` を生成します。

### 5. 1 ステップ前の変数を検査する

```json
{
  "tool": "get_shader_debug_variables",
  "debug_id": "dbg_ff00aa11",
  "step": 46,
  "variable_names": ["luminance", "epsilon", "input_color"]
}
```

レスポンス例 (説明用):

```json
{
  "variables": {
    "luminance":   { "value": [0.0] },
    "epsilon":     { "value": [0.0] },
    "input_color": { "value": [0.0, 0.0, 0.0, 1.0] }
  }
}
```

このスレッドでは `input_color` が黒 (ゼロ) — 黒い境界ピクセルです。黒いピクセルに
対して `luminance` が正しくゼロになっています。バグは `epsilon` が `log(0)` を
防ぐための小さな非ゼロ定数 (例: `1e-6`) であるべきところ、`0.0` として読み取られて
いることです。

### 6. 必要に応じて他のスレッドを確認する

NaN が特定のスレッドに限定される場合があります。比較のためにディスパッチの中央の
スレッドをデバッグします:

```json
{
  "tool": "debug_compute_shader",
  "event_id": 550,
  "group_x": 4, "group_y": 4, "group_z": 0,
  "thread_x": 8, "thread_y": 8, "thread_z": 0
}
```

他のスレッドでゼロ以外の `luminance` が示されて NaN がない場合、問題は輝度が
ちょうどゼロのピクセル (暗い境界や空の領域) に限定されます。

### 7. デバッグストアのステータスを確認する

```json
{ "tool": "get_shader_debug_status" }
```

レスポンス例:

```json
{
  "debug_ids": ["dbg_ff00aa11", "dbg_a1b2c300"]
}
```

```json
{
  "tool": "get_shader_debug_status",
  "debug_id": "dbg_ff00aa11"
}
```

```json
{
  "debug_id": "dbg_ff00aa11",
  "status": "ready",
  "stage": "compute",
  "event_id": 550,
  "step_count": 112,
  "truncated": false
}
```

---

## 根本原因まとめ

| ステップ | 変数 | 値 | 観察 |
|---|---|---|---|
| 10 | `luminance`   | 0.0  | 黒いピクセルとして正しい |
| 46 | `epsilon`     | 0.0  | ~1e-6 であるべきがゼロ |
| 47 | `log_lum`     | Inf  | `log(0 + 0) = -Inf` |
| 48 | `tone_factor` | NaN  | Inf に対する下流の算術演算 |

修正: `log` 呼び出しの前に `epsilon` が非ゼロの定数に初期化されていることを確認します。
これは通常、定数バッファのアップロードバグです — ユニフォームが設定されていないか
ゼロにされています。

---

## 制限事項

- デバッグされるのは要求された単一スレッドのみです。共有メモリ、バリア、ウェーブ操作は
  シングルスレッドビューからは観察できません。
- NaN が `max_steps` (デフォルト 200、最大 500) を超えた後に最初に現れる場合は、
  `max_steps` を増やすか問題の発生源に近いスレッドを使用してください。
- API またはドライバーがコンピュートシェーダーデバッグをサポートしない場合は
  `error: debug_compute_unsupported` を返します (古い OpenGL ドライバーでよくあります)。
- `DebugStore` は最大 10 個のトレースを保持します; 溢れた場合は古いものが削除されます。

## 関連ツール

`debug_compute_shader`, `get_shader_debug_trace`, `get_shader_debug_variables`,
`get_shader_debug_status`, `get_bound_resources` —
[高度なデバッグガイド](../advanced-debugging.md) および
[ツールリファレンス](../tools.md#高度なデバッグピクセル履歴--シェーダーデバッグ)。
