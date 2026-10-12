# 観測線端への接続補筆：実描画の開発比較 v0

関連：ImageProgram #85 / Draft #86、Arena #28 / Draft #29。

目的は、既知の一本の水平線で得た結果が、向き・位置・未完成率を変えた合法Motor実行でも成立するかを調べること。学習や独立testの成功を意味しない。

## 比較条件

- 基準器：ImageProgram `6d8e6399a2b0a44d08054a08b71b4a68d4d9e374`。
- 候補：ImageProgram `ceb9c55f647d81cb5a14fa6934f2d45b09741d0c`。
- 各producerはcleanな別checkoutと、`uv sync --locked --extra render`済みの自身のPython環境を使用する。採点とsource Replayもそのproducerの環境で実行する。
- 各課題でbaselineとendpoint_join_v0それぞれのnoop/off/onを実行。Body、pen、seed=17、public ROI、予算、初期Motorとpoststroke stateを一致させる。
- 開発16条件：水平／垂直 × ROI内位置40／85 × 未完成率0.35／0.45／0.55／0.65。原画サイズ128×160。配置と未完成率はpolicy入力の隠れ正解ではなく実験介入。
- 対照：完成4、境界近傍2、斜線／曲線の不適用2、分岐／ROI接触の入力拒否2。計26条件。入力拒否にはEpisodeが存在しないことも記録する。
- 以前の「2方向×手加工gap1〜4px×2位置」の単体テストとは別。実Worldのgapを無理に1〜4pxへ加工しない。

## 事前の開発判定

全成立Episodeは真正source Replay、独立採点、保護外追加着墨ゼロ、noop白紙、同じ初期prefixを要求する。実行対象は候補がexecuteし、strict raster接続が成立し、凍結F1が基準器以上。完成対照は`reference-already-covered`で補正Motorゼロ。不適用は明示unsupported Stop。入力拒否は対応する`ReferenceGeometryUnsupported`を両producerが返す。

連結が成立しても、接線方向・線幅・実作品の品質を合格とはしない。失敗・missingを削除しない。16条件は四つの元幾何familyの反復で、96 Episodeを96独立標本と数えない。開発結果を使った調整後には、別source-familyの未使用testが必要。

## 実行

ArenaとModelを別々に固定し、Arenaのclean checkoutで次を実行する。

```bash
../ImageProgram-Baseline/.venv/bin/python -m adapters.imageprogram_reference.run_e1_join_matrix_v0 \
  --baseline ../ImageProgram-Baseline \
  --candidate ../ImageProgram-E1-Join \
  --out runs/e1-join-development-v0
```

`configuration.json`は描画前に凍結する。results.jsonlに条件ごとに結果を書き、最後にreport.jsonを作る。原画、public crop、checkpoint、raw Episode、private採点はignored runsに保存する。GitHubにはコード、再現手順、集計とdigestのみを置く。

このrunnerは終了コードだけで能力PASSを表さない。`report.status`と全行の失敗理由を確認する。人の受入れ、WSL2実測、未知条件、学習、曲線対応は別gate。
