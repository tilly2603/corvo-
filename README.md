# CORVO — Multi-core Processor Analyser

CORVO monitors CPU utilization, per-core activity, process/thread counts, context switches and available CPU temperature. It includes a six-component Core Efficiency Index (CEI), a live dashboard, charts, saved CSV readings, recommendations, and a multiprocessing benchmark.

## Setup

Use Python 3.10 or newer. On Windows, install dependencies from PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

On macOS/Linux, activate `.venv` with the platform's usual command, install requirements, and run `python main.py`.

## CEI formula

The agreed full score is:

`CEI = 0.25B + 0.20T + 0.15A + 0.15C + 0.10H + 0.15S`

- **B (25%)** — Core Utilization Balance
- **T (20%)** — Thread Distribution / thread-pressure proxy
- **A (15%)** — Active/Idle Core Efficiency
- **C (15%)** — Context-Switching Efficiency
- **H (10%)** — Thermal Efficiency
- **S (15%)** — Benchmark Scalability

Each valid component is scored from 0 to 100. When a component cannot be measured, CORVO excludes it and normalizes the remaining original weights to calculate a clearly labelled **provisional** score. When all six components are valid, the exact full formula is used. A missing sensor is never treated as a zero-degree temperature. Context-switch scoring waits for a baseline reading. Scalability is unavailable until at least two benchmark worker configurations have been measured.

### Ratings

- **GOOD:** 85–100
- **MODERATE:** 60–84.99
- **POOR:** below 60

These are project thresholds, not universal hardware standards. A thermal warning is independent of the overall CEI rating.

## Recommendations and actions

Recommendations show observed evidence, possible causes, suggested solutions and available actions. The benchmark controls can run the full worker-count sweep or test a selected worker count. The selected-worker result is compared with the 1-worker baseline when one exists. This benchmark action changes only CORVO's benchmark workload; it does not reconfigure other applications or terminate processes.

Some component calculations are transparent project heuristics. In particular, general-purpose OS APIs do not expose a portable, exact runnable-thread distribution for every process, and the generic thermal fallback may not match a particular CPU's maximum temperature. Treat these indicators as diagnostic guidance and check vendor-specific specifications where applicable.

## Data and tests

Live monitoring rows are appended to `data/cpu_data.csv`. The CSV may contain historical readings from prior runs. Unit tests for CEI boundaries and missing measurements can be run with:

```powershell
python -m unittest discover -s tests -v
```
