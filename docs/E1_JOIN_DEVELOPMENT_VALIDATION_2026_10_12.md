# 観測線端による接続補筆：実描画開発比較（2026-10-12）

**判定：直線16条件を支持。全体は25/26開発判定で、曲線対照1条件のFAILを保持。未知作品・学習・人の受入れは未達。**

## 結果

| 条件 | 件数 | 結果 |
|---|---:|---|
| 水平／垂直 × 2位置 × 4未完成率 | 16 | 全条件で従来gap1px→候補gap0px、2成分→1成分。F1は両方式1.0 |
| 完成 | 4 | 両方式Stop、補正Motorゼロ |
| ROI境界近傍 | 2 | gap1px→0px、保護外追加着墨ゼロ |
| 斜線 | 1 | 両方式unsupported-nonstraight-missing Stop |
| 曲線 | 1 | 想定したunsupported Stopに一致せずFAIL。実際はmultiple-missing-components Stop |
| 分岐／原画ROI境界に接触 | 2 | 両producerが対応するReferenceGeometryUnsupportedで入力拒否。Episodeなし |

24成立課題 × 2戦略 × noop/off/on = **144実P1 Episode**を作成・独立Replay・採点。16主要条件の96 Episodeは四つの元幾何familyの反復。独立96標本、未知作品への一般化、実機の検証とは扱わない。全成立armで保護外追加着墨ゼロ、noop白紙、両戦略の初期Motor digest／poststroke state／初期action数が一致。

## 固定ソースと環境

- 基準器 ImageProgram #81：`6d8e6399a2b0a44d08054a08b71b4a68d4d9e374`。
- 候補 ImageProgram #86：`ceb9c55f647d81cb5a14fa6934f2d45b09741d0c`。
- 評価器と事前登録runner：`fe75246cd0a781714889d57e23e9a06d95f8076c`（Arena #29の`7d08dd16ea9e72ad3f76bed2fb38301086aa6c32`にrunner・来歴拒否test・runbookを追加）。
- Codex Linux、Python 3.12.14。各Model自身のuv.lockでoffline sync：NumPy 2.5.3、Pillow 12.3.0、Pydantic 2.13.5、Ruff 0.16.7。
- 接続から取得した全blob、tree、commitをSHA一致で復元。各producerは別clean checkoutと自身の.venv。source Replay／scorerも同じproducer環境で実行。
- seed17、既定Body／pen／予算、同じ公開ROI。人がCanvasのgapを加工していない。

## 実行した検証

| 検証 | 結果 |
|---|---|
| 基準器 full scripts/check.py | 238/238、103.601秒、OK |
| 候補 full scripts/check.py | 248/248、106.756秒、OK |
| 元Arena #29 full suite（正しい基準器環境） | 123/123、31.909秒、OK |
| 本runner追加後Arena full suite | 126/126、40.299秒、OK、skipゼロ |
| 新規来歴拒否test | 3/3、OK |
| 候補Model Ruff全体 | PASS |
| 新規runner／test Ruff | PASS |

初回Arena suiteは候補Model環境で呼んだため、固定#81を要求する4テストが想定通り拒否。正しい基準器環境へ切り替えて123/123を確認し、runner追加後126/126も同じ環境で確認した。初回失敗をPASS件数に含めない。

Arena全体への追加lint診断には親branchの9件（import整列・未使用import）が残る。本PRはそれらを変更せず、全体Ruff PASSは主張しない。変更した2 PythonファイルのRuffはPASS。

## 曲線で分かったこと

曲線対照の実Eye差分はmissing=164px、excess=52px、missing_component_count=2。両方式とも`status=unknown / multiple-missing-components`となり、補正Motorはゼロ。これは安全な保留だが、事前に登録したunsupported理由へ一致しないので**FAILを維持**する。理由分類や閾値を後から変更して26/26としない。

不足画素を一つの連結領域・直線候補として扱う現行差分表現では、この曲線を修正候補へ渡せない。単純な接続anchor変更より前の表現段階が障害になっている。粗い参照簡略化、既描画の原形ずれ、Raster samplingを原因候補として切り分ける必要がある。今回の数値だけで単独原因を断定しない。

次の最小課題は**許可referenceの順序付き曲線仮説と、実Canvasの到達位置・局所方向を対応付けること**。曲線を描ける有意味なopen-loop comparatorを固定し、observed anchor/tangent介入を別に比較する。分岐・複数線・不連続欠落を単一経路へ無理に結合しない。既存repair_segment契約やscorerを黙って曲線対応へ変更しない。

## 費用と制約

主要16条件のうち8条件で候補の合計Motorが基準器より1増、残り8は同じ。境界近傍では1条件で1増。全18補筆条件のstrokeは両方式2。速度・費用削減は主張しない。曲線接線、線幅、過描画、別Body、未知作品、学習済みSkill、Corpus #82の受入れは未検証。

Google Driveの既存Image/Monochrome素材から一点をエンジニアリング参考として確認。現行抽出器の「crop境界に線が接するなら拒否」という条件により、実輪郭の局所切り出しが難しい。64/96/128px・16px gridの限定探索では条件を満たす曲線cropが0件だった。これは当該有限探索の結果で、全作品に適用可能ROIがない証明ではない。モデルへの原画入力や実作品作画は今回実行していない。原画bytes・候補crop・Drive個人識別情報はGitに保存していない。

## 再現と証拠

実行前にconfiguration.jsonを固定し、各結果をresults.jsonlへ追記。集計はreport.jsonへ保存した。再現コマンドは[runbook](e1_join_development_matrix_v0.md)。

- configuration hash：`sha256:88e2cd83c870bbf02cff76d84f5586f44c72bb615bd8522c967cebb3a6593bfe`
- report bytes SHA-256：`469b1b31964c80609e82d7910bc9a2a86c71e733a97b39ac213b63cdeb8102b3`

raw画像・Episode・score・private checkpointはignored runsのみ。Gitにはこの集計と再現コードを保存。比較図は真正P1 PNGの同じ座標範囲をnearest-neighbor拡大した事後表示で、policyに逆流させない。人による継ぎ目の受入れはまだfalse。新しいWSL2実測、署名付きCI、merge、有料Actions、Model学習は行っていない。

関連： [Model #85](https://github.com/ryonakayama234/ImageProgram/issues/85)、[Model #86](https://github.com/ryonakayama234/ImageProgram/pull/86)、[曲線提案 #89](https://github.com/ryonakayama234/ImageProgram/issues/89)、[Arena #28](https://github.com/ryonakayama234/ImageProgram-Arena/issues/28)。
