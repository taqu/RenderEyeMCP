[English](../../en/examples/shader-resources.md) | [日本語](shader-resources.md)

# シナリオC — Textureやマテリアルの値がおかしい

## 問題

マテリアルに違うTextureやデフォルト/仮のTextureが表示される、または値(色味、
Roughness、UVスケールなど)が想定と違います。

## 準備

そのマテリアルを描画しているDrawCallを選択します。

## プロンプト例

> 選択中のDrawCallで使われているPixel Shaderを調べてください。TextureとSamplerの
> Bindingを一覧し、実際にBindされているリソースを特定して、関係するマテリアルの定数を
> 確認してください。

## 調査の流れ

1. `list_shaders` — Pixel ShaderがBindされていることを確認し、IDを得る。
2. `get_shader_reflection`(`stage: Pixel`、`section: resources`、続いて`cbuffers`) —
   Shaderが*宣言*しているもの: Texture/Samplerの名前とスロット、Constant Bufferの変数と
   バイトオフセット、型。
3. `get_shader_bindings`(`stage: Pixel`) — 宣言ごとに*実際に*何かがBindされているかと
   その`resource_id`。Constant Bufferは`byte_offset`と`byte_size`も。
4. Bindされた各Textureに`get_texture_info` / `get_resource_info` — 名前、サイズ、
   フォーマット、Mip数。
5. 各Constant Bufferを`byte_offset`から`read_buffer_data`し、Reflectionの変数から
   組み立てた`decode_layout`でデコードする(`float4`なら`float32`×4など)。
6. 必要なら、`get_texture_image`でBindされたTextureを表示する。

## 確認できること

- 宣言名(例: t0の`AlbedoMap`)と、Bindされたリソースとその名前
  (例: `/textures/rock_albedo`)の対応表。
- 欠けているものは`bound: false` / `resource_id: null`。
- Reflectionの名前と並んだ定数のデコード値。例:
  `BaseColorTint = [1.0, 0.5, 0.5, 1.0]`。

## 解釈

- **宣言があるのに未Bind** → エンジンがそのスロットを設定していません。GPUはNullか
  古いディスクリプタを読んでいます。
- **Bindされているが名前・サイズ・フォーマットが想定外**(4×4のデフォルトTexture、色の
  はずが`R8_UNORM`など) → 違うアセット、またはフォールバックがBindされています。
- **定数がおかしい**(0、NaN、極端に大きい) → Bufferを埋めるエンジン側のコードと、
  使ったオフセットがReflectionのレイアウトと合っているかを確認してください。

これらはDrawCall 1つについての観察です。値が*間違い*かどうかは、マテリアルが本来
持つべき内容によります。期待値がわかっていれば、エージェントに伝えてください。

## 制限

- Samplerステートの詳細(フィルタリング、アドレッシング)は、Reflectionの宣言の範囲に
  限られます。
- 値は選択中のEvent時点で読みます。Frameの後半で更新されるリソースは、その時点の状態です。
- 複雑なパッキング(配列、構造体、行列)のConstant Bufferには、パッキング規則を反映した
  `decode_layout`が必要です。エージェントがReflectionのオフセットから組み立てる必要が
  あります。
- 読み出しは1回あたり16384バイト、デコードは100要素までです。

## 関連Tool

`list_shaders`、`get_shader_info`、`get_shader_reflection`、`get_shader_bindings`、
`get_texture_info`、`get_resource_info`、`read_buffer_data`、`get_texture_image` —
[ShaderとReflection](../tools.md#shaderとreflection)を参照。
