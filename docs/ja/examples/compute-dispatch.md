[English](../../en/examples/compute-dispatch.md) | [日本語](compute-dispatch.md)

# シナリオF — Compute Shaderの出力がおかしい

## 問題

Compute Shaderが想定外の結果(0、ゴミ値、途中までしか埋まっていないBuffer)を書き込んで
います。

## 準備

RenderDocでそのDispatchを選択します。探すときはエージェントに
「このCaptureのDispatchを、スレッドグループ数と一緒に一覧表示してください。」と頼むと
便利です。

## プロンプト例

**クイック調査:**
> 選択中のCompute Dispatchを調べてください。Dispatchの次元、Shaderリソースの
> Binding、Constant Buffer、出力用のStorage Bufferを確認し、出力の先頭の数要素を
> 確認してください。

**詳細な調査:**
> 選択中のCompute Dispatchが想定外の出力を生成しています。スレッドグループの次元と
> データサイズとの関係を調べてください。すべてのリソースBindingを確認して、入力と出力の
> Bufferが正しくBindされているか確認してください。Constant Bufferの値を読んでおかしなものを
> 報告してください。その後、出力Bufferの先頭要素を読んで内容を説明してください。

**フォローアップ (任意):**
> Compute Shaderの逆アセンブルでnumthreads宣言を探し、スレッドグループ数が全要素を
> 処理するのに十分かどうか確認してください。

## 調査内容

- Dispatchの次元(X、Y、Z軸のスレッドグループ数)と、それが処理するデータサイズに対して十分かどうか
- どのCompute Shaderがバインドされているか、エントリポイントとスレッドグループサイズの宣言
- 全リソースBinding: 読み取り専用の入力スロット、読み書き可能な出力スロット(UAV)、バインドされていないスロットがないか
- Constant Bufferの内容。特に早期リターンの原因になり得る件数・Stride・時間値
- 出力BufferまたはTexture UAVの先頭要素が正しく書き込まれているか

## 期待される結果

- `[16, 8, 16]`のようなDispatchの次元
- `cbuffer Params → ResourceId::1401`、`InputData → ResourceId::503`、`OutputData (UAV) → ResourceId::505`のようなBinding
- デコードした定数値と出力の先頭要素

## 結果の解釈

- **Dispatchの次元はスレッド数ではなく、スレッドグループ数です。** 論理的な処理量は
  軸ごとに`グループ数 × numthreads`です。1000要素のBufferを`numthreads(64,1,1)`で処理する
  なら最低16グループ必要で、15グループでは末尾が書かれません。`numthreads`は逆アセンブルか
  ソースで確認してください。
- **UAVが未Bind**、または想定外のリソースにBindされている → 出力が別の場所に行っています。
- 件数、Stride、時間などの**定数**が0や古い値だと、早期リターンの原因になりがちです。
- 出力は**選択中のEvent時点**、つまりこのDispatchのFrame内の位置で読みます。後のパスで
  上書きされるならDispatch自体を選択し、Dispatch前の状態が必要なら直前のEventを選択して
  ください。

## 制限事項

- 個々のスレッドの実行をステップ実行したり調べたりはできません(Shaderデバッグなし)。
- Structured Bufferには要素の構造体に合った`decode_layout`が必要です(1回の読み出しは
  100要素・16384バイトまで。`offset`でページ送り)。
- Indirect Dispatchの引数は特別扱いでデコードしません。必要なら引数Bufferを
  `read_buffer_data`で読んでください。

## 関連ツール

`get_selected_event`、`list_capture_events`、`list_shaders`、`get_shader_info`、
`get_shader_reflection`、`get_shader_bindings`、`get_shader_disassembly`、
`get_buffer_info`、`read_buffer_data`、`get_texture_statistics`、`get_pixel_value` —
[Toolリファレンス](../tools.md)を参照。
