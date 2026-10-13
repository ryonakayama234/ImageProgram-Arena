# 実Canvasの線のまとまりを測る v0

関連：ImageProgram #89。profile `thin-smooth-open-contour-v0` の独立事後診断。
位置一致と線損傷は分離し、品質違反を高F1で救済しない。

`evaluate_line_integrity_v0`は真正な実行／Replayをbenchmarkが確認したL8実Canvas、
Arena-private analytic source path、editable mask、固定thresholds、profileから診断を返す。
このモジュールはImageProgramをimportせず、Model抽出経路を正解にしない。
Program、stroke数、candidate ID、良悪タグを品質測定へ入力しない。

## 測定

- sourceを独立に弧長1px間隔でsample。端から8pxは除き、前後3pxの方向で法線を定める。
- 各点の法線±6 World pxを0.25px間隔でbilinear L8 sampling。
- 着墨を(255-L8)/255に変換し、積分幅・着墨重心の符号付きoffset・ink>=.2のband数を計算。
- 重心offsetの±4px二階差分を測り、意図した曲率そのものではなく、局所的な余分の曲がりを検出。
- 可視ink<250の8近傍成分数と保護外inkを別に測る。太らせて接続するだけでは合格しない。
- blank・不完全なsection・複数成分・幅超過・複数band・過大な二階差分は別reason。
- 短線・閉経路・近接する非局所区間により断面が混ざるsourceはunknown。

初期値：積分幅1.65pxを超えるsectionが2%超、複数bandが2%超、二階差分1.4px超を品質違反。
観測section97%以上、8近傍1成分、保護外ink0も必要。
値は今回の1px pen・解像度・限定smooth profile用。輪郭一般の美しさや接線の厳密C1条件ではない。
形状適合は既存scorerのF1_2px>=.95と別に判定。実測構造を全scoreの和へ潰さない。

## 比較と情報境界

20開発組・固定後10新組。同じ許可referenceから作った同じ公開candidate集合について、
Modelの位置だけの比較器と品質条件付き候補器のdecisionを全arm実行前に保存。
その後candidateごとのWorld・canonical P1・Replay・独立品質／F1を収集する。
private analytic geometry、損傷種別、正解選択ID、候補実結果はModel入力に含めない。
source-family内の反復・3arm数を独立作品数にしない。
良い案だけでなく損傷案・no-op・hold・失敗も保存。

## 限界

適用域は緩い一本の開曲線・固定pen。端の8px以内の折れ／太りをこの断面診断は評価しない。
損傷が±6pxの測定tube外に出る場合や、curve相互の近接・brush・意図した線幅変化には別診断が必要。
F1と連結診断も併記するが、これらが未測定の視覚品質を保証するわけではない。
人の受入れは別欄。自動分類の成功を美的品質・学習済みSkillの獲得と呼ばない。
今回のWorldは同位置再描画で濃くならないため、にじみ／墨溜まりの実測を主張しない。

実行：

```bash
# clean固定Arena checkout、固定ModelをimportするPython。新規の出力先を使う。
../ImageProgram-LineIntegrity/.venv/bin/python -m adapters.imageprogram_reference.line_integrity_benchmark_v0 \
  --split development --out runs/line-integrity-development
../ImageProgram-LineIntegrity/.venv/bin/python -m adapters.imageprogram_reference.line_integrity_benchmark_v0 \
  --split reserved --development-report runs/line-integrity-development/report.json \
  --out runs/line-integrity-reserved
```

`--pilot`はdirty開発を許すが、reservedとは同時指定できず、正式合格証拠ではない。
