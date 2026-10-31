[English](../../en/examples/pixel-history.md) | [日本語](pixel-history.md)

# シナリオ D1 — ピクセルの色が間違っている

## 問題

画面上のあるピクセルが間違った色を表示しています。そのピクセルに最後に書き込んだ
ドローコールを見つけ、なぜ期待通りの結果と異なるのかを調査します。

## 準備

1. RenderEyeMCP 拡張機能を有効にした状態で RenderDoc が起動していること。
2. キャプチャがロードされていること。`get_current_capture` で確認してください。
3. 問題のあるピクセルのおおよその画面座標がわかっていること。

## プロンプト例

> ピクセル (512, 384) が白になるべきところ暗い赤になっています。どのドローコールが
> 原因で、シェーダーがどんな色を出力したかを見つけてください。

---

## 調査ワークフロー

### 1. キャプチャのロードを確認する

```json
{ "tool": "get_current_capture" }
```

参照用に `capture_path` をメモします。

### 2. レンダーターゲットのリソース ID を特定する

```json
{ "tool": "get_render_targets" }
```

レスポンス例 (説明用):

```json
{
  "color_targets": [
    { "slot": 0, "resource_id": "0x00012abc", "format": "R8G8B8A8_UNORM",
      "width": 1920, "height": 1080 }
  ],
  "depth_target": { "resource_id": "0x00012abd", "format": "D24_UNORM_S8_UINT" }
}
```

`0x00012abc` を `resource_id` として使用します。

### 3. ピクセル履歴を取得する

```json
{
  "tool": "get_pixel_history",
  "resource_id": "0x00012abc",
  "x": 512,
  "y": 384,
  "max_modifications": 50
}
```

レスポンス例 (説明用):

```json
{
  "resource_id": "0x00012abc",
  "x": 512, "y": 384,
  "modification_count": 3,
  "modifications": [
    {
      "event_id": 12,
      "passed": true,
      "pre_mod":   { "r": 0.0, "g": 0.0, "b": 0.0, "a": 1.0 },
      "shader_out":{ "r": 0.1, "g": 0.1, "b": 0.1, "a": 1.0 },
      "post_mod":  { "r": 0.1, "g": 0.1, "b": 0.1, "a": 1.0 },
      "prim_id": 4, "frag_index": 0
    },
    {
      "event_id": 88,
      "passed": true,
      "pre_mod":   { "r": 0.1, "g": 0.1, "b": 0.1, "a": 1.0 },
      "shader_out":{ "r": 0.8, "g": 0.05, "b": 0.05, "a": 1.0 },
      "post_mod":  { "r": 0.8, "g": 0.05, "b": 0.05, "a": 1.0 },
      "prim_id": 211, "frag_index": 0
    },
    {
      "event_id": 120,
      "passed": false,
      "rejection_reason": "depth_test",
      "depth_test_failed": true,
      "pre_mod":   { "r": 0.8, "g": 0.05, "b": 0.05, "a": 1.0 },
      "shader_out":{ "r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0 },
      "post_mod":  { "r": 0.8, "g": 0.05, "b": 0.05, "a": 1.0 }
    }
  ],
  "summary": {
    "passed_fragments": 2,
    "rejected_fragments": 1,
    "last_modifying_event": 88
  }
}
```

重要な観察点:
- イベント 88 がピクセルに**書き込んだ**最後のドローです (暗い赤 `0.8, 0.05, 0.05`)。
- イベント 120 は正しい白 (`1.0, 1.0, 1.0`) を生成しましたが**深度テスト**に失敗し、
  出力が棄却されました。

### 4. イベント 120 の深度失敗を調査する

期待通りの白い色はイベント 120 から来るはずでしたが、深度テストで棄却されました。
赤い色を書いたドロー (イベント 88) は、イベント 120 のジオメトリよりもカメラに
近い深度値でレンダリングされました。

さらに調査するには:

```json
{ "tool": "get_pipeline_state", "event_id": 120 }
```

深度テストが有効で深度比較関数が正しいかを確認します (深度規則に応じて `LESS`、
`LESS_EQUAL`、`GREATER` のいずれか)。

```json
{ "tool": "get_pipeline_state", "event_id": 88 }
```

イベント 88 の深度状態を確認します。深度書き込みが有効で、イベント 120 のジオメトリが
前面に来るべきなのに後から描画されている場合は、描画順序または深度バッファの初期化を
確認します。

### 5. オプション: イベント 88 のピクセルシェーダーをデバッグする

暗い赤の色自体が疑わしい場合 (描画順序だけの問題ではない場合)、トレースを収集します:

```json
{
  "tool": "debug_pixel_shader",
  "x": 512,
  "y": 384,
  "event_id": 88
}
```

レスポンス:

```json
{ "debug_id": "dbg_3f1a2c00", "stage": "pixel", "event_id": 88,
  "step_count": 42, "truncated": false }
```

次に間違ったライティングやテクスチャサンプルをトレースで検査します:

```json
{
  "tool": "get_shader_debug_trace",
  "debug_id": "dbg_3f1a2c00",
  "first_step": 0,
  "count": 50
}
```

---

## まとめ

| イベント | 通過 | シェーダー出力 | 棄却理由 |
|---|---|---|---|
| 12  | はい | (0.1, 0.1, 0.1) | — |
| 88  | はい | (0.8, 0.05, 0.05) | — (最後の書き込み) |
| 120 | いいえ | (1.0, 1.0, 1.0) | depth_test |

正しい色を生成するはずだった後のドローが深度テストで棄却されたため、ピクセルに
間違った色が表示されています。イベント 120 のフラグメントが勝てるよう、深度バッファ
の状態または描画順序を調査してください。

---

## 制限事項

- ピクセル履歴は GPU リプレイを実行します。多くのピクセルでループして呼び出すことは
  避けてください。
- `max_modifications` は最大 200 です。非常にオーバードローが多いシーンでは増やしてください。
- ピクセル履歴の利用可能性はグラフィクス API によって異なります。
  [高度なデバッグ](../advanced-debugging.md#グラフィクス-api-とシェーダーサポート) を参照してください。

## 関連ツール

`get_current_capture`, `get_render_targets`, `get_pixel_history`,
`debug_pixel_shader`, `get_shader_debug_trace`, `get_shader_debug_variables`,
`get_pipeline_state` —
[高度なデバッグガイド](../advanced-debugging.md) および
[ツールリファレンス](../tools.md#高度なデバッグピクセル履歴--シェーダーデバッグ)。
