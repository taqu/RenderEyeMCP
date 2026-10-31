[English](../../en/examples/active-capture.md) | [日本語](active-capture.md)

# シナリオA — 開いているCaptureを調べる

## 問題

エンジン(またはUnity/Unreal)でFrameをキャプチャし、RenderDocで開いています。何も
開き直さずに、*その*Captureをエージェントに扱ってほしい状況です。

## 準備

1. RenderEyeMCP拡張機能を有効にしたRenderDocが起動している。
2. Captureが開いている。Event Browserで適当なEventを選択しておく。

## プロンプト例

**クイック調査:**
> RenderDocで今開いているCaptureを調べて、使っているGraphics API、キャプチャされた
> Frame、選択中のEventを教えてください。

**詳細な調査:**
> RenderDocで開いているCaptureの全体像を教えてください。Graphics API、GPU、Frame番号、
> 総Event数、DrawCall数、Dispatch数を確認してください。さらに、現在選択中のEventの
> 名前とEvent IDも教えてください。

## 調査内容

- どのRenderDocウィンドウが接続していて、それぞれ何のCaptureを読み込んでいるか
- 読み込まれたCaptureのGraphics API、GPUベンダー、Frame番号、統計サマリー(総Event数、DrawCall数、Dispatch数)
- Event Browserで現在選択されているEventのIDとAPI呼び出し名

## 期待される結果

- ロード状態と`.rdc`ファイルのパス
- `D3D12`などの`api`、Frame番号、`{"total_events": 2370, "draw_calls": 533, "dispatches": 17}`のような統計値
- RenderDocでハイライトされているEIDと一致するSelected Event IDと`ID3D12GraphicsCommandList::DrawIndexedInstanced()`のような名前

## 結果の解釈

エージェント → MCPサーバー → 共有サービス → 拡張機能 → あなたのRenderDocウィンドウ、
という経路全体が動いていることを確認できます。選択中のEventがマーカーや`Present`だと、
以降のシナリオでは「Shaderが未Bind」になります。先に進む前にDrawCallを選択してください。

## 制限事項

- 複数のRenderDocウィンドウが接続していると、エージェントはどれかを選ぶ必要があります
  (`status: ambiguous`)。どのCaptureのことか伝えてください。
- Captureによっては`capture_time`が`0`になります。

## 関連ツール

`list_renderdoc_sessions`、`get_renderdoc_session_state`、`get_current_capture`、
`get_current_capture_info`、`get_selected_event`、`list_capture_events` —
[Toolリファレンス](../tools.md#セッションとcapture)を参照。
