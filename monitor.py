import psutil
from storage import save_cpu_data


def get_cpu_usage():
    return psutil.cpu_percent(interval=1)


def get_core_usage():
    return psutil.cpu_percent(interval=1, percpu=True)


def get_core_count():
    return psutil.cpu_count(logical=False)


def get_logical_core_count():
    return psutil.cpu_count(logical=True)


def get_context_switches():
    stats = psutil.cpu_stats()
    return stats.ctx_switches


def get_process_count():
    return len(psutil.pids())


def get_total_threads():
    total_threads = 0

    for process in psutil.process_iter(['num_threads']):
        try:
            total_threads += process.info['num_threads']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return total_threads


def get_process_details():
    processes = []

    for process in psutil.process_iter(['pid', 'name', 'cpu_percent', 'num_threads']):
        try:
            processes.append(process.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return processes
def get_top_processes(limit=5):
    processes = []

    for process in psutil.process_iter(
        ['pid', 'name', 'num_threads']
    ):
        try:
            name = process.info['name']

            # Ignore System Idle Process
            if name == "System Idle Process":
                continue

            cpu_usage = process.cpu_percent(interval=0.1)

            processes.append({
                'pid': process.info['pid'],
                'name': name,
                'cpu_percent': cpu_usage,
                'num_threads': process.info['num_threads']
            })

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    processes.sort(
        key=lambda process: process['cpu_percent'],
        reverse=True
    )

    return processes[:limit]
def get_cpu_temperature():
    try:
        temperatures = psutil.sensors_temperatures()

        if not temperatures:
            return None

        for sensor_group in temperatures.values():
            for sensor in sensor_group:
                if sensor.current is not None:
                    return sensor.current

        return None

    except Exception:
        return None
import time
def monitor_for_10_seconds():
    print("\n===== LIVE MONITORING =====")

    for i in range(10):
        cpu = get_cpu_usage()
        core_usage = get_core_usage()
        context_switches = get_context_switches()
        processes = get_process_count()
        threads = get_total_threads()
        temperature = get_cpu_temperature()

        if temperature is None:
            temperature = "N/A"

        data = [
            time.strftime("%H:%M:%S"),
            cpu,
            core_usage,
            context_switches,
            processes,
            threads,
            temperature
        ]

        save_cpu_data(data)

        print(
            "Second:", i + 1,
            "| CPU:", cpu, "%",
            "| Processes:", processes,
            "| Threads:", threads
        )

        time.sleep(1)
monitor_for_10_seconds()

def main():
    print("===== CORVO CPU MONITOR =====")

    print("CPU Usage:", get_cpu_usage(), "%")
    print("Core Usage:", get_core_usage())
    print("Physical Cores:", get_core_count())
    print("Logical Cores:", get_logical_core_count())
    print("Context Switches:", get_context_switches())
    print("Running Processes:", get_process_count())
    print("Total Threads:", get_total_threads())
    temperature = get_cpu_temperature()

    if temperature is not None:
        print("CPU Temperature:", temperature, "°C")
    else:
        print("CPU Temperature: Not Available")

    print("\n===== PROCESS DETAILS =====")

    processes = get_process_details()

    for process in processes[:10]:
        print(process)
print("\n===== TOP CPU PROCESSES =====")

top_processes = get_top_processes()

for process in top_processes:
    print(
        "PID:", process['pid'],
        "| Name:", process['name'],
        "| CPU:", process['cpu_percent'], "%",
        "| Threads:", process['num_threads']
    )

if __name__ == "__main__":
    main()