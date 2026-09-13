## xgboost_combined (teammate baseline, scored with the shared harness)

scored 4396 / 6556 windows; 4396 predictions, 0 unknown ids
missing predictions per split: train 1716, val 444

| split | H | n | pos | AUROC | AP | R@10%FAR | R@5%FAR | hard P / R / F1 | subsystem macro-F1 | subsystem acc |
|---|---|---|---|---|---|---|---|---|---|---|
| test_a | 1 | 567 | 170 | 0.824 | 0.739 | 0.606 | 0.524 | 0.805 / 0.629 / 0.706 | 0.205 | 0.547 |
| test_a | 3 | 581 | 192 | 0.780 | 0.689 | 0.495 | 0.365 | 0.707 / 0.578 / 0.636 | 0.146 | 0.510 |
| test_a | 6 | 593 | 215 | 0.735 | 0.648 | 0.433 | 0.223 | 0.707 / 0.516 / 0.597 | 0.134 | 0.447 |
| test_a | all | 1741 | 577 | 0.779 | 0.688 | 0.523 | 0.354 | 0.736 / 0.570 / 0.643 | 0.161 | 0.497 |
| test_b | 1 | 878 | 279 | 0.614 | 0.492 | 0.283 | 0.215 | 0.848 / 0.140 / 0.240 | 0.081 | 0.111 |
| test_b | 3 | 886 | 294 | 0.617 | 0.448 | 0.218 | 0.122 | 0.829 / 0.099 / 0.176 | 0.062 | 0.075 |
| test_b | 6 | 891 | 304 | 0.613 | 0.443 | 0.178 | 0.105 | 0.771 / 0.089 / 0.159 | 0.071 | 0.072 |
| test_b | all | 2655 | 877 | 0.614 | 0.458 | 0.223 | 0.148 | 0.819 / 0.108 / 0.191 | 0.073 | 0.086 |

Per class, horizons pooled (recall at 10 % FAR · subsystem accuracy · n):

| split | brake_hydraulics | converter_grid | gearbox_lubrication | generator_cooling | pitch_system | structural_overspeed | yaw_cable |
|---|---|---|---|---|---|---|---|
| test_a | 0.111 · 0.000 · 9 | 0.096 · 0.058 · 52 | 0.487 · 0.026 · 39 | 0.055 · 0.000 · 91 | 0.080 · 0.000 · 25 | 0.816 · 0.878 · 320 | 0.220 · 0.049 · 41 |
| test_b | 0.067 · 0.000 · 15 | 0.122 · 0.000 · 426 | – | 0.157 · 0.014 · 70 | 0.000 · 0.000 · 11 | 0.439 · 0.273 · 271 | 0.155 · 0.000 · 84 |
