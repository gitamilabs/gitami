# GitAmi Benchmark Evaluation Report

**Run Timestamp**: `2026-10-20 08:35:58`  
**Datasets Evaluated**: ``  
**Total Cases**: `50`  
**Mean Latency**: `1.9s per case`  

## 1. Overall Performance Metrics

| Metric | Value | Description |
| :--- | :--- | :--- |
| **Precision** | **26.7%** | True Positives / Total Predictions (16/60) |
| **Recall** | **9.2%** | True Positives / Ground Truth Issues (16/173) |
| **F1 Score** | **0.1373** | Harmonic mean of Precision and Recall |
| **True Positives (TP)** | `16` | Successfully detected ground-truth defects |
| **False Positives (FP)** | `44` | Spurious or hallucinated issues |
| **False Negatives (FN)** | `157` | Missed ground-truth defects |

## 2. Category Breakdown

| Category | Detected | Total Ground Truth | Detection Rate |
| :--- | :--- | :--- | :--- |
| **Bug** | 13 | 128 | 10.2% |
| **Convention** | 0 | 28 | 0.0% |
| **Performance** | 2 | 6 | 33.3% |
| **Security** | 1 | 11 | 9.1% |

## 3. Severity Breakdown

| Severity | Detection Rate |
| :--- | :--- |
| **Error** | 9.1% |
| **Info** | 8.7% |
| **Warning** | 9.8% |

## 4. Per-Testcase Summary

| Case ID | Dataset | Precision | Recall | F1 Score | TP/FP/FN | Latency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `martian_cal_dot_com_1` | martian | 0% | 0% | 0.00 | 0/2/2 | 2.90s |
| `martian_cal_dot_com_2` | martian | 25% | 40% | 0.31 | 2/6/3 | 2.28s |
| `martian_cal_dot_com_3` | martian | 14% | 17% | 0.15 | 1/6/5 | 3.51s |
| `martian_cal_dot_com_4` | martian | 50% | 50% | 0.50 | 1/1/1 | 16.76s |
| `martian_cal_dot_com_5` | martian | 50% | 67% | 0.57 | 2/2/1 | 2.07s |
| `martian_cal_dot_com_6` | martian | 0% | 0% | 0.00 | 0/3/2 | 3.45s |
| `martian_cal_dot_com_7` | martian | 0% | 0% | 0.00 | 0/4/9 | 2.52s |
| `martian_cal_dot_com_8` | martian | 0% | 0% | 0.00 | 0/0/2 | 0.70s |
| `martian_cal_dot_com_9` | martian | 33% | 33% | 0.33 | 2/4/4 | 10.28s |
| `martian_cal_dot_com_10` | martian | 0% | 0% | 0.00 | 0/4/4 | 2.81s |
| `martian_discourse_1` | martian | 0% | 0% | 0.00 | 0/0/4 | 0.81s |
| `martian_discourse_2` | martian | 0% | 0% | 0.00 | 0/0/2 | 1.16s |
| `martian_discourse_3` | martian | 0% | 0% | 0.00 | 0/0/3 | 0.89s |
| `martian_discourse_4` | martian | 0% | 0% | 0.00 | 0/3/8 | 3.07s |
| `martian_discourse_5` | martian | 0% | 0% | 0.00 | 0/0/3 | 0.70s |
| `martian_discourse_6` | martian | 0% | 0% | 0.00 | 0/0/1 | 0.79s |
| `martian_discourse_7` | martian | 0% | 0% | 0.00 | 0/0/5 | 1.20s |
| `martian_discourse_8` | martian | 100% | 17% | 0.29 | 1/0/5 | 1.11s |
| `martian_discourse_9` | martian | 0% | 0% | 0.00 | 0/0/2 | 0.79s |
| `martian_discourse_10` | martian | 0% | 0% | 0.00 | 0/0/7 | 1.27s |
| `martian_grafana_1` | martian | 0% | 0% | 0.00 | 0/0/5 | 0.91s |
| `martian_grafana_2` | martian | 0% | 0% | 0.00 | 0/0/3 | 0.81s |
| `martian_grafana_3` | martian | 0% | 0% | 0.00 | 0/0/3 | 0.93s |
| `martian_grafana_4` | martian | 0% | 0% | 0.00 | 0/2/1 | 1.70s |
| `martian_grafana_5` | martian | 0% | 0% | 0.00 | 0/1/2 | 1.10s |
| `martian_grafana_6` | martian | 0% | 0% | 0.00 | 0/0/3 | 0.78s |
| `martian_grafana_7` | martian | 100% | 100% | 1.00 | 2/0/0 | 1.62s |
| `martian_grafana_8` | martian | 100% | 50% | 0.67 | 1/0/1 | 0.78s |
| `martian_grafana_9` | martian | 0% | 0% | 0.00 | 0/0/2 | 0.78s |
| `martian_grafana_10` | martian | 0% | 0% | 0.00 | 0/0/2 | 0.79s |
| `martian_keycloak_1` | martian | 0% | 0% | 0.00 | 0/0/2 | 1.01s |
| `martian_keycloak_2` | martian | 0% | 0% | 0.00 | 0/0/2 | 0.79s |
| `martian_keycloak_3` | martian | 0% | 0% | 0.00 | 0/0/4 | 1.08s |
| `martian_keycloak_4` | martian | 0% | 0% | 0.00 | 0/0/2 | 1.01s |
| `martian_keycloak_5` | martian | 50% | 40% | 0.44 | 2/2/3 | 2.40s |
| `martian_keycloak_6` | martian | 50% | 50% | 0.50 | 1/1/1 | 2.32s |
| `martian_keycloak_7` | martian | 0% | 0% | 0.00 | 0/1/5 | 1.72s |
| `martian_keycloak_8` | martian | 0% | 0% | 0.00 | 0/0/4 | 1.29s |
| `martian_keycloak_9` | martian | 0% | 0% | 0.00 | 0/0/2 | 0.95s |
| `martian_keycloak_10` | martian | 0% | 0% | 0.00 | 0/0/2 | 0.74s |
| `martian_sentry_1` | martian | 0% | 0% | 0.00 | 0/0/4 | 0.70s |
| `martian_sentry_2` | martian | 0% | 0% | 0.00 | 0/0/4 | 0.96s |
| `martian_sentry_3` | martian | 0% | 0% | 0.00 | 0/0/3 | 0.90s |
| `martian_sentry_4` | martian | 0% | 0% | 0.00 | 0/1/3 | 0.82s |
| `martian_sentry_5` | martian | 50% | 17% | 0.25 | 1/1/5 | 4.95s |
| `martian_sentry_6` | martian | 0% | 0% | 0.00 | 0/0/5 | 0.78s |
| `martian_sentry_7` | martian | 0% | 0% | 0.00 | 0/0/4 | 0.94s |
| `martian_sentry_8` | martian | 0% | 0% | 0.00 | 0/0/2 | 0.80s |
| `martian_sentry_9` | martian | 0% | 0% | 0.00 | 0/0/2 | 0.93s |
| `martian_sentry_10` | martian | 0% | 0% | 0.00 | 0/0/3 | 0.82s |
