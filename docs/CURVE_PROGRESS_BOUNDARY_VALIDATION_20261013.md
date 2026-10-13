# 曲線の到達位置と形状差を分ける v1：実行記録（2026-10-13 JST）

**合格条件未達。** 固定後の新しい4曲線family・48条件のうち47は正しく測れたが、
1条件をmeasuredと返しながら独立source対応位置誤差が2.455519pxとなり、上限2pxを超えた。
測定率90%以上を満たしても、誤確定0という条件を満たさない。Model昇格・曲線補筆への接続は行わない。

関連：ImageProgram #89、親Draft #90、Arena親Draft #31。
原画・checkpoint・個別privateラベル・raw EpisodeはGitへ追加していない。
下記は人工の1px pen曲線についてのengineering実験で、実作品・学習・技能転移の結果ではない。

## 固定したコードと設定

| 対象 | 実験開始時のGit commit |
|---|---|
| ImageProgram | `5ab87eaf006d055ad237d28839b1c8005c22ddbd` |
| ImageProgram-Arena | `df5bf6f29b1b9acdb9eef6b4df41875d068949e0` |

GitHub APIで作成したtreeとローカルtreeの一致を検査し、GitHub commit objectも同一SHAでローカルへ構成してから正式比較を実行した。
後続の検証報告追加は文書のみ。再実行はbranch先端ではなく上記code commitを使う。

- 形状残差許容4.5 World px、終端の参照方向への軸方向差1.5px。
- 方向比較窓6pxと12px、両窓の方向差35度以内、唯一かつ連続の候補区間幅4px以下。
- 参照／観測抽出・frontier回復・順序対応は固定v0の処理を再利用。
- **旧v0は許容2pxのまま固定し、coverageをそのままv1出力へ保持。**
- Model入力は許可reference、placement、真正Broker frame、版付き設定のみ。
  source Program、制作fraction、privateラベル、筆先の隠れ状態は渡さない。
- 位置の評価は対応参照点をArenaのprivate analytic sourceへ投影して弧長誤差を計算。
  Model推定経路を正解には使わない。raw推定弧長差とは別に報告する。

軸方向一致は追加の幾何仮定であり、潜在的な制作意図を画像から復元したとは呼ばない。
同じ公開画像に複数の解釈が成立する場合の一般的な識別保証もない。

## 条件と結果

法線方向のずれは始点を固定し、15 World pxまでに1/2/3pxへ増加する一軸介入。
粗い折れ線条件は101点のsourceを16点間隔で間引き、prefix終点を保持。
Body・配置・pen・予算を固定し、同じ真正Canvasに両observerを適用する。

| 群 | 全条件の期待判定・精度を満たした数 | 支持例 | v0で正しく測定 | v1で正しく測定 | v1誤確定 | 最大対応位置誤差 |
|---|---:|---:|---:|---:|---:|---:|
| 既知の回帰 | 66/66 | 56 | 56/56 | 56/56 | 0 | 1.413px |
| 開発 | 31/31 | 25 | 9/25 | 25/25 | 0 | 1.193px |
| 固定後の4曲線family | 47/48 | 48 | 6/48 | 47/48 | 1 | 2.456px |

開発の支持25は2 family×3到達状態×4介入の24と既知near-self probeの1。
その他6は横ずれ4/6px診断2と穴・遠い終端だけ・枝・閉参照の4。
回帰66は前段で既に観測した54+12であり、新しいheld-outとは呼ばない。
新しい48は4 family×3到達状態×4介入。48独立作品ではなく4つの合成幾何family内の反復。
小標本の限定実験で、統計的な一般化・実作品性能を主張しない。

全145条件のcanonical P1実行・Replay、測定frameとcanonical final raster一致、
測定中Motor0、測定前後World hash不変、保護外着墨0を確認。旧coverage判定の変更は0。
全条件で再観測からの測定を行い、正解をModelに直接渡す経路はない。

## 開発pilotの扱い

形状許容4.0pxの初回pilotは開発31条件中27が期待判定、支持25中21を正しく測定、誤確定0。
3px横ずれ4条件では残差4.171～4.277pxが許容を超えunknownだった。
開発後に形状許容だけを4.5pxへ調整。位置評価の2px上限・旧v0の判定・否定例を変更していない。
同一source treeでの追加開発実行も保持した。GitHub code identity固定後に正式開発31条件を再実行し、そのreportでreserved実行の条件を検査した。
reservedを見た後のコード・閾値調整や同じ群での再合格主張はしていない。

## 未使用群で得た反例

`s_new-0.8-normal-2.0`：

- v0：unknown、最小形状残差3.075284px。
- v1：measured、候補区間172.541847～174.536551px、推定弧長173.539199px。
- 対応点を独立sourceへ投影すると169.923710px。管理側の準備位置172.379230pxとの差2.455519px。
- raw推定弧長差は1.159969px。これが2px以内でも独立対応位置誤差はFAILであり、同じ指標ではない。
- 方向差10.22/3.28度、軸方向残差0.229px。狭い候補区間でも正確さを保証しなかった。

事後の原因診断（private管理情報を用いた診断で、Model入力ではない）：
細線化された終端は(140.5,184.5)、frontier回復後は(142.5,187.5)。
最後の合法接触命令位置は(144.988043,188.671394) World px。
この位置に最も近い可視インクpixel centre(144.5,188.5)は細線化終端から5.656854px離れ、
固定4pxのfrontier回復窓の外だった。中心線短縮を回復し切れないことが誤推定の原因の一つ。
命令位置を観測位置の正解へすり替えず、実際の可視インクも確認した。

**次の一能力：実インク端の回復が不十分なときに検出してunknownへ保留する。**
この反例は今後developmentへ移す。修正版を検証するなら、新しい独立familyを再度固定する。
今回の48例を未使用のまま再利用しない。

## 旧coarse曲線の事後診断

元の合法Motorを新しい固定Modelで再実行し、元のCanvasと画素一致、canonical Replayを確認。
v0はunknownのまま、v1はmeasuredを返し、候補区間95.925831～97.924286px、推定96.925058px。
形状残差3.701556px、coverageはunverifiedのまま。
この旧fixtureには独立analytic sourceの到達位置ラベルが保存されていないため、
精度合否は `INCONCLUSIVE_NO_PRIVATE_SOURCE_LABEL`。測れたという出力を精度PASSへ格上げしない。
この診断1例は上記145条件の分母に含めない。

## 回帰・環境

- Model全unittest：266/266 PASS、Ruff全体PASS。
  266には新規6観測testを含む。全体checkはGitHubと同一source treeで実行、commit objectのローカル構成はその実行中に行ったがsource変更はない。
- Arena全unittest：132/132 PASS、skip0。既存cross-repo契約のため元#81のbaseline sourceをPYTHONPATHに指定した同じlocked環境で実行。
  新しいbenchmark本体と単体3testは新Modelを使う。Arena全体を新Modelで検証したという意味ではない。
- Arena新規PythonのE4/E7/E9/F/I PASS。親からの全体lint問題は残り、全体Ruff PASSとはしない。
- Python3.12.14、NumPy2.5.3、Pillow12.3.0、Pydantic2.13.5、Ruff0.16.7。
- 前回lockに対応したvenvを複製し、新checkoutへeditable import先を更新して使用。新規uv sync成功や新しいWSL2実測とはしない。
- Observer v1はv0を呼んだ後に追加対応計算を行う。計算費用削減は主張しない。Motorとwall/sim費用は区別して保存。

## 再実行

```bash
# 固定Arena checkout内、固定ModelのPythonを使う。未存在の出力先を指定。
../ImageProgram-ProgressV1/.venv/bin/python -m adapters.imageprogram_reference.curve_progress_boundary_v1   --split development --out runs/boundary-development
../ImageProgram-ProgressV1/.venv/bin/python -m adapters.imageprogram_reference.curve_progress_boundary_v1   --split regression --out runs/boundary-regression
../ImageProgram-ProgressV1/.venv/bin/python -m adapters.imageprogram_reference.curve_progress_boundary_v1   --split reserved --development-report runs/boundary-development/report.json   --out runs/boundary-reserved
```

reservedはclean source、同一SHA/fingerprint、全開発ID、成功率・誤確定・Replay条件を検査してから出力を作る。
保存reportのhashはbyte破損確認で、署名された第三者実行証明ではない。

## 記録digest

- development report SHA256: `134d21182529751489ddfccd49243e92f81e72b2be417747121ce23b50f6311d`
- regression report SHA256: `bd01fd4dfb094cb4355f3c0079d8af9ad18d3895043ad80d559049d0366b5425`
- reserved report SHA256: `fac7a655821681ec3c424affbf6d979f7f454895dfc32fbaa6308ce198eb6a39`
- curve_progress_v1.py SHA256: `144f47751db60ecf3556849c34cfaa799a2a8127e618f3462c8b95bc206d4718`
- curve_progress_boundary_v1.py SHA256: `601d8ef99be2d80ce859aac983a0c2a72974d94623b437fb519c9e03fcf0d910`
