from monitor import get_system_snapshot


def calculate_core_balance(core_usage):
    if not core_usage:
        return 0

    average = sum(core_usage) / len(core_usage)

    differences = []

    for usage in core_usage:
        differences.append(abs(usage - average))

    average_difference = sum(differences) / len(differences)

    balance = 100 - average_difference

    if balance < 0:
        balance = 0

    return round(balance, 2)


def analyze_core_activity(core_usage):
    active_cores = 0
    idle_cores = 0

    for usage in core_usage:
        if usage > 5:
            active_cores += 1
        else:
            idle_cores += 1

    return active_cores, idle_cores


def analyze_thread_distribution(total_threads, process_count):
    if process_count == 0:
        return 0

    average_threads = total_threads / process_count

    return round(average_threads, 2)


def analyze_context_switches(current_switches, previous_switches):
    if previous_switches is None:
        return 0

    switch_difference = current_switches - previous_switches

    if switch_difference < 0:
        return 0

    return switch_difference


def calculate_cei(core_balance, active_cores, total_cores, average_threads):
    if total_cores == 0:
        return 0

    core_utilization = (active_cores / total_cores) * 100

    # Thread score
    if average_threads <= 20:
        thread_score = 100
    elif average_threads <= 50:
        thread_score = 80
    elif average_threads <= 100:
        thread_score = 60
    else:
        thread_score = 40

    cei = (
        (0.5 * core_balance)
        + (0.3 * core_utilization)
        + (0.2 * thread_score)
    )

    return round(cei, 2)


def generate_recommendations(
    core_balance,
    active_cores,
    total_cores,
    average_threads,
    context_switches
):
    recommendations = []

    if core_balance < 70:
        recommendations.append(
            "CPU workload is unevenly distributed across cores."
        )
    else:
        recommendations.append(
            "CPU workload is well distributed across cores."
        )

    if active_cores < total_cores / 2:
        recommendations.append(
            "Many CPU cores are underutilized."
        )
    else:
        recommendations.append(
            "A sufficient number of CPU cores are active."
        )

    if average_threads > 50:
        recommendations.append(
            "High average threads per process detected."
        )
    else:
        recommendations.append(
            "Thread load per process is within the normal project threshold."
        )

    if context_switches > 100000:
        recommendations.append(
            "High context-switch activity detected."
        )
    else:
        recommendations.append(
            "Context-switch activity is within the project threshold."
        )

    return recommendations


def analyze_system(
    core_usage,
    total_threads,
    process_count,
    current_switches,
    previous_switches
):
    balance = calculate_core_balance(core_usage)

    active, idle = analyze_core_activity(core_usage)

    average_threads = analyze_thread_distribution(
        total_threads,
        process_count
    )

    switch_difference = analyze_context_switches(
        current_switches,
        previous_switches
    )

    cei = calculate_cei(
        balance,
        active,
        len(core_usage),
        average_threads
    )

    recommendations = generate_recommendations(
        balance,
        active,
        len(core_usage),
        average_threads,
        switch_difference
    )

    return {
        "Core Balance": balance,
        "Active Cores": active,
        "Idle Cores": idle,
        "Average Threads per Process": average_threads,
        "Context Switch Increase": switch_difference,
        "CEI": cei,
        "Recommendations": recommendations
    }


if __name__ == "__main__":
    print("Taking first system snapshot...")
    snapshot1 = get_system_snapshot()

    import time
    time.sleep(2)

    print("Taking second system snapshot...")
    snapshot2 = get_system_snapshot()

    result = analyze_system(
        snapshot2["Core Usage"],
        snapshot2["Threads"],
        snapshot2["Processes"],
        snapshot2["Context Switches"],
        snapshot1["Context Switches"]
    )

    print("\n===== CORVO ANALYSIS =====")
    print("CPU Usage:", snapshot2["CPU Usage"])
    print("Core Usage:", snapshot2["Core Usage"])
    print("Core Balance:", result["Core Balance"])
    print("Active Cores:", result["Active Cores"])
    print("Idle Cores:", result["Idle Cores"])
    print(
        "Average Threads per Process:",
        result["Average Threads per Process"]
    )
    print(
        "Context Switch Increase:",
        result["Context Switch Increase"]
    )
    print(
        "Core Efficiency Index (CEI):",
        result["CEI"]
    )

    print("\n===== RECOMMENDATIONS =====")

    for recommendation in result["Recommendations"]:
        print("-", recommendation)