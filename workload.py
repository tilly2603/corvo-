"""
workload.py  -  CORVO Multi-core Processor Analyser

Multicore benchmark: the SAME amount of CPU-bound work (matrix
multiplication) is run with 1, 2, 4, 8 ... worker processes.
If the CPU scales well, the total time drops as workers are added.

Why plain Python loops (no NumPy)?
    NumPy's matrix multiplication already uses several cores by itself,
    which would hide the effect of our worker processes.  Plain loops
    run on ONE core per process, so the effect of the workers is clear.

Why processes and not threads?
    Python threads share one interpreter lock (GIL), so CPU-bound threads
    do not run in parallel.  Separate processes do.

Result format of run_benchmark()  (a list, one dictionary per test):
    {"Workers": 4, "Time": 1.52, "Speedup": 3.1, "Parallel Efficiency": 77.5}

Run on its own:   python workload.py
"""

import multiprocessing
import os
import time

MATRIX_SIZE = 160      # each task multiplies two 160 x 160 matrices
TASK_COUNT = 24        # total tasks (divides evenly by 1, 2, 3, 4, 6, 8, 12)


def multiply_matrices(size):
    """One CPU-bound task: multiply two size x size matrices (nested loops)."""
    a = [[(i + j) % 10 for j in range(size)] for i in range(size)]
    b = [[(i * j) % 10 for j in range(size)] for i in range(size)]
    result = [[0] * size for _ in range(size)]

    for i in range(size):
        for j in range(size):
            total = 0
            for k in range(size):
                total += a[i][k] * b[k][j]
            result[i][j] = total

    return result[0][0]      # return one number, not the whole matrix


def warm_up(number):
    """Tiny task so every worker process has started before timing begins."""
    return number


def get_worker_counts(max_workers):
    """1, 2, 4, 8 ... up to max_workers (max_workers itself is included)."""
    counts = [1]
    workers = 2
    while workers < max_workers:
        counts.append(workers)
        workers *= 2
    if max_workers > 1:
        counts.append(max_workers)
    return counts


def time_workload(worker_count, task_count=TASK_COUNT, size=MATRIX_SIZE):
    """Run all tasks with worker_count processes.  Returns seconds."""
    with multiprocessing.Pool(processes=worker_count) as pool:
        pool.map(warm_up, range(worker_count))          # start the workers

        start = time.perf_counter()
        pool.map(multiply_matrices, [size] * task_count, chunksize=1)
        end = time.perf_counter()

    return end - start


def run_benchmark(max_workers=None):
    """Run the benchmark for 1, 2, 4, 8 ... workers.  Returns a list."""
    if max_workers is None:
        # Keep the default GUI run bounded; machines with many logical CPUs
        # should not accidentally launch dozens/hundreds of worker processes.
        max_workers = min(os.cpu_count() or 1, 8)
    max_workers = max(1, min(int(max_workers), os.cpu_count() or int(max_workers)))

    results = []
    single_worker_time = None

    for workers in get_worker_counts(max_workers):
        seconds = time_workload(workers)

        if single_worker_time is None:         # the first test has 1 worker
            single_worker_time = seconds

        speedup = single_worker_time / seconds
        efficiency = speedup / workers * 100

        results.append({
            "Workers": workers,
            "Time": round(seconds, 2),
            "Speedup": round(speedup, 2),
            "Parallel Efficiency": round(efficiency, 1),
        })

    return results


if __name__ == "__main__":
    print("CORVO benchmark: matrix multiplication,", TASK_COUNT, "tasks of",
          MATRIX_SIZE, "x", MATRIX_SIZE)
    print("Logical cores:", os.cpu_count())
    print()
    print(f"{'Workers':>8} {'Time (s)':>10} {'Speedup':>9} {'Efficiency':>12}")

    for row in run_benchmark():
        print(f"{row['Workers']:>8} {row['Time']:>10} {row['Speedup']:>9} "
              f"{row['Parallel Efficiency']:>11}%")