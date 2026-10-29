[English](../en/advanced-debugging.md) | [日本語](advanced-debugging.md)

# 高度なデバッグ (ピクセル履歴・シェーダーデバッグトレース)

## はじめに

RenderEyeMCP は RenderDoc のピクセル履歴 API とシェーダーデバッグ API を 7 つの
構造化 MCP ツールとして公開します。これらのツールにより、AI コーディングエージェントは
静的なパイプラインおよびリソース検査だけでは解明できないレンダリング問題を調査できます。

ワークフローは 2 つの補完的なアプローチを中心に設計されています。

- **ピクセル履歴** — 「このピクセルにどのドローコールが触れ、結果はどうだったか？」
- **シェーダーデバッグトレース** — 「シェーダーが実際に何をステップごとに計算したか？」

どちらも RenderDoc GPU バックエンドでのリプレイ作業が必要です。これらは明示的な操作
であり、サーバーが自動的に実行することはありません。

---

## 前提条件

- RenderEyeMCP 拡張機能を有効にした状態で RenderDoc が起動していること。
- RenderDoc GUI でキャプチャ (`.rdc` ファイル) が開かれていること。
- `get_current_capture` で準備状況を確認してください。
- **グラフィクス API サポート**: ピクセル履歴とシェーダーデバッグはすべてのグラフィクス
  API およびすべてのシェーダータイプで利用できるわけではありません。サポートされていない
  操作は、作り物の結果ではなく明示的なエラーコードを返します。

---

## 利用可能なツール

| ツール | 目的 | 読み取り専用 |
|---|---|---|
| `get_pixel_history` | ピクセルに影響したすべての変更を取得する | いいえ† |
| `debug_pixel_shader` | 有界なピクセルシェーダーデバッグトレースを収集する | いいえ† |
| `debug_vertex_shader` | 有界な頂点シェーダーデバッグトレースを収集する | いいえ† |
| `debug_compute_shader` | 有界なコンピュートシェーダーデバッグトレースを収集する | いいえ† |
| `get_shader_debug_trace` | 保存されたトレースから有界なステップを取得する | はい |
| `get_shader_debug_variables` | 特定ステップでの変数状態を検査する | はい |
| `get_shader_debug_status` | 保存されたトレースのステータスを確認し、トレース ID を列挙する | はい |

† GPU リプレイを実行します。読み込まれているキャプチャや GUI で選択されているイベントは変更しません。

---

## ピクセル履歴

### `get_pixel_history`

現在フレーム内の 1 ピクセルへの変更履歴を `max_modifications` エントリまで取得します。

**パラメーター**

| パラメーター | 型 | デフォルト | 説明 |
|---|---|---|---|
| `resource_id` | string | — | 対象テクスチャの ResourceId |
| `x`, `y` | int | — | ピクセル座標 |
| `mip` | int | `0` | Mip レベル |
| `slice` | int | `0` | 配列スライス |
| `sample` | int | `0` | MSAA サンプルインデックス |
| `max_modifications` | int | `50` | 返す最大数 (最大 200) |
| `event_id` | int | `0` | 未使用 (将来のスコープ指定用に予約) |

**変更ごとの主要なレスポンスフィールド**

| フィールド | 意味 |
|---|---|
| `event_id` | このフラグメントを生成したドローコール |
| `passed` | フラグメントがピクセルを変更した場合 `true` |
| `rejection_reason` | `depth_test`、`stencil_test`、`shader_discard`、`backface_cull`、`scissor`、`sample_mask`、`unknown` のいずれか |
| `pre_mod` | このドロー前のピクセル値 |
| `shader_out` | シェーダーの生の出力 |
| `post_mod` | ブレンド/書き込みマスク後の最終ピクセル値 |
| `prim_id` | プリミティブ (三角形) インデックス |
| `frag_index` | ドロー内のフラグメントインデックス |
| `depth_test_failed` | 深度テストで棄却された場合 `true` |
| `shader_discarded` | ピクセルシェーダーが discard を呼び出した場合 `true` |

**`summary` フィールド** はさらに以下を報告します:
- `passed_fragments` / `rejected_fragments` カウント
- `last_modifying_event`: 実際にピクセルに書き込んだ最後のフラグメントの event_id

### ピクセル履歴ワークフロー

```text
get_current_capture → キャプチャを確認
       ↓
get_render_targets → テクスチャの resource_id を見つける
       ↓
get_pixel_history (resource_id, x, y) → 変更リストを取得
       ↓
rejection_reason とテストフラグを確認
       ↓
オプション: 関連イベントに対して debug_pixel_shader を実行
```

---

## シェーダーデバッグトレース

### トレースのライフサイクル

シェーダーデバッグは 2 フェーズの操作です:

1. **収集** (`debug_pixel_shader` / `debug_vertex_shader` / `debug_compute_shader`)
   — GPU リプレイを実行し、命令ステップと変数変更を収集し、結果をサーバーの
   `DebugStore` に保存して `debug_id` を返します。

2. **検査** (`get_shader_debug_trace`、`get_shader_debug_variables`、
   `get_shader_debug_status`) — さらなる GPU 作業なしに保存されたデータを読み取ります。

```text
debug_pixel_shader(x, y, event_id) → { debug_id, step_count }
              ↓
get_shader_debug_trace(debug_id, first_step=0, count=50) → ステップ
              ↓
get_shader_debug_variables(debug_id, step=N) → ステップ N での変数状態
```

`DebugStore` は最近最も使われていないものから順に最大 10 個のトレースを保持します。

### `debug_pixel_shader`

特定のピクセル座標のピクセルシェーダーデバッグトレースを開始します。

**パラメーター**

| パラメーター | 型 | デフォルト | 説明 |
|---|---|---|---|
| `x`, `y` | int | — | デバッグするピクセル |
| `event_id` | int | `0` | ドローイベント (0 = 現在の GUI 選択) |
| `sample` | int | `0` | MSAA サンプルインデックス |
| `primitive` | int | `-1` | プリミティブ ID (-1 = 自動選択) |
| `view` | int | `0` | マルチビューインデックス |
| `max_steps` | int | `200` | 最大トレースステップ数 (最大 500) |

返り値: `debug_id`、`stage`、`event_id`、`step_count`、`truncated`。

### `debug_vertex_shader`

特定の頂点呼び出しの頂点シェーダーデバッグトレースを開始します。

**パラメーター**

| パラメーター | 型 | デフォルト | 説明 |
|---|---|---|---|
| `vert_id` | int | `0` | デバッグする頂点インデックス |
| `inst_id` | int | `0` | インスタンスインデックス |
| `idx` | int | `0` | インデックスバッファの値 (インデックス付きドロー用) |
| `view` | int | `0` | マルチビューインデックス |
| `event_id` | int | `0` | ドローイベント (0 = 現在) |
| `max_steps` | int | `200` | 最大ステップ数 (最大 500) |

### `debug_compute_shader`

特定スレッドのコンピュートシェーダーデバッグトレースを開始します。

**パラメーター**

| パラメーター | 型 | デフォルト | 説明 |
|---|---|---|---|
| `group_x/y/z` | int | `0` | ワークグループインデックス |
| `thread_x/y/z` | int | `0` | ワークグループ内のスレッド |
| `event_id` | int | `0` | ディスパッチイベント (0 = 現在) |
| `max_steps` | int | `200` | 最大ステップ数 (最大 500) |

**注記**: デバッグされるのは要求された単一スレッドのみです。スレッド間の動作
(共有メモリ、バリア、ウェーブ操作) はこのビューからは観察できません。

### `get_shader_debug_trace`

保存されたトレースから有界なステップを取得します。

**パラメーター**

| パラメーター | 型 | デフォルト | 説明 |
|---|---|---|---|
| `debug_id` | string | — | デバッグツールから返された ID |
| `first_step` | int | `0` | 開始ステップインデックス |
| `count` | int | `50` | 返すステップ数 (最大 500) |

各ステップには以下が含まれます:
- `step`: ステップインデックス
- `next_instruction`: 実行しようとしている命令オフセット
- `flags`: ビットマスク; ビット 0x2 = `generated_nan_or_inf`
- `generated_nan_or_inf`: NaN または Inf が生成された場合 `true`
- `changes`: このステップで変化した各変数の `{ before: ShaderVariable, after: ShaderVariable }` のリスト

### `get_shader_debug_variables`

初期状態から指定の `step` まですべての変更デルタを累積することで、特定ステップでの
完全な変数状態を再構築します。

**パラメーター**

| パラメーター | 型 | デフォルト | 説明 |
|---|---|---|---|
| `debug_id` | string | — | デバッグツールから返された ID |
| `step` | int | `0` | 再構築するステップ (有効範囲にクランプ) |
| `variable_names` | list[string] | `null` | フィルター; null = すべて返す |

変数名 → `{ name, rows, columns, type, value }` のマッピングを含む `variables` オブジェクトを返します。

### `get_shader_debug_status`

トレースのステータスを確認するか、保存されているすべてのトレース ID を列挙します。

- `debug_id` あり: `status` (`ready`/`failed`/`invalidated`)、`stage`、`event_id`、
  `step_count`、およびすべてのメタデータを返します。
- `debug_id` なし: 保存されているすべての `debug_ids` を列挙します。

---

## ShaderVariable フォーマット

トレースステップと initial_vars の各変数には以下があります:

| フィールド | 意味 |
|---|---|
| `name` | 変数またはレジスタ名 |
| `rows`, `columns` | 行列の次元 (スカラーの場合 1×1) |
| `type` | RenderDoc リフレクションからの型文字列 |
| `value` | ベクター/行列の場合はスカラー、リスト、またはネスト |
| `members` | ネストされた変数 (構造体/配列) |

---

## 推奨デバッグワークフロー

### ピクセルの色が間違っている原因を見つける

```text
get_render_targets → レンダーターゲットの resource_id を特定
get_pixel_history(resource_id, x, y) → 最後に変更したイベントを見つける
debug_pixel_shader(x, y, event_id) → トレースを収集
get_shader_debug_trace(debug_id) → NaN フラグがあるステップを検査
get_shader_debug_variables(debug_id, step=N) → 重要なステップでの変数を検査
```

### シェーダーが最初に NaN を生成する場所を見つける

```text
debug_pixel_shader / debug_vertex_shader / debug_compute_shader → トレースを収集
get_shader_debug_trace(debug_id, count=500) → generated_nan_or_inf フラグをスキャン
  → generated_nan_or_inf: true の最初のステップを記録
get_shader_debug_variables(debug_id, step=first_nan_step) → 変数を特定
```

### 頂点変換をトレースする

```text
get_draw_geometry_info → vert_id と idx を見つける
debug_vertex_shader(vert_id, inst_id, idx) → トレースを収集
get_shader_debug_trace(debug_id) → 位置変換をステップ実行
get_shader_debug_variables(debug_id, step=N) → MVP 乗算結果を検査
```

---

## リプレイの影響と GUI の安全性

4 つの収集ツールはすべて RenderDoc の内部リプレイコントローラーを通じて GPU リプレイ
作業を実行します。これらは以下を行いません:
- 読み込まれているキャプチャを変更する。
- GUI で選択されているイベントを変更する。
- 開発者に見えているシェーダーデバッガー UI の状態を変更する。

ただし、収集中に RenderDoc の内部リプレイ位置が変わる場合があります。この内部状態は
RenderDoc によって自動的に復元されます。

---

## グラフィクス API とシェーダーサポート

デバッグサポートは RenderDoc の API とドライバー統合によって異なります。一般的な
利用可能性:

| 機能 | D3D11 | D3D12 | Vulkan | OpenGL |
|---|---|---|---|---|
| ピクセル履歴 | 可 | 可 | 可 | 可 |
| ピクセルシェーダーデバッグ | 通常可 | 通常可 | ドライバー依存 | 通常可 |
| 頂点シェーダーデバッグ | 可 | 可 | ドライバー依存 | 可 |
| コンピュートシェーダーデバッグ | 通常可 | 通常可 | ドライバー依存 | 限定的 |

デバッグ情報なしでコンパイルされたシェーダーは命令レベルのトレースのみを生成します;
ソースレベルの変数名は利用できません。

API またはシェーダーが要求されたデバッグ操作をサポートしない場合、
`error: debug_pixel_unsupported` (または `vertex`/`compute`) を返します。

---

## 既知の制限事項

- **ソースレベルデバッグなし**: キャプチャにデバッグ情報がなければ命令レベルのステップと
  レジスタ名のみです。
- **シングルスレッドコンピュート**: スレッド間の依存関係 (バリア、アトミック、共有メモリ)
  は反映されません。
- **プリミティブの曖昧さ**: 1 つのドローで複数のフラグメントがピクセルをカバーする場合、
  `primitive: -1` は自動的に 1 つを選択します; 正しい `prim_id` を特定するにはまず
  ピクセル履歴を使用してください。
- **ステップ制限**: トレースは `max_steps` (デフォルト 200、最大 500) で打ち切られます。
  大規模なシェーダーは切り詰められる場合があります; `truncated` フィールドを確認してください。
- **DebugStore の容量**: サーバーは最大 10 個のトレースを保持します; 溢れた場合は古い
  ものが削除されます。
- **リプレイコスト**: 各収集呼び出しは GPU カウンター測定パス 1 回に相当する GPU
  コストがかかります。タイトなループでの呼び出しは避けてください。

---

## 関連ドキュメント

- [ツールリファレンス](tools.md#高度なデバッグピクセル履歴--シェーダーデバッグ)
- [シナリオ D1 — ピクセルの色が間違っている](examples/pixel-history.md)
- [シナリオ D2 — ピクセルシェーダーデバッグ](examples/shader-debugging.md)
- [シナリオ D3 — 深度テスト棄却](examples/depth-rejection.md)
- [シナリオ D4 — 頂点シェーダーデバッグ](examples/vertex-debugging.md)
- [シナリオ D5 — コンピュートシェーダーの NaN](examples/compute-debugging.md)
- [ジオメトリ・メッシュ調査](geometry.md)
- [GPU パフォーマンス分析](performance.md)
