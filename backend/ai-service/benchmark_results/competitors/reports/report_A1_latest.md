# GitAmi Benchmark Evaluation Report

**Run Timestamp**: `2026-10-19 21:30:28`  
**Datasets Evaluated**: ``  
**Total Cases**: `50`  
**Mean Latency**: `18.69s per case`  

## 1. Overall Performance Metrics

| Metric | Value | Description |
| :--- | :--- | :--- |
| **Precision** | **30.4%** | True Positives / Total Predictions (24/79) |
| **Recall** | **13.9%** | True Positives / Ground Truth Issues (24/173) |
| **F1 Score** | **0.1905** | Harmonic mean of Precision and Recall |
| **True Positives (TP)** | `24` | Successfully detected ground-truth defects |
| **False Positives (FP)** | `55` | Spurious or hallucinated issues |
| **False Negatives (FN)** | `149` | Missed ground-truth defects |

## 2. Category Breakdown

| Category | Detected | Total Ground Truth | Detection Rate |
| :--- | :--- | :--- | :--- |
| **Bug** | 20 | 128 | 15.6% |
| **Convention** | 3 | 28 | 10.7% |
| **Performance** | 0 | 6 | 0.0% |
| **Security** | 1 | 11 | 9.1% |

## 3. Severity Breakdown

| Severity | Detection Rate |
| :--- | :--- |
| **Error** | 18.2% |
| **Info** | 10.9% |
| **Warning** | 11.5% |

## 4. Per-Testcase Summary

| Case ID | Dataset | Precision | Recall | F1 Score | TP/FP/FN | Latency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `martian_cal_dot_com_1` | martian | 0% | 0% | 0.00 | 0/1/2 | 4.93s |
| `martian_cal_dot_com_2` | martian | 22% | 40% | 0.29 | 2/7/3 | 25.35s |
| `martian_cal_dot_com_3` | martian | 0% | 0% | 0.00 | 0/5/6 | 4.77s |
| `martian_cal_dot_com_4` | martian | 0% | 0% | 0.00 | 0/0/2 | 28.69s |
| `martian_cal_dot_com_5` | martian | 50% | 67% | 0.57 | 2/2/1 | 3.33s |
| `martian_cal_dot_com_6` | martian | 0% | 0% | 0.00 | 0/3/2 | 8.29s |
| `martian_cal_dot_com_7` | martian | 0% | 0% | 0.00 | 0/4/9 | 50.03s |
| `martian_cal_dot_com_8` | martian | 100% | 50% | 0.67 | 1/0/1 | 24.52s |
| `martian_cal_dot_com_9` | martian | 33% | 17% | 0.22 | 1/2/5 | 15.60s |
| `martian_cal_dot_com_10` | martian | 0% | 0% | 0.00 | 0/2/4 | 12.99s |
| `martian_discourse_1` | martian | 50% | 25% | 0.33 | 1/1/3 | 79.16s |
| `martian_discourse_2` | martian | 50% | 50% | 0.50 | 1/1/1 | 12.66s |
| `martian_discourse_3` | martian | 0% | 0% | 0.00 | 0/0/3 | 71.53s |
| `martian_discourse_4` | martian | 0% | 0% | 0.00 | 0/3/8 | 19.05s |
| `martian_discourse_5` | martian | 0% | 0% | 0.00 | 0/0/3 | 33.23s |
| `martian_discourse_6` | martian | 0% | 0% | 0.00 | 0/2/1 | 3.88s |
| `martian_discourse_7` | martian | 0% | 0% | 0.00 | 0/0/5 | 26.02s |
| `martian_discourse_8` | martian | 67% | 33% | 0.44 | 2/1/4 | 6.00s |
| `martian_discourse_9` | martian | 50% | 50% | 0.50 | 1/1/1 | 23.54s |
| `martian_discourse_10` | martian | 0% | 0% | 0.00 | 0/2/7 | 11.57s |
| `martian_grafana_1` | martian | 0% | 0% | 0.00 | 0/1/5 | 24.51s |
| `martian_grafana_2` | martian | 0% | 0% | 0.00 | 0/0/3 | 11.61s |
| `martian_grafana_3` | martian | 0% | 0% | 0.00 | 0/0/3 | 4.10s |
| `martian_grafana_4` | martian | 0% | 0% | 0.00 | 0/0/1 | 1.67s |
| `martian_grafana_5` | martian | 67% | 100% | 0.80 | 2/1/0 | 20.38s |
| `martian_grafana_6` | martian | 0% | 0% | 0.00 | 0/0/3 | 1.44s |
| `martian_grafana_7` | martian | 0% | 0% | 0.00 | 0/0/2 | 2.85s |
| `martian_grafana_8` | martian | 100% | 100% | 1.00 | 2/0/0 | 1.88s |
| `martian_grafana_9` | martian | 0% | 0% | 0.00 | 0/0/2 | 9.82s |
| `martian_grafana_10` | martian | 0% | 0% | 0.00 | 0/2/2 | 14.79s |
| `martian_keycloak_1` | martian | 0% | 0% | 0.00 | 0/1/2 | 14.09s |
| `martian_keycloak_2` | martian | 0% | 0% | 0.00 | 0/0/2 | 52.95s |
| `martian_keycloak_3` | martian | 0% | 0% | 0.00 | 0/0/4 | 19.56s |
| `martian_keycloak_4` | martian | 0% | 0% | 0.00 | 0/0/2 | 36.96s |
| `martian_keycloak_5` | martian | 100% | 40% | 0.57 | 2/0/3 | 10.80s |
| `martian_keycloak_6` | martian | 100% | 50% | 0.67 | 1/0/1 | 11.82s |
| `martian_keycloak_7` | martian | 33% | 20% | 0.25 | 1/2/4 | 11.87s |
| `martian_keycloak_8` | martian | 0% | 0% | 0.00 | 0/2/4 | 10.31s |
| `martian_keycloak_9` | martian | 100% | 100% | 1.00 | 2/0/0 | 18.51s |
| `martian_keycloak_10` | martian | 0% | 0% | 0.00 | 0/0/2 | 36.52s |
| `martian_sentry_1` | martian | 33% | 25% | 0.29 | 1/2/3 | 11.06s |
| `martian_sentry_2` | martian | 50% | 25% | 0.33 | 1/1/3 | 25.09s |
| `martian_sentry_3` | martian | 0% | 0% | 0.00 | 0/2/3 | 37.31s |
| `martian_sentry_4` | martian | 50% | 33% | 0.40 | 1/1/2 | 29.84s |
| `martian_sentry_5` | martian | 0% | 0% | 0.00 | 0/0/6 | 7.09s |
| `martian_sentry_6` | martian | 0% | 0% | 0.00 | 0/0/5 | 1.46s |
| `martian_sentry_7` | martian | 0% | 0% | 0.00 | 0/1/4 | 10.29s |
| `martian_sentry_8` | martian | 0% | 0% | 0.00 | 0/0/2 | 8.07s |
| `martian_sentry_9` | martian | 0% | 0% | 0.00 | 0/2/2 | 11.38s |
| `martian_sentry_10` | martian | 0% | 0% | 0.00 | 0/0/3 | 11.16s |
