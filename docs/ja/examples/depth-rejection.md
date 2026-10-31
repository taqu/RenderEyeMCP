[English](../../en/examples/depth-rejection.md) | [日本語](depth-rejection.md)

# シナリオ D3 — 深度テスト棄却

## 問題

オブジェクトが他のすべてのものより前面にあるべきなのに表示されていません。
ピクセル履歴ではフラグメントは存在していますが、常に深度テストで棄却されています。

## 準備

1. RenderEyeMCP 拡張機能を有効にした状態で RenderDoc が起動していること。
2. キャプチャがロードされていること。`get_current_capture` で確認してください。
3. 表示されるべきオブジェクトが現れるはずのピクセル座標がわかっていること。

## プロンプト例

> ピクセル (960, 540) の UI オーバーレイが表示されていません。ピクセル履歴では
> そのドローコールがフラグメントを生成していますが、すべて棄却されています。
> 原因を調べてください。

---

## 調査ワークフロー

### 1. 影響を受けるピクセルでピクセル履歴を実行する

```json
{
  "tool": "get_pixel_history",
  "resource_id": "0x00014f00",
  "x": 960,
  "y": 540,
  "max_modifications": 50
}
```

レスポンス例 (説明用):

```json
{
  "modification_count": 4,
  "modifications": [
    { "event_id": 5,   "passed": true,  "post_mod": { "r": 0.2, "g": 0.2, "b": 0.2, "a": 1.0 } },
    { "event_id": 180, "passed": true,  "post_mod": { "r": 0.6, "g": 0.4, "b": 0.1, "a": 1.0 } },
    { "event_id": 305, "passed": true,  "post_mod": { "r": 0.6, "g": 0.4, "b": 0.1, "a": 1.0 } },
    {
      "event_id": 420,
      "passed": false,
      "rejection_reason": "depth_test",
      "depth_test_failed": true,
      "shader_out": { "r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0 },
      "pre_mod":    { "r": 0.6, "g": 0.4, "b": 0.1, "a": 1.0 },
      "post_mod":   { "r": 0.6, "g": 0.4, "b": 0.1, "a": 1.0 }
    }
  ],
  "summary": {
    "passed_fragments": 3,
    "rejected_fragments": 1,
    "last_modifying_event": 305
  }
}
```

イベント 420 (UI オーバーレイ) は毎回深度テストで棄却されています。シェーダー出力は
正しい (白) ですが、ピクセル値は変わりません。

### 2. イベント 420 のパイプライン状態を確認する

```json
{ "tool": "get_pipeline_state", "event_id": 420 }
```

深度/ステンシル状態を確認します:

```json
{
  "depth_stencil": {
    "depth_enable": true,
    "depth_write_enable": false,
    "depth_func": "LESS",
    "stencil_enable": false
  }
}
```

深度テストが `LESS` です。UI オーバーレイは `z = 1.0` (遠平面) でレンダリングされて
いますが、シーンジオメトリはすでにこのピクセルに `z = 0.82` を書き込んでいます。
`1.0` は `0.82` より小さくないため、フラグメントは失敗します。

### 3. 深度値を比較する

イベント 420 の前の深度バッファを確認して深度値を検証します:

```json
{ "tool": "get_bound_resources", "event_id": 420 }
```

深度バッファのリソースを特定し、バインドされた深度を検査します:

```json
{ "tool": "get_resource_info", "resource_id": "<depth_resource_id>" }
```

### 4. 描画順序と深度設定を確認する

問題は UI オーバーレイが深度テストなし (またはデプスを常に通過) でレンダリングされる
べきですが、誤ってシーンの深度状態を使用していることです。

```json
{ "tool": "get_pipeline_state", "event_id": 305 }
```

イベント 305 (深度書き込みが有効な最後の 3D オブジェクト) とイベント 420 を比較します。
420 が UI パスであれば、`depth_func: ALWAYS` を使用するか、深度テストを無効に
(`depth_enable: false`) するべきです。

### 5. 別のピクセルで確認する

オーバーレイが現れるべき別のピクセルを確認します:

```json
{
  "tool": "get_pixel_history",
  "resource_id": "0x00014f00",
  "x": 980,
  "y": 540,
  "max_modifications": 20
}
```

同じパターンが繰り返される場合 (オーバーレイフラグメントあり、常に深度棄却)、
パイプライン状態のエラーが確認されます。

---

## 棄却理由リファレンス

| `rejection_reason` | 意味 | よくある原因 |
|---|---|---|
| `depth_test` | 深度比較が失敗 | 間違った深度関数、不正な z 値、早すぎる深度書き込み |
| `stencil_test` | ステンシル比較が失敗 | ステンシルマスクの不一致、間違った参照値 |
| `shader_discard` | シェーダーが `discard` / `clip` を呼び出した | アルファテスト、範囲外 UV、明示的なカリング |
| `backface_cull` | 裏面が除去された | 間違った巻き順、反転した法線 |
| `scissor` | シザー矩形の外側 | シザー矩形の設定ミス |
| `sample_mask` | MSAA サンプルマスクで除外 | MSAA 設定の不一致 |
| `unknown` | 理由が特定できない | 他のパイプラインステージを確認 |

---

## 根本原因まとめ

| 観察 | 意味 |
|---|---|
| イベント 420 のフラグメントはあるが常に深度棄却 | UI レンダリングのパイプライン深度状態が間違っている |
| UI ドローに `depth_func: LESS` | UI は `ALWAYS` または深度テストなしを使用すべき |
| シーン深度 = 0.82、UI z = 1.0 | UI は深度バッファ内のすべてのジオメトリの後ろにある |

修正: UI ドローコールパスの `depth_enable = false` (または `depth_func = ALWAYS`) を設定します。

---

## 制限事項

- ピクセル履歴は GPU リプレイベースです。多くのピクセルでタイトなループで呼び出すことは
  避けてください。
- 深度棄却が期待通り (正しいオクルージョン) の場合は、`passed: true` を使用してピクセルに
  実際に書き込んだ最後のフラグメントを見つけてください。

## 関連ツール

`get_pixel_history`, `get_pipeline_state`, `get_bound_resources`, `get_resource_info` —
[高度なデバッグガイド](../advanced-debugging.md) および
[ツールリファレンス](../tools.md#高度なデバッグピクセル履歴--シェーダーデバッグ)。
