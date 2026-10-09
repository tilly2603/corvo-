"""
visualizer.py  -  CORVO (Soham)

Matplotlib drawing functions for the CORVO dashboard.

Every function receives an Axes object ("ax") and draws on it.
It does NOT call plt.show(), so the same function can be used:
  * inside the Tkinter window  (gui.py puts the Figure in a FigureCanvasTkAgg)
  * on its own for testing     (run:  python visualizer.py)

If data is missing (None / empty), the function writes a short message on
the chart instead of crashing.
"""

# One restrained colour palette, used by every chart
ACCENT = "#2F5D8A"      # main line / bar colour
ACCENT_2 = "#C0633A"    # second colour (only used where a 2nd series exists)
GRID = "#D9D9D9"


def show_message(ax, text):
    """Write a centred message on an empty chart."""
    ax.clear()
    ax.text(0.5, 0.5, text, ha="center", va="center",
            transform=ax.transAxes, fontsize=11, color="#555555")
    ax.set_xticks([])
    ax.set_yticks([])


def _set_time_ticks(ax, times):
    """Show at most ~5 time labels so the x-axis does not get crowded."""
    step = max(1, -(-len(times) // 5))      # ceiling of len / 5
    positions = list(range(0, len(times), step))
    ax.set_xticks(positions)
    ax.set_xticklabels([times[i] for i in positions])


def _style(ax, title, xlabel, ylabel):
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)


def plot_cpu_usage(ax, times, cpu_usage):
    """Line plot: overall CPU usage over time."""
    if not times or not cpu_usage:
        show_message(ax, "No CPU usage data yet.")
        return

    ax.clear()
    ax.plot(range(len(cpu_usage)), cpu_usage, color=ACCENT,
            marker="o", markersize=3, linewidth=1.8)
    _style(ax, "Overall CPU Usage", "Time", "CPU Usage (%)")
    ax.set_ylim(0, 100)
    _set_time_ticks(ax, times)


def plot_core_usage(ax, core_usage):
    """Bar graph: current usage of each core."""
    if not core_usage:
        show_message(ax, "No per-core data yet.")
        return

    ax.clear()
    labels = [str(i + 1) for i in range(len(core_usage))]
    bars = ax.bar(labels, core_usage, color=ACCENT, width=0.6)

    for bar, value in zip(bars, core_usage):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 1,
                f"{value:.0f}", ha="center", va="bottom", fontsize=8)

    _style(ax, "Per-Core CPU Utilization", "Core", "Usage (%)")
    ax.set_ylim(0, 110)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.grid(False, axis="x")


def plot_temperature(ax, times, temperatures):
    """Line plot: CPU temperature over time (None values are skipped)."""
    # Keep only the readings that are real numbers
    points = [(i, t) for i, t in enumerate(temperatures or [])
              if t is not None]

    if not points:
        show_message(ax, "Temperature data unavailable on this system.")
        return

    ax.clear()
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    ax.plot(xs, ys, color=ACCENT_2, marker="o", markersize=3, linewidth=1.8)
    _style(ax, "CPU Temperature", "Time", "Temperature (°C)")
    _set_time_ticks(ax, times)


def plot_context_switches(ax, times, switch_increase):
    """Line plot: context switches that happened between samples."""
    if not times or not switch_increase:
        show_message(ax, "No context-switch data yet.")
        return

    ax.clear()
    ax.plot(range(len(switch_increase)), switch_increase, color=ACCENT,
            marker="o", markersize=3, linewidth=1.8)
    _style(ax, "Context Switches per Sample", "Time", "Switches")
    _set_time_ticks(ax, times)


def plot_cei(ax, cei_value):
    """Single horizontal bar showing CEI out of 100.

    No GOOD/MODERATE/POOR colouring: the thresholds belong to the
    analyzer (Palak) and are not final yet.
    """
    if cei_value is None:
        show_message(ax, "CEI not calculated yet.")
        return

    ax.clear()
    ax.barh(["CEI"], [100], color="#E6E6E6", height=0.4)
    ax.barh(["CEI"], [cei_value], color=ACCENT, height=0.4)
    if cei_value >= 30:     # enough room: write the value inside the bar
        ax.text(2, 0, f"{cei_value:.1f} / 100", va="center",
                color="white", fontsize=11, fontweight="bold")
    else:                   # bar too short: write the value after it
        ax.text(cei_value + 2, 0, f"{cei_value:.1f} / 100", va="center",
                fontsize=11, fontweight="bold")
    ax.set_xlim(0, 100)
    ax.set_ylim(-1.5, 1.5)          # keeps the bar slim
    ax.set_title("Core Efficiency Index (CEI)", fontsize=11,
                 fontweight="bold")
    ax.set_xlabel("Score out of 100")
    ax.set_yticks([])


def plot_benchmark(ax, results):
    """Bar graph: benchmark time for 1, 2, 4, 8 ... workers.

    Question answered: does the total time drop when more cores are used?
    The speedup (compared with 1 worker) is written above each bar.
    """
    if not results:
        show_message(ax, "Run the benchmark to see results.")
        return

    ax.clear()
    labels = [str(row["Workers"]) for row in results]
    times = [row["Time"] for row in results]
    bars = ax.bar(labels, times, color=ACCENT, width=0.55)

    for bar, row in zip(bars, results):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f"{row['Time']:.2f} s\n{row['Speedup']:.2f}x",
                ha="center", va="bottom", fontsize=9)

    _style(ax, "Benchmark: Execution Time vs Workers",
           "Number of worker processes", "Time (seconds)")
    ax.set_ylim(0, max(times) * 1.25)
    ax.grid(False, axis="x")


# ---------------------------------------------------------------
# Stand-alone test with DUMMY data (not real measurements)
# Run:  python visualizer.py
# ---------------------------------------------------------------
if __name__ == "__main__":
    import matplotlib.pyplot as plt

    dummy_times = ["10:00:00", "10:00:05", "10:00:10", "10:00:15",
                   "10:00:20", "10:00:25", "10:00:30", "10:00:35"]
    dummy_cpu = [25, 31, 45, 52, 48, 61, 55, 42]
    dummy_cores = [32, 71, 44, 39, 12, 5, 60, 22]
    dummy_switches = [31000, 42000, 38000, 55000, 47000, 61000, 52000, 40000]

    fig, axes = plt.subplots(2, 3, figsize=(14, 7))
    plot_cpu_usage(axes[0][0], dummy_times, dummy_cpu)
    plot_core_usage(axes[0][1], dummy_cores)
    plot_temperature(axes[0][2], dummy_times, [None] * 8)   # unavailable case
    plot_context_switches(axes[1][0], dummy_times, dummy_switches)
    plot_cei(axes[1][1], 82)
    plot_benchmark(axes[1][2], [                            # dummy benchmark
        {"Workers": 1, "Time": 6.0, "Speedup": 1.0},
        {"Workers": 2, "Time": 3.1, "Speedup": 1.94},
        {"Workers": 4, "Time": 1.7, "Speedup": 3.53},
        {"Workers": 8, "Time": 1.1, "Speedup": 5.45}])
    fig.tight_layout()
    plt.show()