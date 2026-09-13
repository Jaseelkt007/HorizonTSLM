## xgboost_sensors_only (teammate baseline, scored with the shared harness)

scored 4396 / 6556 windows; 4396 predictions, 0 unknown ids
missing predictions per split: train 1716, val 444

| split | H | n | pos | AUROC | AP | R@10%FAR | R@5%FAR | hard P / R / F1 | subsystem macro-F1 | subsystem acc |
|---|---|---|---|---|---|---|---|---|---|---|
| test_a | 1 | 567 | 170 | 0.826 | 0.752 | 0.624 | 0.512 | 0.790 / 0.641 / 0.708 | 0.195 | 0.553 |
| test_a | 3 | 581 | 192 | 0.784 | 0.693 | 0.458 | 0.380 | 0.679 / 0.583 / 0.627 | 0.145 | 0.510 |
| test_a | 6 | 593 | 215 | 0.737 | 0.646 | 0.400 | 0.260 | 0.669 / 0.526 / 0.589 | 0.169 | 0.470 |
| test_a | all | 1741 | 577 | 0.780 | 0.693 | 0.508 | 0.354 | 0.708 / 0.579 / 0.637 | 0.170 | 0.508 |
| test_b | 1 | 878 | 279 | 0.622 | 0.485 | 0.276 | 0.190 | 0.885 / 0.165 / 0.278 | 0.089 | 0.125 |
| test_b | 3 | 886 | 294 | 0.597 | 0.420 | 0.163 | 0.075 | 0.763 / 0.099 / 0.175 | 0.059 | 0.071 |
| test_b | 6 | 891 | 304 | 0.575 | 0.432 | 0.174 | 0.118 | 0.735 / 0.082 / 0.148 | 0.072 | 0.072 |
| test_b | all | 2655 | 877 | 0.596 | 0.442 | 0.206 | 0.124 | 0.806 / 0.114 / 0.200 | 0.075 | 0.089 |

Per class, horizons pooled (recall at 10 % FAR · subsystem accuracy · n):

| split | brake_hydraulics | converter_grid | gearbox_lubrication | generator_cooling | pitch_system | structural_overspeed | yaw_cable |
|---|---|---|---|---|---|---|---|
| test_a | 0.222 · 0.000 · 9 | 0.058 · 0.058 · 52 | 0.513 · 0.000 · 39 | 0.055 · 0.011 · 91 | 0.080 · 0.000 · 25 | 0.794 · 0.891 · 320 | 0.171 · 0.098 · 41 |
| test_b | 0.067 · 0.000 · 15 | 0.110 · 0.000 · 426 | – | 0.171 · 0.014 · 70 | 0.091 · 0.000 · 11 | 0.399 · 0.284 · 271 | 0.143 · 0.000 · 84 |
