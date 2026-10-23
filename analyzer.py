"""CORVO scoring and recommendation engine.

CEI uses the agreed six fixed weights. If an input is unavailable, the
available weighted components are normalized to 100 and the result is clearly
marked provisional; the official six-component formula is unchanged.
"""
from __future__ import annotations

WEIGHTS = {"B": 0.25, "T": 0.20, "A": 0.15, "C": 0.15, "H": 0.10, "S": 0.15}
COMPONENT_NAMES = {
    "B": "Core Utilization Balance",
    "T": "Thread Distribution",
    "A": "Active/Idle Core Efficiency",
    "C": "Context-Switching Efficiency",
    "H": "Thermal Efficiency",
    "S": "Benchmark Scalability",
}


def _clamp(value, low=0.0, high=100.0):
    return max(low, min(high, float(value)))


def calculate_core_balance(core_usage):
    """B: 100 minus mean absolute deviation, in percentage points."""
    if not core_usage:
        return None
    values = [_clamp(v) for v in core_usage]
    mean = sum(values) / len(values)
    mean_absolute_deviation = sum(abs(v - mean) for v in values) / len(values)
    return round(_clamp(100 - mean_absolute_deviation), 2)


def analyze_core_activity(core_usage, active_threshold=5.0):
    active = sum(1 for usage in core_usage if usage > active_threshold)
    return active, len(core_usage) - active


def analyze_thread_distribution(total_threads, process_count, logical_cores=None):
    """Return an average-thread pressure proxy, not a per-thread scheduler map."""
    if not process_count or total_threads is None:
        return None
    return round(max(0, total_threads) / process_count, 2)


def calculate_thread_score(total_threads, process_count, logical_cores):
    """T: unavailable until CORVO can measure runnable-thread distribution.

    Total OS thread count / process count is not a defensible measure of how
    runnable work is distributed across cores. Returning a perfect score from
    that proxy made the CEI misleading. Keep the counts for diagnostics and
    recommendations, but exclude T from CEI until a valid metric is collected.
    """
    return None


def calculate_active_idle_score(active_cores, total_cores, cpu_usage):
    """A: score active capacity only when there is enough demand to judge it.

    At low system utilization, idle cores are normal and cannot establish
    either good or poor parallel efficiency. Treat A as unavailable until
    utilization is high enough to make active/idle distribution informative.
    """
    if not total_cores or cpu_usage is None:
        return None
    usage = _clamp(cpu_usage)
    if usage < 20:
        return None
    active_ratio = _clamp((active_cores / total_cores) * 100)
    # At high demand, broad core participation is useful; at moderate demand,
    # avoid requiring every core to be active.
    expected = max(20.0, usage * 0.75)
    if active_ratio >= expected:
        return 100.0
    return round(_clamp(100 * active_ratio / expected), 2)


def analyze_context_switches(current_switches, previous_switches):
    """Return context-switch count delta, or None until a baseline exists."""
    if current_switches is None or previous_switches is None:
        return None
    delta = current_switches - previous_switches
    if delta < 0:  # counter reset / reboot: establish a new baseline
        return None
    return delta


def calculate_context_score(switch_delta, interval_seconds=1.0, logical_cores=None):
    """C: heuristic score from context switches/sec/logical core."""
    if switch_delta is None or not logical_cores or interval_seconds <= 0:
        return None
    rate_per_core = switch_delta / interval_seconds / logical_cores
    # Explicit project thresholds; rates alone cannot prove a bottleneck.
    if rate_per_core <= 500:
        score = 100
    elif rate_per_core <= 1500:
        score = 100 - (rate_per_core - 500) * 0.03
    elif rate_per_core <= 4000:
        score = 70 - (rate_per_core - 1500) * 0.012
    else:
        score = max(10, 40 - (rate_per_core - 4000) * 0.003)
    return round(_clamp(score), 2)


def calculate_thermal_score(temperature, thermal_limit=100.0):
    """H: score against a configurable limit; absent temperature stays absent."""
    if temperature is None or thermal_limit is None or thermal_limit <= 0:
        return None
    # Generic fallback is an assumption, not a claimed CPU-specific limit.
    ratio = _clamp((temperature / thermal_limit) * 100)
    if ratio <= 50:
        score = 100
    elif ratio <= 70:
        score = 100 - (ratio - 50) * 1.0
    elif ratio <= 85:
        score = 80 - (ratio - 70) * 2.0
    else:
        score = max(0, 50 - (ratio - 85) * (50 / 15))
    return round(_clamp(score), 2)


def calculate_scalability_score(benchmark_results):
    """S: combine speedup and parallel efficiency from benchmark results."""
    if not benchmark_results:
        return None
    usable = [r for r in benchmark_results if r.get("Workers", 0) > 0 and r.get("Time", 0) > 0]
    if len(usable) < 2:
        return None
    baseline = next((r for r in usable if r["Workers"] == 1), None)
    if baseline is None:
        baseline = min(usable, key=lambda r: r["Workers"])
    best = max(usable, key=lambda r: (r.get("Speedup", 0), r.get("Workers", 1)))
    workers = max(1, best["Workers"] / baseline["Workers"])
    speedup = min(float(best.get("Speedup", baseline["Time"] / best["Time"])), workers)
    efficiency = _clamp((speedup / workers) * 100)
    # Balanced score rewards measured speedup and efficiency rather than worker count alone.
    score = 0.5 * _clamp(speedup / workers * 100) + 0.5 * efficiency
    return round(_clamp(score), 2)


def classify_cei(cei):
    if cei is None:
        return "N/A"
    if cei >= 85:
        return "GOOD"
    if cei >= 60:
        return "MODERATE"
    return "POOR"


def calculate_cei(component_scores):
    """Calculate weighted CEI; normalize only across valid components."""
    valid = {key: value for key, value in component_scores.items()
             if key in WEIGHTS and value is not None}
    if not valid:
        return None, "unavailable", []
    weight_total = sum(WEIGHTS[key] for key in valid)
    weighted = sum(WEIGHTS[key] * _clamp(value) for key, value in valid.items())
    score = round(weighted / weight_total, 2)
    missing = [key for key in WEIGHTS if key not in valid]
    return score, ("full" if not missing else "provisional"), missing


def _recommendation(title, priority, evidence, cause, solutions, action=None):
    details = [f"{title} [{priority} priority]", f"Evidence: {evidence}",
               f"Possible cause: {cause}", "Suggested solutions: " + "; ".join(solutions)]
    if action:
        details.append("Available action: " + action)
    return "\n".join(details)


def generate_recommendations(core_balance, active_cores, total_cores,
                             average_threads, context_switches,
                             cpu_usage=None, temperature=None, cei=None,
                             component_scores=None, benchmark_results=None,
                             logical_cores=None, process_count=None, total_threads=None,
                             previous_temperature=None, previous_cpu_usage=None, previous_process_count=None,
                             previous_thread_count=None, previous_cei=None,
                             process_details=None, save_error=None):
    """Generate evidence-based, actionable recommendations without claiming certainty."""
    recs = []
    components = component_scores or {}
    if core_balance is not None and core_balance < 75:
        recs.append(_recommendation("Uneven core utilization", "MEDIUM",
            f"B={core_balance:.1f}/100", "single-threaded work, CPU affinity, or an uneven workload",
            ["Inspect the top CPU-consuming processes", "Check whether the application can parallelize work",
             "Compare CORVO benchmark runs at different worker counts"],
            "Run a selected-worker benchmark and compare results."))
    if cpu_usage is not None and cpu_usage >= 90:
        recs.append(_recommendation("Sustained CPU saturation", "HIGH",
            f"overall CPU usage is {cpu_usage:.1f}%", "a CPU-bound task or competing background work",
            ["Inspect top CPU processes", "Close only applications you recognize and do not need",
             "Reduce workload intensity if the system is unresponsive"],
            "Open the process overview; CORVO will not terminate processes automatically."))
    if cpu_usage is not None and cpu_usage < 10:
        recs.append(_recommendation("Low CPU utilization", "INFORMATIONAL",
            f"overall CPU usage is {cpu_usage:.1f}%", "the system may be idle or waiting on disk, network, or user input",
            ["Interpret this together with the workload", "Run the controlled CORVO CPU benchmark if performance is being evaluated"]))
    if (cpu_usage is not None and cpu_usage >= 65 and active_cores < max(1, total_cores * 0.5)):
        recs.append(_recommendation("High demand with many idle cores", "MEDIUM",
            f"CPU usage is {cpu_usage:.1f}% while {active_cores}/{total_cores} cores are active",
            "single-thread bottlenecks, affinity restrictions, or workload structure",
            ["Check whether the workload supports parallel execution", "Inspect application affinity settings without changing them automatically", "Compare controlled benchmark worker counts"],
            "Run the selected-worker benchmark."))
    if cpu_usage is not None and cpu_usage >= 70 and core_balance is not None and core_balance < 85:
        recs.append(_recommendation("Possible scheduling or affinity bottleneck", "MEDIUM",
            f"CPU usage is {cpu_usage:.1f}% and B={core_balance:.1f}/100",
            "a concentrated task, affinity restriction, or uneven workload",
            ["Inspect the workload and CPU-affinity settings", "Check whether work can be parallelized", "Repeat monitoring during a representative workload"]))
    if (temperature is not None and previous_temperature is not None
            and temperature - previous_temperature >= 10):
        recs.append(_recommendation("Rapid temperature rise", "HIGH",
            f"temperature increased from {previous_temperature:.1f} °C to {temperature:.1f} °C",
            "a sudden load increase or cooling/airflow limitation",
            ["Check airflow and vents", "Pause optional benchmark work if temperature keeps rising", "Compare readings against the processor's documented thermal limit"],
            "Stop optional benchmark runs if the rise continues."))
    if (previous_cpu_usage is not None and cpu_usage is not None
            and abs(cpu_usage - previous_cpu_usage) >= 35):
        recs.append(_recommendation("Sharp CPU utilization fluctuation", "MEDIUM",
            f"CPU usage changed from {previous_cpu_usage:.1f}% to {cpu_usage:.1f}% between samples",
            "a bursty workload or background process activity",
            ["Collect more samples before changing settings", "Review process activity during the spike", "Compare readings during a repeatable workload"]))
    if (previous_process_count is not None and process_count is not None
            and process_count - previous_process_count >= 20):
        recs.append(_recommendation("Process count increased sharply", "MEDIUM",
            f"process count rose from {previous_process_count} to {process_count}",
            "applications or services starting many processes",
            ["Review recently opened applications", "Check whether the count settles after startup", "Investigate unexpected repeated process creation"]))
    if (previous_thread_count is not None and total_threads is not None
            and total_threads - previous_thread_count >= max(100, int(previous_thread_count * 0.25))):
        recs.append(_recommendation("Thread count increased sharply", "MEDIUM",
            f"thread count rose from {previous_thread_count} to {total_threads}",
            "a thread-heavy workload or possible resource growth",
            ["Observe whether the count stabilizes", "Review applications that recently started", "Repeat measurements during a comparable workload"]))
    if process_details:
        top = max(process_details, key=lambda p: p.get("cpu_percent", 0), default=None)
        if top and top.get("cpu_percent", 0) >= 70:
            recs.append(_recommendation("One process dominates CPU usage", "MEDIUM-HIGH",
                f"{top.get('name', 'Unknown process')} (PID {top.get('pid', '?')}) reports {top.get('cpu_percent', 0):.1f}% CPU",
                "one CPU-heavy task or an application-specific workload",
                ["Check whether the process is expected", "Save work before closing any application", "Investigate the process documentation if the load is unexpected"],
                "Inspect the process; termination is not automatic."))
    if save_error:
        recs.append(_recommendation("Monitoring data could not be saved", "MEDIUM",
            str(save_error), "file permissions, a locked CSV, or a storage error",
            ["Close the CSV in spreadsheet software", "Check write permissions for the data folder", "Retry monitoring after resolving the file issue"]))
    if previous_cei is not None and cei is not None and previous_cei - cei >= 10:
        recs.append(_recommendation("CEI dropped significantly", "MEDIUM-HIGH",
            f"CEI changed from {previous_cei:.1f} to {cei:.1f}",
            "one or more component scores declined or the available component set changed",
            ["Compare the component scores and excluded inputs", "Check whether the workload changed", "Repeat measurement under comparable conditions"]))
    if average_threads is not None and average_threads > 50:
        recs.append(_recommendation("High average threads per process", "MEDIUM",
            f"average is {average_threads:.1f} threads/process", "thread-heavy applications or many background services",
            ["Review processes with high thread counts", "Check for excessive concurrency or thread growth",
             "Compare a lower-worker benchmark configuration"],
            "Run the benchmark with a selected worker count."))
    if context_switches is not None and logical_cores and context_switches / logical_cores > 1500:
        recs.append(_recommendation("High context-switch activity", "MEDIUM",
            f"{context_switches:,} switches in the latest sampling interval", "many runnable tasks, synchronization, or normal high system activity",
            ["Compare several samples instead of relying on one spike", "Inspect CPU-heavy processes", "Benchmark with fewer workers and compare elapsed time"] ,
            "Run a controlled worker-count comparison."))
    if temperature is not None and temperature >= 85:
        recs.append(_recommendation("High CPU temperature", "HIGH",
            f"reported temperature is {temperature:.1f} °C", "heavy load, restricted airflow, cooling, or sensor-specific limits",
            ["Check vents and airflow", "Stop optional stress/benchmark work if temperature continues rising", "Check the CPU manufacturer's thermal specifications"],
            "Pause optional benchmark runs; CORVO does not alter cooling controls."))
    if temperature is None:
        recs.append(_recommendation("Temperature data unavailable", "INFORMATIONAL",
            "no supported temperature reading was returned", "the OS, sensor, or hardware does not expose temperature to psutil",
            ["Check vendor monitoring software or firmware diagnostics", "Do not interpret missing temperature as a cool CPU"]))
    if components.get("S") is None:
        recs.append(_recommendation("Benchmark scalability not measured", "INFORMATIONAL",
            "S is unavailable until a valid benchmark comparison exists", "no benchmark has run in this session or fewer than two worker configurations were measured",
            ["Run the CORVO benchmark", "Compare elapsed time, speedup and parallel efficiency"],
            "Use the benchmark controls below."))
    elif components.get("S", 100) < 60:
        recs.append(_recommendation("Poor benchmark scalability", "MEDIUM",
            f"S={components['S']:.1f}/100", "serial work, process overhead, synchronization, or workload size",
            ["Compare 1, 2, 4 and other supported worker counts", "Choose the configuration with the best measured time", "Inspect context-switch rate and task size"],
            "Run a selected-worker benchmark and compare before/after."))
    if benchmark_results and len(benchmark_results) >= 2:
        valid_benchmarks = [r for r in benchmark_results if r.get("Workers", 0) > 1]
        if valid_benchmarks:
            best_efficiency = max(r.get("Parallel Efficiency", 0) for r in valid_benchmarks)
            if best_efficiency < 50:
                recs.append(_recommendation("Low parallel efficiency", "MEDIUM",
                    f"best measured parallel efficiency is {best_efficiency:.1f}%",
                    "serial work, process overhead, synchronization, or workload size",
                    ["Compare fewer workers", "Increase benchmark work size only if appropriate", "Choose the best measured elapsed time rather than the highest worker count"],
                    "Run a selected-worker comparison."))
    if cei is not None and cei < 60:
        weakest = min(((score, key) for key, score in components.items() if score is not None), default=None)
        detail = f"weakest measured component: {COMPONENT_NAMES[weakest[1]]} ({weakest[0]:.1f})" if weakest else "component detail unavailable"
        recs.append(_recommendation("Low overall CEI", "HIGH", f"CEI={cei:.1f}/100; {detail}",
            "one or more measured efficiency dimensions are weak", ["Open the component breakdown", "Address the lowest valid component first", "Re-measure under comparable workload conditions"]))
    if not recs:
        recs.append(_recommendation("No major issue detected", "INFORMATIONAL",
            f"CEI status: {classify_cei(cei)}", "no current rule crossed its alert threshold",
            ["Keep monitoring during a representative workload", "Run the benchmark when you want to assess scalability"]))
    return recs


def analyze_system(core_usage, total_threads, process_count, current_switches,
                   previous_switches, cpu_usage=None, temperature=None,
                   benchmark_results=None, logical_cores=None,
                   context_interval_seconds=2.0, thermal_limit=100.0,
                   previous_temperature=None, previous_cpu_usage=None,
                   previous_process_count=None, previous_thread_count=None,
                   previous_cei=None, process_details=None, save_error=None):
    total_cores = len(core_usage or [])
    logical_cores = logical_cores or total_cores
    balance = calculate_core_balance(core_usage)
    active, idle = analyze_core_activity(core_usage or [])
    average_threads = analyze_thread_distribution(total_threads, process_count, logical_cores)
    switch_delta = analyze_context_switches(current_switches, previous_switches)
    scores = {
        "B": balance,
        "T": calculate_thread_score(total_threads, process_count, logical_cores),
        "A": calculate_active_idle_score(active, total_cores, cpu_usage),
        "C": calculate_context_score(switch_delta, context_interval_seconds, logical_cores),
        "H": calculate_thermal_score(temperature, thermal_limit),
        "S": calculate_scalability_score(benchmark_results),
    }
    cei, cei_mode, missing = calculate_cei(scores)
    recommendations = generate_recommendations(
        balance, active, total_cores, average_threads, switch_delta,
        cpu_usage=cpu_usage, temperature=temperature, cei=cei,
        component_scores=scores, benchmark_results=benchmark_results,
        logical_cores=logical_cores, process_count=process_count, total_threads=total_threads,
        previous_temperature=previous_temperature,
        previous_cpu_usage=previous_cpu_usage,
        previous_process_count=previous_process_count,
        previous_thread_count=previous_thread_count, previous_cei=previous_cei,
        process_details=process_details, save_error=save_error)
    return {
        "Core Balance": balance if balance is not None else 0.0,
        "Active Cores": active, "Idle Cores": idle,
        "Average Threads per Process": average_threads if average_threads is not None else 0.0,
        "Context Switch Increase": switch_delta,
        "CEI": cei, "CEI Mode": cei_mode, "CEI Missing Components": missing,
        "CEI Rating": classify_cei(cei), "CEI Components": scores,
        "Recommendations": recommendations,
    }


if __name__ == "__main__":
    from monitor import get_system_snapshot
    import time
    first = get_system_snapshot()
    time.sleep(1)
    second = get_system_snapshot()
    result = analyze_system(second["Core Usage"], second["Threads"], second["Processes"],
                            second["Context Switches"], first["Context Switches"],
                            cpu_usage=second["CPU Usage"], temperature=second["Temperature"],
                            logical_cores=second["Logical Cores"])
    for key, value in result.items():
        print(f"{key}: {value}")
