# RenderEyeMCP — 開発状況と今後の方針まとめ

2026年10月30日｜次の設計議論に向けた整理

## 1. プロジェクトの目的

RenderEyeMCP は、RenderDocとAI Coding Agent（Claude Code、Codexなど）を接続し、グラフィックスデバッグを支援するOSSプロジェクト。

基本思想は、開発者が普段使用しているRenderDocを、そのままCoding Agentから調査できるようにすること。

Unity、Unreal Engine、RenderDoc GUIから開かれたCaptureを対象に、AgentがDrawCall、Pipeline State、GPU Resource、Shaderなどの情報を取得し、問題の原因を分析する。

RenderDocの代替や独自GPU Debuggerの開発は目的としない。

## 2. これまでのロードマップ

| Phase | 内容                                 |
| ----- | ---------------------------------- |
| 0〜4   | 基本機能、RenderDoc Extension、MCP連携     |
| 5〜5.5 | インストーラー、配布、README改善                |
| 6     | Shared IPC Service、複数Agent対応       |
| 7     | RenderDoc GUIとロード済みCaptureの検出      |
| 8     | DrawCall、Event、Pipeline State      |
| 9     | GPU Resource、Texture / Buffer情報    |
| 10    | Shader Inspection、Reflection       |
| 11    | Render Target、Texture画像、Pixel値     |
| 12    | リリース準備、日英ドキュメント                    |
| 13    | GPU Performance Analysis           |
| 13.1  | Performance AnalysisのE2E実行シナリオ     |
| 14    | Geometry、Vertex / Index、Post-VS    |
| 15    | Pixel History、Shader Debugging     |

## 3. 現在の技術方針

Coding Agents

Claude Code / Codex / MCP Clients

RenderEyeMCP

MCP Server / Shared IPC Service

RenderDoc Extension

Replay API / GUI State / Capture Inspection

RenderDoc GUI

Existing Capture / Replay Context

今後も以下を維持する。

- RenderDoc GUIを状態の正本（Source of Truth）とする。
- CaptureをAgentが開き直すことを要求しない。
- 複数Agentが同じRenderDocを安全に利用できる。
- Replay操作は適切に調停し、GUIの状態を不用意に変更しない。
- Resource、Event、Captureの識別を厳密にする。
- MCP Toolは情報取得を担当し、分析や原因推定はCoding Agentに任せる。

## 4. 今後の主軸

RenderDocのAPIで公開されている主要な情報取得機能を利用する段階まで進んだため、今後は機能の数を増やすよりも、次の2分野を重視する。

### A. Stability & Reliability

最優先

| 領域                  | 改善方針                                      |
| ------------------- | ----------------------------------------- |
| IPC                 | 再接続、切断、タイムアウト、クラッシュ復旧                     |
| Multi-Agent         | 同時アクセス、Replay競合、リソース所有権                   |
| RenderDoc Lifecycle | 起動、終了、Capture切り替え、Extension再接続            |
| Replay Safety       | GPU Counter、Post-VS、Shader Debuggingの実行調停 |
| Resource Management | Debug Trace、Replay Output、キャッシュの解放        |
| Error Handling      | 構造化エラー、部分失敗、Unsupportedの明示                |
| Testing             | 自動回帰テスト、実CaptureでのE2Eテスト                  |

特に重要なのは、Agentの不適切なTool呼び出しや途中切断によって、RenderDocが不安定にならないこと。

また、RenderEyeMCPの更新時に、以前動作していたGPUデバッグ機能を壊さないことを重視する。

### B. Cross-Platform Support

Windows-firstを維持しながら対応を拡大

| 領域           | 改善方針                                |
| ------------ | ----------------------------------- |
| Windows      | 主力環境として品質維持                         |
| Linux        | RenderDoc Extension、IPC、配布、起動の対応改善  |
| macOS        | RenderDoc本体の対応状況と制約を確認して対応範囲を判断     |
| IPC          | OS固有の通信・プロセス管理を抽象化                  |
| Installation | OSごとに簡単な導入方法を提供                     |
| CI           | Windows / Linux / macOSで実行可能なテストを分離 |
| Packaging    | Wheel、依存関係、Extension配布の互換性確保        |

マルチプラットフォーム対応では、RenderDoc自体が対応していない機能をRenderEyeMCP側で無理に再実装しない 方針とする。

RenderDocのAPI、Graphics API、Replay環境による差異は、Capabilityとして公開する。

## 5. 次の開発ロードマップ案

今後は大きな機能追加ではなく、品質改善フェーズとして整理する。

| Phase案 | テーマ                            | 目的                          |
| ------ | ------------------------------ | --------------------------- |
| 16     | Reliability Hardening          | IPC、Replay、Lifecycleの安定化    |
| 17     | Cross-Platform Foundation      | OS依存部分の整理とLinux対応強化         |
| 18     | Cross-Platform Distribution    | インストール、Packaging、CI整備       |
| 19     | E2E Regression & Compatibility | 実Capture・複数Agent・複数OSの検証    |
| 継続     | Maintenance                    | RenderDoc API追従、バグ修正、ドキュメント |

番号や範囲は今後の議論で調整可能。

## 6. 基本的な非目標

今後も以下は原則として対象外とする。

- RenderDocのGPU Replay機能を独自に再実装する。
- 独自のGPU ProfilerやShader Debuggerを開発する。
- RenderDoc GUIを置き換える。
- Coding Agent専用の独自診断AIを内蔵する。
- 特定GPUベンダーの非公開APIに強く依存する。
- RenderDoc本体の未対応プラットフォームを独自に完全サポートする。

RenderDocで新しいAPIが公開された場合は、その価値と保守コストを評価したうえで機能を追加する。

## 7. 次の議論で決めたいこと

今後の設計で最も重要なのは、次の3点だと思います。

① Shared IPC Serviceの長期安定性

RenderDoc GUI、MCP Process、Shared IPC Serviceがそれぞれ独立して終了・再起動しても、接続関係と状態が安全に復旧する設計をどこまで保証するか。

② Linux対応の優先範囲

Windowsと完全に同じ機能を目指すのか、まずはExtension接続・Capture情報・基本的なReplay Inspectionを確実に使えるようにするのか。

③ RenderDoc APIのバージョン互換性

RenderDocの更新でExtension APIが変化したとき、複数バージョンへの対応、Capability Detection、最低サポートバージョンをどのように管理するか。

## まとめ

RenderEyeMCPは、主要なGPU情報取得・デバッグ機能の実装を目指すロードマップを一通り定義した段階にあります。

今後のプロジェクト方針は次のように整理できます。

「機能拡張中心の開発」から「信頼性・互換性・マルチプラットフォーム対応中心の開発」へ移行する。

RenderDocの進化に追従しながら、既存のCoding Agentワークフローをより安定して使えるOSSとして成熟させることを目指します。
