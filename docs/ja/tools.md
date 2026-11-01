[English](../en/tools.md) | [日本語](tools.md)

# MCP Toolリファレンス

RenderEyeMCPは**58個のTool**を登録しています。通常、Toolを呼ぶのはエージェントであり、
あなたが直接呼ぶ必要はありません。知っておくと、的確なプロンプトを書いたりエージェントの
実行ログを読んだりするのに役立ちます。

- [共通ルール](#共通ルール)
- [セッションとCapture](#セッションとcapture)
- [Event](#event)
- [Pipeline State](#pipeline-state)
- [リソースとBuffer](#リソースとbuffer)
- [ShaderとReflection](#shaderとreflection)
- [Render Target、Texture、Pixel](#render-targettexturepixel)
- [GPUパフォーマンス分析](#gpuパフォーマンス分析)
- [ジオメトリ・メッシュ調査](#ジオメトリメッシュ調査)
- [高度なデバッグ(ピクセル履歴 & シェーダーデバッグ)](#高度なデバッグピクセル履歴--シェーダーデバッグ)
- [CaptureファイルとRenderEyeMCPが管理するウィンドウ](#captureファイルとrendereyemcpが管理するウィンドウ)
- [診断](#診断)
- [例](#例)

## 共通ルール

**読み取り専用。** *GUIの状態を変更*と書かれた5つを除き、すべてのToolは読み取り専用です。
調査用のToolがRenderDocで選択中のEventを変更することはありません。

**選択中のEvent。** 調査用のToolは、**RenderDoc GUIで選択中のEvent**を対象にします。
`get_pipeline_state`の`event_id`は、選択中のEventと一致するかの確認にだけ使われます
(一致しないと`error: event_not_selected`)。`get_capture_event`は選択を変えずに
任意のEventの情報を返します。

**`instance_id`(省略可、既定値`""`)。** すべての調査用Toolで指定できます。空の場合は、
接続中のRenderDocセッションが1つならそれを、またはCaptureを読み込んでいるセッションが
1つならそれを選びます。該当が複数あると`status: ambiguous`と`sessions`一覧が返るので、
そのいずれかの`instance_id`を指定して呼び直します。IDは`list_renderdoc_sessions`で
確認できます。

**識別子。** リソースIDは`ResourceId::805`のような文字列、Event IDはRenderDocに表示される
EIDです。どちらも今読み込まれているCaptureの中でのみ意味を持ちます。このページの値は
例であり、あなたのCaptureに存在するIDではありません。

**調査結果にはすべて**、読み取り元のCaptureを示す`_capture_path`が含まれます。

**共通の結果**

| 結果 | 意味 |
|------|------|
| `status: no_renderdoc_connected` | 拡張機能付きのRenderDocウィンドウが接続されていない |
| `status: ambiguous` | 該当するセッションが複数ある。`instance_id`を指定する |
| `error: no_capture_loaded` / `capture_loading` | 接続済みだが、Captureの準備ができていない |
| `error: resource_not_found` | 読み込み中のCaptureにそのリソースIDがない |
| `error: shader_not_bound` | 選択中のEventにそのステージのShaderがない |
| `error: timeout` | 拡張機能が30秒以内に応答しなかった(RenderDocが処理中、またはダイアログで止まっている) |
| `error: extension_error` | RenderDocがエラーを返した。詳細は`message` |
| `error: result_too_large` | 応答が16 MiBのIPCメッセージ上限を超えた。要求するデータ量を減らす |

## セッションとCapture

| Tool | パラメーター | 戻り値 |
|------|--------------|--------|
| `list_renderdoc_sessions` | — | `sessions[]`: `instance_id`、`process_id`、`connection_state`(`connected`/`disconnected`/`unknown`)、`renderdoc_version`、`capture`(`state`、`path`)、切断済みセッションの`last_known_capture` |
| `get_renderdoc_session_state` | `instance_id`(必須) | 上記の1セッション分。不明なIDは`error: session_not_found` |
| `get_current_capture` | `instance_id` | `status`: `loaded`、`no_capture_loaded`、`capture_loading`、`ambiguous`、`session_not_found`、`session_disconnected`、`no_renderdoc_connected`。読み込み済みなら`capture_path`、`instance_id` |
| `get_current_capture_info` | `instance_id` | `api`(`D3D11`/`D3D12`/`OpenGL`/`Vulkan`)、`vendor`、`frame_number`、`degraded`、`statistics`(`total_events`、`draw_calls`、`dispatches`)、`resource_count` |

手動、Unity、Unreal Engineなど、どの方法で開いたCaptureでも使えます。

## Event

| Tool | パラメーター | 戻り値 / 上限 |
|------|--------------|---------------|
| `list_capture_events` | `limit`(50、**最大200**)、`offset`(0)、`include_markers`(true)、`flags_filter`(`""`、`drawcall`、`dispatch`)、`parent_event_id`(0 = 最上位) | `events[]`(`event_id`、`name`、`action_type`、`flags`、`num_indices`、`num_instances`、`dispatch_dimension`、`child_count`)、`total`、`has_more` |
| `get_capture_event` | `event_id`(必須) | Eventとその`children`。選択は変更しない |
| `get_selected_event` | — | `selected_event_id`、`current_event_id`、`selected_action`(`ID3D12GraphicsCommandList::DrawIndexedInstanced()`のような名前) |

`flags_filter`を指定すると、Frame全体を平坦化した一覧になります。

## Pipeline State

`get_pipeline_state` — `section`(既定値`summary`)、`event_id`(0 = 選択中のEvent)。

| `section` | 内容 |
|-----------|------|
| `summary` | `pipeline_type`(`graphics`/`compute`)、`topology`、使用中のステージとエントリポイント、`render_target_count`、`has_depth_target` |
| `input_assembly` | `topology`、`index_buffer`(`resource_id`、`offset`、`stride`)、`vertex_buffers[]` |
| `shaders` | ステージごとのShader |
| `rasterizer` | `viewports[]`、`scissors[]`(全スロット。未使用のスロットはサイズ0) |
| `depth_stencil` | **注意書きのみ。** Depth/StencilステートはRenderDocのAPI共通インターフェースでは取得できない |
| `output_merger` | `render_targets[]`(`resource_id`、`format`)、`depth_target` |
| `resources` | `bindings[]`: ステージ、`binding_type`(`cbuffer`/`texture`/`uav`)、`resource_id` |

取得できないもの: Cullモード、Fillモード、深度比較関数/深度書き込み、Stencil、Blend
ステート、頂点入力レイアウトの属性(代わりにVertex Shaderの入力シグネチャを使います)。

## リソースとBuffer

| Tool | パラメーター | 戻り値 / 上限 |
|------|--------------|---------------|
| `list_resources` | `resource_type`(`all`/`texture`/`buffer`)、`name_filter`(部分一致)、`limit`(50、**最大500**)、`offset` | `resources[]`(`resource_id`、`name`、`category`)、`total`、`has_more` |
| `get_resource_info` | `resource_id`(必須) | 名前、種類、TextureまたはBuffer固有の詳細 |
| `get_texture_info` | `resource_id`(必須) | `width`、`height`、`depth`、`array_size`、`mip_levels`、`sample_count`、`format`、`texture_type`、`usage`、`byte_size` |
| `get_buffer_info` | `resource_id`(必須) | `byte_size`、`usage`、`gpu_address` |
| `read_buffer_data` | `resource_id`(必須)、`offset`(0)、`length`(256、**最大16384バイト**)、`output_format`(`hex`/`base64`/`bytes`)、`decode_layout`(省略可) | `data`、`buffer_byte_size`。`decode_layout`指定時は`decoded.elements[]`も |

`decode_layout` = `{"stride": N, "element_count": N(最大100), "fields": [{"name", "type", "offset", "components"(1〜16)}]}`。
フィールドの型: `float16`、`float32`、`float64`、`int8`/`16`/`32`/`64`、`uint8`/`16`/`32`/`64`。

Bufferの内容は選択中のEvent時点のものです。Constant Bufferを読むときは、
`get_shader_bindings`が返す`byte_offset`を`offset`に指定してください。多くのエンジンは
1つの大きなBufferからConstant Bufferを切り出して使っています。

## ShaderとReflection

`stage`には`Vertex`/`vs`、`Hull`/`hs`、`Domain`/`ds`、`Geometry`/`gs`、
`Pixel`/`ps`/`fragment`、`Compute`/`cs`を指定できます(大文字小文字は区別しません)。

| Tool | パラメーター | 戻り値 / 上限 |
|------|--------------|---------------|
| `list_shaders` | — | 選択中のEventで使われているShader: `stage`、`shader_id`、`entry_point`、Reflectionの件数、`has_debug_info` |
| `get_shader_info` | `stage`(必須) | ID、エントリポイント、リソース数、`encoding`(例: `DXIL`)、`disassembly_targets`、`source_file_count` |
| `get_shader_reflection` | `stage`(必須)、`section`(`all`/`input`/`output`/`cbuffers`/`resources`/`samplers`) | シグネチャ、変数(`name`、`byte_offset`、`type`)付きのConstant Buffer、読み取り専用/読み書きリソースの宣言。各リストの変数は最大100 |
| `get_shader_bindings` | `stage`(必須) | 宣言されたcbuffer/Texture/UAVごとに`bound`、`resource_id`(未BindならNull)、`byte_offset`、`byte_size` |
| `get_shader_disassembly` | `stage`(必須)、`target`(`""` = 既定)、`offset`、`limit`(**最大200行**)、`search` | `lines[]`、`total_lines`、`has_more`、`available_targets` |
| `get_shader_debug_info` | `stage`(必須)、`file_index`(0)、`start_line`(0)、`max_lines`(100、**最大500**) | Shaderに埋め込まれていれば、ソースファイルと指定範囲の行 |

Shaderデバッグ(ステップ実行、呼び出しごとの変数値)は未実装です。

## Render Target、Texture、Pixel

| Tool | パラメーター | 戻り値 / 上限 |
|------|--------------|---------------|
| `get_render_targets` | — | `color_targets[]`(`index`、`resource_id`、`bound`、`width`、`height`、`format`、`mip`、`slice`)、`depth_target`、`has_depth` |
| `get_texture_image` | `resource_id`(必須)、`mip`(0)、`array_slice`(0)、`max_dim`(1024) | MCPの**画像**(PNG)とメタデータ。Mipが`max_dim`より大きいと`error: image_too_large`と`suggested_mip`(またはNull)、`required_max_dim` |
| `get_pixel_value` | `resource_id`(必須)、`x`、`y`、`mip`、`array_slice`、`sample`、`coords`(`{x, y}`のリスト、**最大16**) | 型付きの生の値`float[]`、`uint[]`、`sint[]`(左上原点)。`coords`指定時は`pixels[]`。Mipの範囲外は`error: out_of_bounds` |
| `get_texture_statistics` | `resource_id`(必須)、`mip`、`array_slice`、`include_histogram`(false)、`hist_min`(0.0)、`hist_max`(1.0) | チャンネルごとの`min`と`max`。必要ならヒストグラム(最大256ビン) |

Textureの内容は選択中のEvent時点のものです。PNGプレビューは表示用の変換
(RenderDoc自身の保存処理)を経ています。数値で判断するときは画像ではなくPixel値を
使ってください。`get_texture_image`はPNG全体を1メッセージで送るため、非常に大きい
Textureでは小さいMipを指定する必要があることがあります。

## CaptureファイルとRenderEyeMCPが管理するウィンドウ

これらのToolは、GUIで開いているCaptureを調べる今のワークフローより前からあるものです。
ディスク上の`.rdc`ファイルと、RenderEyeMCP自身が起動したRenderDocウィンドウを扱います。
自動テストはありますが、今回のリリースでは**実機検証をしていません**。ウィンドウの
フォーカス/クローズにはWindows APIを使います。

| Tool | 用途 | GUIの状態 |
|------|------|-----------|
| `capture_list`、`capture_get`、`capture_latest` | Captureレジストリ(`RENDEREYE_CAPTURE_DIRS`内の`.rdc`)の検索 | 読み取り専用 |
| `capture_rescan` | 監視フォルダーを今すぐ再スキャン | 読み取り専用(レジストリは更新) |
| `capture_registry_status` | 監視の状態と件数 | 読み取り専用 |
| `capture_open` | 登録済みのCaptureをRenderDocで開く(`open_mode`: `new_window`、`reuse`、`replace`) | **GUIの状態を変更** |
| `operation_get` | `capture_open`の処理状況 | 読み取り専用 |
| `instance_list`、`instance_gui_state` | RenderDocのプロセス/ウィンドウと、報告された状態 | 読み取り専用 |
| `session_list`、`session_get` | `capture_open`で作成したセッション | 読み取り専用 |
| `session_focus` | セッションのウィンドウを前面に出す | **GUIの状態を変更** |
| `session_close` | 管理下で保護されていないセッションのウィンドウを閉じる | **GUIの状態を変更** |
| `session_protect` | セッションをクローズ/置き換えから保護する | セッション記録を変更 |

あなた(またはエンジン)が開いたウィンドウを、これらのToolが閉じたり置き換えたりする
ことはありません。

## 診断

| Tool | 戻り値 |
|------|--------|
| `server_status` | サーバー名とバージョン、OS、Python、RenderDocを検出できたか、IPCリスナーの状態、拡張機能の接続数とセッション数 |

## 例

以下の値は説明用です。

既定のセッション選択(`instance_id`なし):

```json
{"tool": "get_current_capture", "arguments": {}}
```

RenderDocウィンドウが2つ開いているときにセッションを明示する:

```json
{"tool": "get_selected_event", "arguments": {"instance_id": "591ad434-1100-4c5c-ba03-3aa0b1361258"}}
```

選択を変えずにEventの情報を見る:

```json
{"tool": "get_capture_event", "arguments": {"event_id": 1039}}
```

`get_render_targets`で得たリソースIDを使う:

```json
{"tool": "get_texture_info", "arguments": {"resource_id": "ResourceId::805"}}
```

範囲を限定したBuffer読み出しを`float4`としてデコードする(オフセット0のConstant Buffer):

```json
{"tool": "read_buffer_data", "arguments": {
  "resource_id": "ResourceId::1401", "offset": 0, "length": 48,
  "decode_layout": {"stride": 16, "element_count": 3,
                    "fields": [{"name": "v", "type": "float32", "offset": 0, "components": 4}]}}}
```

TextureのプレビューとPixel値:

```json
{"tool": "get_texture_image", "arguments": {"resource_id": "ResourceId::805", "max_dim": 1280}}
{"tool": "get_pixel_value", "arguments": {"resource_id": "ResourceId::815", "coords": [{"x": 640, "y": 360}, {"x": 10, "y": 10}]}}
```

## GPUパフォーマンス分析

GPUパフォーマンスToolは2段階で動作します: **測定**（GPUを使用）と**分析**（保存済み結果を使用、GPU不要）。
分析Toolを呼ぶ前に、必ず `list_gpu_counters` → `collect_gpu_counters` を実行してください。

### `list_gpu_counters`

ロード中のCaptureで利用可能なGPUパフォーマンスカウンタを列挙します。
各カウンタの `counter_id`、`name`、`unit`、`result_type` を返します。
利用可能なカウンタはGPU、ドライバ、グラフィクスAPI、RenderDocのバージョンによって異なります。

| パラメータ | デフォルト | 備考 |
|-----------|---------|-------|
| `instance_id` | `""` | オプションのセッションID |

### `collect_gpu_counters`

ロード中のCaptureの全EventのGPUカウンタ値を収集します。
GPUリプレイを伴う `FetchCounters()` を実行します — **読み取り専用ではありません**。
後続の分析Toolで使用する `measurement_id` を返します。

| パラメータ | デフォルト | 備考 |
|-----------|---------|-------|
| `counter_ids` | 必須 | `list_gpu_counters` で取得した整数IDのリスト |
| `instance_id` | `""` | オプションのセッションID |
| `repeats` | `1` | 収集回数（1〜5）; 複数回は平均値を算出 |

### `get_gpu_measurement_status`

保存済み測定の状態を確認します。

| パラメータ | デフォルト | 備考 |
|-----------|---------|-------|
| `measurement_id` | 必須 | `collect_gpu_counters` が返すID |

### `get_gpu_timings`

完了した測定からEvent単位のカウンタ値を取得します。GPUを再実行しません。

| パラメータ | デフォルト | 備考 |
|-----------|---------|-------|
| `measurement_id` | 必須 | — |
| `counter_id` | 自動 | 未指定時は最初のタイミング/継続時間カウンタ |
| `min_value` | なし | 最小値フィルタ |
| `sort_by` | `value_desc` | `value_desc`, `value_asc`, `event_id`, `event_id_desc` |
| `limit` / `offset` | `100` / `0` | ページネーション |

### `get_performance_summary`

カウンタ値の降順で最もコストの高いGPU Eventをランキングします。

| パラメータ | デフォルト | 備考 |
|-----------|---------|-------|
| `measurement_id` | 必須 | — |
| `counter_id` | 自動 | — |
| `top_n` | `20` | 最大100 |

### `get_render_pass_performance`

デバッグマーカー階層（レンダーパス）ごとにカウンタ結果を集計します。
`aggregated_duration` はリーフEventの値の**合計**であり、パスのGPUウォールクロック経過時間ではありません。

| パラメータ | デフォルト | 備考 |
|-----------|---------|-------|
| `measurement_id` | 必須 | — |
| `counter_id` | 自動 | — |
| `instance_id` | `""` | Eventの階層情報取得に必要 |

### `get_pipeline_statistics`

測定結果をパイプライン統計カウンタ（頂点呼び出し数、プリミティブ数、ピクセルシェーダ呼び出し数など）に絞り込みます。

| パラメータ | デフォルト | 備考 |
|-----------|---------|-------|
| `measurement_id` | 必須 | — |
| `event_id` | なし | 単一のドローコールに絞り込む |
| `limit` / `offset` | `100` / `0` | ページネーション |

## ジオメトリ・メッシュ調査

すべてのジオメトリToolは、RenderDoc GUIで**選択中のEvent**に対して動作します。`event_id`は選択確認用のみ（不一致で`error: event_not_selected`）。`get_post_vs_geometry`はリプレイ処理を実行するため**読み取り専用ではありません**。

| Tool | パラメータ | 戻り値 / 制限 |
|------|-----------|------------------|
| `get_draw_geometry_info` | `event_id`(0), `instance_id` | `is_indexed`, `is_instanced`, `is_indirect`, `num_indices`, `num_instances`, 描画オフセット（`index_offset`, `base_vertex`, `instance_offset`）, `topology`, `vertex_buffers[]`, `index_buffer` |
| `get_vertex_input_layout` | `event_id`(0), `instance_id` | `attributes[]`（name, format, `component_type`, `component_count`, `component_byte_width`, `vertex_buffer`スロット, `byte_offset`, `per_instance`）, `vertex_buffers[]`, `index_buffer`, `vs_input_signature[]` |
| `get_mesh_indices` | `event_id`(0), `first_index`(0), `count`(100, **最大1000**), `instance_id` | `indices[]`（`position`, `raw_index`, `vertex_ref`）, `index_byte_stride`, `base_vertex` |
| `get_mesh_vertices` | `event_id`(0), `first_vertex`(0), `count`(10, **最大100**), `attributes`（リスト, 省略可）, `instance_id` | `vertices[]`（`vertex_id`, `attributes{}`）— 頂点単位のみ; インスタンス単位属性は含まない |
| `get_post_vs_geometry` | `event_id`(0), `instance`(0), `view`(0), `stage`(`vs_out`/`vs_in`/`gs_out`), `max_vertices`(50, **最大100**), `instance_id` | `vertices[]`（`SV_Position_clip` XYZW, `SV_Position_ndc` X/W・Y/W・Z/W, その他VSの出力）; `output_signature[]`, `topology`, `num_indices` — **リプレイ状態を変更** |
| `get_mesh_statistics` | `event_id`(0), `max_vertices`(200, **最大500**), `instance_id` | `position_analysis`: `bounding_box`（オブジェクト空間 min/max XYZ）, `valid_vertex_count`, `nan_component_count`, `inf_component_count`, `vertices_analyzed`; `sampled`フラグ |

`get_post_vs_geometry`の座標はクリップ空間（遠近除算前）です。`SV_Position_ndc`は`{x/w, y/w, z/w}`を返し、wがゼロまたはゼロ付近の場合は省略されます。`get_mesh_statistics`のバウンディングボックスは頂点バッファ入力（変換前オブジェクト空間）を反映します。

## 高度なデバッグ(ピクセル履歴 & シェーダーデバッグ)

RenderDocのPixel HistoryおよびShader Debug Trace APIを使用した、ピクセルレベル・シェーダーレベルのGPUデバッグ用7ツール。

| Tool | 説明 |
|---|---|
| `get_pixel_history` | 選択ピクセルに影響した描画の変更履歴を取得（リプレイ実行） |
| `debug_pixel_shader` | ピクセルシェーダーデバッグトレースを収集 |
| `debug_vertex_shader` | 頂点シェーダーデバッグトレースを収集 |
| `debug_compute_shader` | コンピュートシェーダーデバッグトレースを収集 |
| `get_shader_debug_trace` | 保存済みデバッグトレースのステップを取得 |
| `get_shader_debug_variables` | 特定ステップでの変数状態を再構築 |
| `get_shader_debug_status` | デバッグトレースのステータス確認・一覧取得 |

