# H-LineIntegrity v0 実行記録 — 2026-10-13

## 結論と検証した能力

**限定engineering gate PASS。** 白紙から、固定された公開描画候補のうち、
意図した形と一本の線のまとまりを保つ候補を選ぶ。位置だけの最小比較器より、
今回の折れ・揺れ・太り・余分な並行線・欠損を持つ候補の採用を減らした。
良い案の採用90%以上、明確な損傷案の誤採用0を事前条件とした。

| 比較 | 開発4合成family・20組 | 未使用5合成family・10組 |
|---|---:|---:|
| 位置だけで選択した実描画の形・品質PASS | 4/20 | 2/10 |
| 品質条件を含めて選択した実描画の形・品質PASS | 20/20 | 10/10 |
| 品質付き選択による損傷案の採用 | 0/20 | 0/10 |
| 全比較gate | 20/20 | 10/10 |
| 保留・失敗・missingを除いた比較 | 行わない | 行わない |

対象は `thin-smooth-open-contour-v0`、256px World、1px pen、
ゆるい一本の開曲線。今回の候補選択器はルールによる固定実装。
自由なProgram生成、制作途中からの適応的継続／補筆、実作品への適応、
経験学習、技能発見、一般的美的判断、人の受入れは未検証。
報告JSONの `learned_skill=false`、`human_accepted=false`、
`held_out_generalization=false` はその境界を示す。
未使用合成familyでの小規模検査を一般的転移性能と呼ばない。

## 固定コード・独立性

- Modelコード：`1c3841e5350ef905575db4f0ee939c9fcb4e592b`。
  親はModel Draft #90の `56caed13aeed4b6b70c05b1373b8188a143517fe`。
- Arenaコード：`fa19c20919f0a9ef54145c8632b9fbe91163655c`。
  親はArena Draft #31の `47b32d412bd3e8d8e506db615efec2380e013991`。
- この検証文書等の後続commitは報告のみ。正式runは上記のclean checkoutで実行。
- #91／Arena #32の到達位置v1は別研究。以前の誤確定を含むFAILは保持し、
  この品質研究の依存や修正済み結果に読み替えない。
- 開発と未使用群は同じModel／Arena SHA・source fingerprintsで実行。
  未使用群は全20開発組PASSと一致した固定コードを確認してから開いた。
  未使用結果を見てcode、閾値、候補や分母を調整していない。

Modelは許可参照と真正Broker白紙frame、profile、公開candidate幾何だけを受け取る。
全候補は許可参照から抽出・平滑化した仮説から作り、private analytic sourceから作らない。
candidate IDはopaqueで良悪ラベルを供給しない。
位置だけ／品質付きの両decisionは同じ候補集合に対し、全候補実行の**前**に保存。
予測時のMotorは0。World、fork、private source、候補実結果はpolicy入力にしない。

Arenaの品質評価器はImageProgramをimportせず、実Canvas L8と独立analytic sourceで測定。
Program、stroke数、candidate IDや良悪ラベルを品質測定へ入れない。
凍結した2px許容F1は独立の形状適合軸。線品質違反をF1満点で相殺しない。
比較器は今回定義した位置のみの最小選択規則であり、現行P2全体の性能baselineではない。

## 実描画・形状・stroke対照

各組は良い案・損傷案・no-opの3候補。開発60＋未使用30＝90独立候補実行。
合法TracePolylineのprotection guardとMotor、canonical P1実行、Replayを通した。
全90候補でsource Replay一致、実測frameとcanonical final PNGの一致、保護外着墨0。
全30組で候補実行前のdecision保存と、測定中Motor0を確認した。
no-opは全30組で完成PASSにならない。

全30良例の独立F1_2pxは1.0。
良い案と損傷案のF1絶対差は開発0〜0.0092879257、未使用0〜0.0055555556。
そのため今回の線損傷は従来の位置指標だけで十分区別できない。
例えばarcのまとまった重ね2stroke、局所折れ1stroke、局所太り3strokeは、
いずれもF1_2px=1.0で、実品質はPASS／REJECT／REJECT。
比較PNGは実Episodeのfinal.pngと、その最近傍拡大から作成した。

開発4familyそれぞれで、同じ良い線の1stroke／自然につながる分割2stroke／
同位置重ね2strokeを比較。4/4 familyで実PNGと品質判定・全品質指標が完全一致。
運動command、stroke、時間等の費用は別記録。
少ないstroke数を普遍的な線品質とする規則は入れていない。
現Worldでは同位置の再描画で無限に濃くならないため、にじみ・墨溜まりの実測は主張しない。

## 測定の意味と制限

Arenaはsource弧長1pxの法線断面で実inkの積分幅、重心offset、
複数band、欠損を別測定し、重心offsetの局所二階差分で余分な折れを診断。
8近傍連結と保護外着墨も別に測る。
Modelは公開参照仮説とnominal penの掃引区間から予測する別実装であり、
予測PASSを実測PASSの代用にしない。

固定実測閾値：幅1.65px超のsection比率2%以下、複数band比率2%以下、
重心offset二階差分最大1.4px以下、観測section97%以上、連結1成分、保護外ink0。
F1_2px>=.95も必要。滑らかさは今回のprofileの意図。
角、ラフ、線幅の意図的変化、ハッチングを普遍的に悪いとしない。

断面は法線±6px、source端8pxを除く。端付近の折れ・太りやtube外の損傷は保証しない。
短線、閉線、接近する非局所区間はunknownの適用条件。
AA、解像度、曲率、幅が変われば今回の数値をそのまま一般化しない。
候補familyと損傷は人工的に構成され、30組は30独立作品ではない。
未使用5familyでの10組は小さなengineering gateで、統計的優位や実作品一般への転移を示さない。

Google Driveの「1-pen.jpg」はエンジニアリング参考として人間側で閲覧した。
輪郭と意図的な並行陰影が同じ画像にあるためprofileを限定した。
この原画をModel入力・benchmark・正解や実作品PASS証拠には使っていない。
Wolframでは断面方向誤差による幾何幅係数1/cos(theta)を確認した
（0,20,45,60度で1,1.064,1.414,2）。この計算はraster評価の合格証拠ではない。

## 開発中の失敗と修正

1. 初回pilotは既存F1のfieldを `f1` と誤指定し停止。正本 `f1_2px` を使用した。
2. 次のpilotはraster参照の階段を折れと誤認して良例までhold。途中終了し合格に数えない。
   profileに明示した滑らかな参照仮説を7点平均で作り、独立実測閾値は緩めなかった。
3. 20組pilot PASS後の全回帰で、同じ直線を複数strokeへ分けた案が誤棄却された。
   遠隔ink判定が参照「頂点」へ距離を測っていたため、「線分」への射影距離へ修正。
   修正中の変数shadow例外も解消し、最終固定SHAで全回帰と開発20組を再実行。
   この旧Model `b5b0d7337e5f7287f5022e8f1187fbb97030eb8e` のrunを
   最終検証証拠へ混ぜていない。

これらはすべて未使用群の実行前。失敗／途中終了runを成功率の分母から都合よく除外する
操作ではなく、開発履歴と最終固定実装の検証を分離して保存した。

## 回帰・環境

| 検査 | 実測 |
|---|---|
| 固定Model `scripts/check.py` | 265/265 PASS、162.288s |
| Model全Ruff | PASS |
| Arena全unit suite | 137/137 PASS、44.594s、skip0 |
| Arena新規4Pythonファイル指定lint E4,E7,E9,F,I | PASS |
| Arena全repo Ruff | PASSとは主張しない（親の既存問題） |
| 同見た目の異stroke対照 | 4/4 family 完全一致 |

Arena既存suiteは旧#81 Model固定baseline
`6d8e6399a2b0a44d08054a08b71b4a68d4d9e374` をPYTHONPATHでimportするpaired環境。
新規実描画benchmarkは最終新Model `1c3841...` をimport。
両検査を同じModelで全Arenaを回した検証と混同しない。

Linux CPU、Python3.12.14、NumPy2.5.3、Pillow12.3.0、Pydantic2.13.5、Ruff0.16.7。
以前のlock対応venvをコピーしてeditable pathを今回checkoutへ設定。
今回の新規uv sync成功、ユーザー側WSL2実測、有料Actions、GPU学習は主張しない。
canonical schema／World／Registry／P1／P2の意味は変更しない。
コードはexperimentsとArena reference adapterの限定研究として置く。

## 保存記録・経験への接続

各case directoryに、参照・公開decision・全candidateのcanonical Episode／final PNG、
独立private_evaluation.json、実costを関連付けた。
report.jsonのresultsはcase ID、family、profile、実装／設定版、採否と理由、
prediction、独立実測、good／bad／no-op Episodeへの対応をまとめた実験索引。
成功だけでなく損傷・no-op・開発失敗を保持。既存E1 corpusへの取込や学習は未接続。
raw原画、signed URL、private geometry、Episode群、大きなrun JSONはGitに入れない。

| 記録 | SHA256 |
|---|---|
| development report.json | 97622e67e2f6f1594f3c4a4db9b224db9ba54cf3267b63ef7b5d30512060e6dc |
| reserved report.json | b8911d728ce0060ae0365760bb53c855a84b23b4252649eb8f0a5633c30fa107 |
| development configuration | f22fd2e7a48942eea7a6c67d8b7c5e7aa7b8537b0404d6936f38fb7ec20f5bb0 |
| reserved configuration | 3f84b6ece05b7c91d26fa9a9f160d1efd38baef532b86753a44fcdd39604b9bf |
| Model choice source | 30d19ea8ffd91f4bcdcf7f98d5ad324eacb026b20b707cc3e0154ca9be19fef6 |
| Arena evaluator source | 105dda519b4e503257b7ecac920b38f2b94a8b31906ce54d11102a1154f829c2 |
| Arena benchmark source | 6afb07350587e6e9ee28a8b078820d1d5186cc9096b0e3dd5cc04b3cf3fa50d9 |

raw runはignored `runs/line-integrity-{development,reserved}-final-20261013`。
wall time等は再実行で変わるため、raw report byte digestの同一性を再現要件にはしない。

## 再現手順

固定SHAのclean checkoutを並べ、Modelのlock対応Python環境を用意する。
ドキュメント報告commitではなく上記**コードSHA**にcheckoutする。
Arena directoryから新規出力先で実行：

```bash
../ImageProgram-LineIntegrity/.venv/bin/python -m adapters.imageprogram_reference.line_integrity_benchmark_v0 \
  --split development --out runs/line-integrity-development
../ImageProgram-LineIntegrity/.venv/bin/python -m adapters.imageprogram_reference.line_integrity_benchmark_v0 \
  --split reserved --development-report runs/line-integrity-development/report.json \
  --out runs/line-integrity-reserved
```

`--pilot`はdirty開発だけに許可しreservedとは併用不可。
未使用gateで失敗した場合、結果を残して新しい版・新しい未使用群で再検証する。

## 次の単一能力候補

**部分的に描かれた一本の線から、まとまりを壊さない継続案を選べるか。**
今回の形／品質Goalと独立実測を維持し、白紙条件だけを実Canvasの部分線へ広げる。
まず同じ固定候補方式で、自然な継続・折れ・重なり太り・余分な並行線・停止を比較する。
候補生成の学習や技能抽象化まで同時に増やさない。

