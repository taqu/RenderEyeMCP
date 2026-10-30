なるほど。それならGoへの移植方針がかなり明確になります。

現在のRenderEyeMCPは、MCP BridgeとShared IPC Serviceが既にプロセスとして分離されている ため、RenderDoc Extensionを変更せずに、Goへの段階的な移植を進めやすい構造です。

ただし、インストールの煩わしさを解消する目的なら、MCP BridgeだけでなくShared IPC ServiceもGoへ移植するべき だと思います。

## 1. 現在と移植後の構成

現在：Python

Python MCP Bridge × N

Agentごと

stdio / MCP

Python Shared IPC Service

TCP 127.0.0.1:37020 / 独立デーモン

RenderDoc Extension

RenderDoc内部のPython APIを使用

移植後：Go

Go MCP Bridge × N

Native

stdio / MCP

Go Shared IPC Service

Native

TCP 127.0.0.1:37020 / 独立デーモン

RenderDoc Extension（変更なし）

既存のPython / RenderDoc Replay API

ポイントは、通信プロトコルとプロセス境界を維持したまま、Pythonの実装だけをGoへ置き換える ことです。

## 2. さらに、Goの実行ファイルを1種類に統合できる

ここで検討したいのは、MCP BridgeとShared IPC Serviceを別々のGo実行ファイルにする必要があるか、という点です。

私は、単一バイナリ・複数動作モード を推奨します。

例えば次のような構成です。

```
rendereye-mcp.exe
    ├── bridge mode  (default)
    └── service mode (internal)
```

起動例：

```
# Coding Agentが起動
rendereye-mcp.exe

# 内部的に起動されるShared IPC Service
rendereye-mcp.exe service
```

これなら配布物は原則として1つの実行ファイルで済みます。

MCP Bridgeは従来どおりstdioでCoding Agentと通信し、Shared IPC ServiceとはTCPで通信します。

### 注意：Serviceの起動競合

複数のAgentが同時にBridgeを起動するため、次の状態が発生します。

```
Claude Code → Go Bridge A ─┐
                           ├→ Go Shared IPC Service
Codex       → Go Bridge B ─┘
```

Bridge AとBridge Bが同時にService起動を試みても、実際に動作するServiceは1プロセスだけ でなければなりません。

このため、既存Phase 6で実装した競合解決ロジックを調査し、Goへ移植する必要があります。

ここは新設計にするより、既存の仕組みを維持する方が安全です。

TCPポート `127.0.0.1:37020` も、互換性維持のため当面変更する必要はありません。

## 3. 移植順序はShared IPC Serviceを先にする方がよい

前回はMCP Bridgeを先にGoへ移植する案を挙げましたが、今回の構成を踏まえると、少し考えを変えたいです。

| 順序 | 作業                               | 理由                        |
| -- | -------------------------------- | ------------------------- |
| 1  | IPC Protocolの仕様・互換性テスト           | Python / Go間の通信を固定        |
| 2  | Shared IPC ServiceをGoに移植         | 独立プロセスなので先に置換しやすい         |
| 3  | Python MCP BridgeからGo Serviceに接続 | 既存Toolを使って動作確認            |
| 4  | MCP BridgeをGoに移植                 | Tool定義・MCP応答の互換性維持        |
| 5  | 単一バイナリ化                          | Bridge / Serviceの起動モードを統合 |
| 6  | OS別ビルドと配布                        | Windows / Linux / macOS   |

この順番なら、途中で次の組み合わせを検証できます。

| Bridge | Shared IPC Service | 用途               |
| ------ | ------------------ | ---------------- |
| Python | Python             | 既存の基準実装          |
| Python | Go                 | IPC Service移植の検証 |
| Go     | Go                 | 最終構成             |
| Go     | Python             | 移行期間中の互換性検証（任意）  |

特にPython BridgeとGo Serviceの組み合わせで、Phase 8〜15のToolが正常に動作すれば、Shared IPC Service側の互換性を広く検証できます。

ただし、Serviceに共有データやJob管理がある場合は、その移植量が大きくなる可能性があります。まずコードの責務を調査する必要があります。

## 4. Python依存はどこまで残るか

| コンポーネント                  | 移植後                |
| ------------------------ | ------------------ |
| MCP Bridge               | Go                 |
| Shared IPC Service       | Go                 |
| RenderDoc Extension      | Python             |
| RenderDoc Replay APIアクセス | Python Extension経由 |
| インストーラー                  | Goまたは配布スクリプト       |
| ユーザー管理のPython環境          | 原則不要               |
| `uv` / `pip`             | 一般ユーザーには不要         |

RenderDoc ExtensionはRenderDocが提供するPython実行環境を利用する想定です。外部Pythonパッケージへの依存が存在する場合は、その扱いを別途確認する必要があります。

## 5. 改訂ロードマップ

次の開発段階はこのように整理できます。

| Phase | テーマ                                          |
| ----- | -------------------------------------------- |
| 16    | IPC Protocol Contract & Compatibility Tests  |
| 17    | Go Shared IPC Service                        |
| 18    | Go MCP Bridge                                |
| 19    | Single Binary & Cross-Platform Distribution  |
| 20    | Reliability / Migration / Python Deprecation |

ここまで完了すれば、Python版MCPサーバーを段階的に廃止し、Go版を正式な配布経路にできます。

PyPI配布についても、Go版移行後に互換パッケージとして残すか、GitHub Releases中心に切り替えるか判断すればよいでしょう。

## 結論

今回のアーキテクチャなら、RenderEyeMCPのGo移植はかなり合理的です。

特に重要なのは、現在のShared IPC Serviceを統合・廃止するのではなく、独立プロセスという構造を維持しながらGoに置き換える ことです。

これならPhase 6で確立した複数Agent対応を壊すリスクを抑えられます。

最終的には、次のような配布形態を目指せます。

```
RenderEyeMCP/
  rendereye-mcp.exe
  extension/
    ...
  rendereye.env
```

そしてユーザーが意識するのは、`rendereye-mcp.exe` をCoding Agentに登録することだけです。

次のPhase 16は、いきなりGoを書き始めるのではなく、既存IPC Protocolの仕様を確定し、PythonとGoで同じ通信ができることを保証する互換性テストを整備するフェーズ にするのがよいと思います。

これが、安定性と移植の容易さを両立させる一番重要な準備になるはずです。
