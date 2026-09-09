# GitAmi Benchmark Evaluation Report

**Run Timestamp**: `2026-09-09 14:02:01`  
**Datasets Evaluated**: `martian, vulngym`  
**Total Cases**: `3`  
**Mean Latency**: `58.2s per case`  

## 1. Overall Performance Metrics

| Metric | Value | Description |
| :--- | :--- | :--- |
| **Precision** | **14.3%** | True Positives / Total Predictions (2/14) |
| **Recall** | **15.4%** | True Positives / Ground Truth Issues (2/13) |
| **F1 Score** | **0.1481** | Harmonic mean of Precision and Recall |
| **True Positives (TP)** | `2` | Successfully detected ground-truth defects |
| **False Positives (FP)** | `12` | Spurious or hallucinated issues |
| **False Negatives (FN)** | `11` | Missed ground-truth defects |

## 2. Category Breakdown

| Category | Detected | Total Ground Truth | Detection Rate |
| :--- | :--- | :--- | :--- |
| **Bug** | 2 | 8 | 25.0% |
| **Convention** | 0 | 4 | 0.0% |
| **Performance** | 0 | 1 | 0.0% |

## 3. Severity Breakdown

| Severity | Detection Rate |
| :--- | :--- |
| **Error** | 40.0% |
| **Info** | 0.0% |
| **Warning** | 0.0% |

## 4. Per-Testcase Summary

| Case ID | Dataset | Precision | Recall | F1 Score | TP/FP/FN | Latency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `martian_cal_dot_com_1` | martian | 33% | 50% | 0.40 | 1/2/1 | 47.88s |
| `martian_cal_dot_com_2` | martian | 0% | 0% | 0.00 | 0/6/5 | 69.07s |
| `martian_cal_dot_com_3` | martian | 20% | 17% | 0.18 | 1/4/5 | 57.64s |
