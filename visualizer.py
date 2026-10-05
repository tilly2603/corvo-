import matplotlib.pyplot as plt


def plot_cpu_usage(time_points, cpu_usage):
    plt.figure(figsize=(8, 4))

    plt.plot(time_points, cpu_usage, marker="o")

    plt.title("Overall CPU Usage")
    plt.xlabel("Time")
    plt.ylabel("CPU Usage (%)")
    plt.ylim(0, 100)
    plt.grid(True)

    plt.show()


if __name__ == "__main__":
    time_points = [1, 2, 3, 4, 5, 6, 7, 8]
    cpu_usage = [25, 31, 45, 52, 48, 61, 55, 42]

    plot_cpu_usage(time_points, cpu_usage)

def plot_core_usage(core_usage):
    cores = [f"Core {i + 1}" for i in range(len(core_usage))]

    plt.figure(figsize=(8, 4))

    plt.bar(cores, core_usage)

    plt.title("CPU Core Utilization")
    plt.xlabel("CPU Core")
    plt.ylabel("Usage (%)")
    plt.ylim(0, 100)

    plt.show()


if __name__ == "__main__":
    plot_core_usage([32, 71, 44, 39])

def plot_temperature(time_points, temperatures):
    plt.figure(figsize=(8, 4))

    plt.plot(time_points, temperatures, marker="o")

    plt.title("CPU Temperature")
    plt.xlabel("Time")
    plt.ylabel("Temperature (°C)")
    plt.grid(True)

    plt.show()

plot_temperature(
    [1, 2, 3, 4, 5, 6],
    [51, 53, 56, 58, 60, 57]
)