# Curve Progress v0：独立した実描画観測の比較

親：Arena #30。Modelは#86上のcurve_progress_v0 prototypeを使用する。補筆・学習・Model昇格は行わない。

- development：Bezier四族の白紙／20／40／60／80／100%、U字五状態、水平／垂直二位置の16途中＋4完成、穴・終点patch・分岐・closedの4負例、near-selfの順序比較1。計54状態。
- reserved：新しいcontrol geometry二族の白紙／25／45／65／85／100%。計12状態。調整に使わず、ModelとArenaのclean exact code/config、developmentの全行の成功とsource Replayを検証してから開く。二族の反復であり、広い統計的一般化は主張しない。
- 成立観測はすべて合法Trace／continuous guard／P1 World由来。Observerには許可reference・placement・Broker観測しか渡さない。private source geometryとfractionは生成・事後評価だけ。Modelが算出したreference経路を正解ラベルに流用しない。
- source geometryへの投影による弧長誤差、raw inferred弧長誤差、nearest端点の誤差を別に記録する。pixel境界・AA・細線化による定義差を隠さない。
- measurementはMotorゼロ。World hash不変、真正frameとcanonical final一致、source Replay、保護外着墨ゼロを要求する。新モデル環境で新規Episodeを作り、旧モデルEpisodeを最新replayerで書換えない。

```bash
# cleanな別Model／Arena checkoutを使う
../ImageProgram-CurveProgress/.venv/bin/python -m adapters.imageprogram_reference.curve_progress_benchmark_v0 \
  --split development --out runs/progress-development

../ImageProgram-CurveProgress/.venv/bin/python -m adapters.imageprogram_reference.curve_progress_benchmark_v0 \
  --split reserved --development-report runs/progress-development/report.json \
  --out runs/progress-reserved
```

private_configuration.jsonを実行前に固定。measurement＋private評価はignored runsに保存し、Gitには集計・digest・再現コードだけを置く。実行結果に失敗があっても記録を削除せずreportを読む。人の受入れ、実作品、WSL2、learned Skill、registry promotionは別の状態として扱う。
