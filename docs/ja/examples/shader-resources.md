[English](../../en/examples/shader-resources.md) | [日本語](shader-resources.md)

# シナリオC — Textureやマテリアルの値がおかしい

## 問題

マテリアルに違うTextureやデフォルト/仮のTextureが表示される、または値(色味、
Roughness、UVスケールなど)が想定と違います。

## 準備

そのマテリアルを描画しているDrawCallを選択します。

## プロンプト例

**クイック調査:**
> 選択中のDrawCallで使われているPixel Shaderを調べてください。TextureとSamplerの
> Bindingを一覧し、実際にBindされているリソースを特定して、関係するマテリアルの定数を
> 確認してください。

**詳細な調査:**
> 選択中のDrawCallが間違った外観のマテリアルをレンダリングしています。Pixel Shaderの
> 全リソースBindingを調べてください: 宣言された各Textureスロットについて、リソースが
> 実際にバインドされているか、バインドされている場合はその名前・フォーマット・サイズを
> 報告してください。次にマテリアルのConstant Bufferを読んで、Shader Reflectionから
> 得た名前でデコードしてください。欠損している、プレースホルダーがバインドされている、
> または想定外の値を持つバインディングを特定してください。

## 調査内容

- どのPixel Shaderがバインドされているか、それが宣言しているリソース(TextureとSamplerのスロット、変数名とオフセットを含むConstant Bufferのレイアウト)
- 宣言された各リソーススロットに実際に何かバインドされているか(リソースID、利用可能な場合は名前、フォーマット、次元)
- Reflectionの変数名と型を使ってデコードしたConstant Bufferの内容

## 期待される結果

- 宣言名(例: t0の`AlbedoMap`)とバインドされたリソースとその名前
  (例: `/textures/rock_albedo`)の対応表
- 欠けているものは`bound: false` / `resource_id: null`
- Reflectionの名前と並んだ定数のデコード値。例:
  `BaseColorTint = [1.0, 0.5, 0.5, 1.0]`

## 結果の解釈

- **宣言があるのに未Bind** → エンジンがそのスロットを設定していません。GPUはNullか
  古いディスクリプタを読んでいます。
- **Bindされているが名前・サイズ・フォーマットが想定外**(4×4のデフォルトTexture、色の
  はずが`R8_UNORM`など) → 違うアセット、またはフォールバックがBindされています。
- **定数がおかしい**(0、NaN、極端に大きい) → Bufferを埋めるエンジン側のコードと、
  使ったオフセットがReflectionのレイアウトと合っているかを確認してください。

これらはDrawCall 1つについての観察です。値が*間違い*かどうかは、マテリアルが本来
持つべき内容によります。期待値がわかっていれば、エージェントに伝えてください。

## 制限事項

- Samplerステートの詳細(フィルタリング、アドレッシング)は、Reflectionの宣言の範囲に
  限られます。
- 値は選択中のEvent時点で読みます。Frameの後半で更新されるリソースは、その時点の状態です。
- 複雑なパッキング(配列、構造体、行列)のConstant Bufferには、パッキング規則を反映した
  `decode_layout`が必要です。エージェントがReflectionのオフセットから組み立てる必要が
  あります。
- 読み出しは1回あたり16384バイト、デコードは100要素までです。

## 関連ツール

`list_shaders`、`get_shader_info`、`get_shader_reflection`、`get_shader_bindings`、
`get_texture_info`、`get_resource_info`、`read_buffer_data`、`get_texture_image` —
[ShaderとReflection](../tools.md#shaderとreflection)を参照。
