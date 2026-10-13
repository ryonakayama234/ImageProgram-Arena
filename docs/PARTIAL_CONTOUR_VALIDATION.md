# PartialContour v0 development review

Modelのfocus/context研究入力をsource-private Arena intakeから生成し、8区間を全数記録する。
旧孤立線抽出0/8、新観測3/8、smooth実行1/8、観測経路の診断実行3/8。
全4 Episodeは1stroke・Replay・公開focus+2px halo外着墨0。
長い服輪郭は曲線fitの固定残差条件を超過、短い髪断片は長さ条件未満。
短い縦断片の実行は意図輪郭を描けた証拠ではない。

reviewはImageProgramをimportせず、公開座標配置・halo・決定hash・Episode artifact hashと
raw Canvasを独立に確認する。選択したpathを評価の正解には使わない。
focus全体F1は他線/陰影も含む参考診断。独立target注釈がないため
target_selection/line_qualityはunknown、capability_pass/human_accepted/learned_skillはfalse。

新review tests3/3 PASS (3.172s)。新規3PythonのE4/E7/E9/F/I lint PASS。
Model277/277・全Ruff PASS。全Arena suite/全repo lint/未使用作品/WSL2は今回の検証外。
初回配置helper戻り値取り違えによるAttributeErrorを修正して全8区間を再実行した。

Model docs/PARTIAL_CONTOUR_V0.mdに全8結果・ADR・再現手順。
private original/global boxes/rights/familyは推論入力へ流さず、権利資料・原画・runsはGitに追加しない。
