[English](../../en/examples/active-capture.md) | [日本語](active-capture.md)

# シナリオA — 開いているCaptureを調べる

## 問題

エンジン(またはUnity/Unreal)でFrameをキャプチャし、RenderDocで開いています。何も
開き直さずに、*その*Captureをエージェントに扱ってほしい状況です。

## 準備

1. RenderEyeMCP拡張機能を有効にしたRenderDocが起動している。
2. Captureが開いている。Event Browserで適当なEventを選択しておく。

## プロンプト例

> RenderDocで今開いているCaptureを調べて、使っているGraphics API、キャプチャされた
> Frame、選択中のEventを教えてください。

## 調査の流れ

1. **GUIセッションの検出** — `list_renderdoc_sessions` / `get_current_capture`:
   どのRenderDocウィンドウが接続していて、それぞれ何を読み込んでいるか。
2. **Captureの特定** — `get_current_capture_info`: API、GPUベンダー、Frame番号、
   Event/DrawCall/Dispatchの数。
3. **選択中のEvent** — `get_selected_event`: 選択したEIDとAPI呼び出し。
4. 必要なら`list_capture_events`(`flags_filter: drawcall`)で全体像をつかむ。

## 確認できること

- `.rdc`ファイルのパス付きの`status: loaded`。
- `D3D12`などの`api`、`frame_number`、
  `{"total_events": 2370, "draw_calls": 533, "dispatches": 17}`のような`statistics`。
- RenderDocでハイライトされているEIDと一致する`selected_event_id`と、
  `ID3D12GraphicsCommandList::DrawIndexedInstanced()`のような名前。

## 解釈

エージェント → MCPサーバー → 共有サービス → 拡張機能 → あなたのRenderDocウィンドウ、
という経路全体が動いていることを確認できます。選択中のEventがマーカーや`Present`だと、
以降のシナリオでは「Shaderが未Bind」になります。先に進む前にDrawCallを選択してください。

## 制限

- 複数のRenderDocウィンドウが接続していると、エージェントはどれかを選ぶ必要があります
  (`status: ambiguous`)。どのCaptureのことか伝えてください。
- Captureによっては`capture_time`が`0`になります。

## 関連Tool

`list_renderdoc_sessions`、`get_renderdoc_session_state`、`get_current_capture`、
`get_current_capture_info`、`get_selected_event`、`list_capture_events` —
[Toolリファレンス](../tools.md#セッションとcapture)を参照。
