"""
gui.py  -  CORVO Multi-core Processor Analyser (Soham)

Tkinter dashboard.  It only DISPLAYS data; it does not calculate CPU analysis.

Data flow
    MonitorWorker (background thread)
        monitor.get_system_snapshot()   -> Tanishka's readings
        analyzer.analyze_system()       -> Palak's CEI, balance, recommendations
        storage.save_cpu_data()         -> Tanishka's CSV storage
        -> puts ONE dictionary ("data") into a queue.Queue
    CorvoApp (main thread)
        root.after() checks the queue every 200 ms and updates the widgets

Keys of "data" (same names as monitor.py and analyzer.py):
    monitor : Time, CPU Usage, Core Usage, Temperature, Processes, Threads,
              Physical Cores, Logical Cores, Context Switches
    analyzer: Core Balance, Active Cores, Idle Cores,
              Average Threads per Process, Context Switch Increase,
              CEI, Recommendations

Start the program with:   python main.py
"""

import queue
import random
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import analyzer                      # Palak
import monitor                       # Tanishka
import visualizer                    # Soham
import workload                      # benchmark (multiprocessing)
from storage import save_cpu_data    # Tanishka

# ---------------------------------------------------------------
# Settings
# ---------------------------------------------------------------
DUMMY_MODE = False           # True = fake test data, False = real monitoring
QUEUE_CHECK_MS = 200         # how often the GUI looks for a new reading
CSV_FILE = "data/cpu_data.csv"
HISTORY_LIMIT = 60           # number of samples kept for the graphs

# Colours and font (one restrained palette)
FONT = "Segoe UI"
BG = "#F2F4F7"
CARD_BG = "#FFFFFF"
HEADER_BG = "#1F2A37"
BORDER = "#D5DAE1"
TEXT = "#1F2933"
MUTED = "#6B7683"
ACCENT = "#2F5D8A"
GREEN = "#2E7D32"
RED = "#B3402A"


# ---------------------------------------------------------------
# Dummy data (TEST ONLY - not real measurements)
# ---------------------------------------------------------------
def get_dummy_data():
    """Return one fake reading with the same keys as the real data."""
    core_usage = [round(random.uniform(2, 90), 1) for _ in range(8)]
    return {
        "Time": time.strftime("%H:%M:%S"),
        "CPU Usage": round(sum(core_usage) / len(core_usage), 1),
        "Core Usage": core_usage,
        "Temperature": round(random.uniform(48, 62), 1),   # use None to test "unavailable"
        "Processes": random.randint(300, 330),
        "Threads": random.randint(5000, 5300),
        "Physical Cores": 4,
        "Logical Cores": 8,
        "Core Balance": round(random.uniform(60, 90), 2),
        "Active Cores": random.randint(4, 8),
        "Idle Cores": random.randint(0, 4),
        "Average Threads per Process": round(random.uniform(15, 18), 2),
        "Context Switch Increase": random.randint(30000, 70000),
        "CEI": round(random.uniform(60, 90), 2),            # dummy value, not the real formula
        "Recommendations": [
            "CPU workload is well distributed across cores.",
            "A sufficient number of CPU cores are active.",
            "Thread load per process is within the normal project threshold.",
            "Context-switch activity is within the project threshold.",
        ],
    }


# ---------------------------------------------------------------
# Reading the saved CSV (Pandas)
# ---------------------------------------------------------------
def parse_core_usage(text):
    """Turn the text "[41.8, 40.9, 12.0]" from the CSV into a list of floats."""
    return [float(part) for part in text.strip("[] ").split(",")]


def load_saved_data():
    """Read data/cpu_data.csv into a DataFrame (Core Usage becomes a list)."""
    frame = pd.read_csv(CSV_FILE)
    frame["Core Usage"] = frame["Core Usage"].apply(parse_core_usage)
    return frame


def saved_data_lines():
    """Summary lines of the saved CSV, used by the View Analysis window."""
    try:
        frame = load_saved_data()
    except FileNotFoundError:
        return ["No saved data found yet (" + CSV_FILE + ")."]
    except pd.errors.EmptyDataError:
        return ["The saved data file is empty."]
    except (ValueError, KeyError) as error:
        return ["Saved data could not be read: " + str(error)]

    if frame.empty:
        return ["The saved data file has no rows yet."]

    try:
        core_matrix = np.array(frame["Core Usage"].tolist())
        core_average = core_matrix.mean(axis=0)
    except ValueError:
        core_average = []         # rows with different core counts

    temperatures = pd.to_numeric(frame["Temperature"], errors="coerce")

    lines = [
        "SAVED DATA (" + CSV_FILE + ")",
        f"Rows saved: {len(frame)}",
        f"Average CPU usage: {frame['CPU Usage'].mean():.1f} %",
        f"Highest CPU usage: {frame['CPU Usage'].max():.1f} %",
        f"Average threads: {frame['Threads'].mean():.0f}",
        f"Average processes: {frame['Processes'].mean():.0f}",
    ]
    if temperatures.notna().any():
        lines.append(f"Average temperature: {temperatures.mean():.1f} \u00B0C")
    else:
        lines.append("Temperature data unavailable on this system.")
    if len(core_average) > 0:
        lines.append("Average usage per core:")
        for number, value in enumerate(core_average, start=1):
            lines.append(f"   Core {number}: {value:.1f} %")
    return lines


# ---------------------------------------------------------------
# Worker thread
# ---------------------------------------------------------------
class MonitorWorker:
    """Takes readings in a background thread so the window never freezes.

    Why: one real reading takes about 2 seconds (psutil measures CPU usage
    over 1 second, twice).  If the GUI waited for it, the window would freeze.

    Attributes
        data_queue      - thread-safe queue; the GUI reads from it
        stop_event      - threading.Event; set() tells the thread to finish
        thread          - the threading.Thread object
        previous_switches - last context-switch count (the analyzer needs it)
    Methods
        start(), stop(), is_running(), run(), read_real_data()

    The worker never touches Tkinter widgets.  It only puts dictionaries into
    the queue; the GUI thread picks them up with root.after().
    """

    def __init__(self, data_queue):
        self.data_queue = data_queue
        self.stop_event = threading.Event()
        self.thread = None
        self.previous_switches = None

    def start(self):
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def is_running(self):
        return self.thread is not None and self.thread.is_alive()

    def run(self):
        while not self.stop_event.is_set():
            try:
                if DUMMY_MODE:
                    time.sleep(1)
                    data = get_dummy_data()
                else:
                    data = self.read_real_data()
            except Exception as error:
                self.data_queue.put(("error", str(error)))
                return
            self.data_queue.put(("data", data))

    def read_real_data(self):
        """One reading: monitor -> analyzer -> CSV.  Returns the data dict."""
        snapshot = monitor.get_system_snapshot()

        analysis = analyzer.analyze_system(
            snapshot["Core Usage"],
            snapshot["Threads"],
            snapshot["Processes"],
            snapshot["Context Switches"],
            self.previous_switches
        )
        self.previous_switches = snapshot["Context Switches"]

        data = dict(snapshot)
        data.update(analysis)
        data["Save Error"] = self.save_row(snapshot)
        return data

    def save_row(self, snapshot):
        """Save one row with storage.py.  Returns an error text or None."""
        temperature = snapshot["Temperature"]
        if temperature is None:
            temperature = "N/A"           # same as Tanishka's monitor
        row = [snapshot["Time"], snapshot["CPU Usage"], snapshot["Core Usage"],
               snapshot["Context Switches"], snapshot["Processes"],
               snapshot["Threads"], temperature]
        try:
            save_cpu_data(row)
        except OSError as error:          # e.g. CSV is open in Excel
            return "Could not save to CSV: " + str(error)
        return None


# ---------------------------------------------------------------
# Small helper functions that build repeated widgets
# ---------------------------------------------------------------
def make_card(parent, title):
    """A small box with a title, a big value and a small note."""
    card = tk.Frame(parent, bg=CARD_BG, highlightbackground=BORDER,
                    highlightthickness=1)
    tk.Label(card, text=title, font=(FONT, 9), fg=MUTED,
             bg=CARD_BG).pack(anchor="w", padx=12, pady=(10, 0))
    value = tk.Label(card, text="--", font=(FONT, 20, "bold"), fg=TEXT,
                     bg=CARD_BG)
    value.pack(anchor="w", padx=12)
    note = tk.Label(card, text="", font=(FONT, 8), fg=MUTED, bg=CARD_BG)
    note.pack(anchor="w", padx=12, pady=(0, 10))
    return card, value, note


def make_panel(parent, title):
    """A white panel with a heading.  Returns the inner frame for content."""
    panel = tk.Frame(parent, bg=CARD_BG, highlightbackground=BORDER,
                     highlightthickness=1)
    tk.Label(panel, text=title.upper(), font=(FONT, 9, "bold"), fg=ACCENT,
             bg=CARD_BG).pack(anchor="w", padx=14, pady=(10, 4))
    ttk.Separator(panel, orient="horizontal").pack(fill="x", padx=14)
    inner = tk.Frame(panel, bg=CARD_BG)
    inner.pack(fill="both", expand=True, padx=14, pady=10)
    return panel, inner


def set_text(text_widget, lines):
    """Replace the content of a read-only Text widget with bullet lines."""
    text_widget.config(state="normal")
    text_widget.delete("1.0", "end")
    for line in lines:
        text_widget.insert("end", "\u2022  " + line + "\n")
    text_widget.config(state="disabled")


# ---------------------------------------------------------------
# The application
# ---------------------------------------------------------------
class CorvoApp:
    """The main CORVO window.

    Attributes
        root            - the Tk window
        monitoring      - True while monitoring is running
        latest          - the newest data dictionary (or None)
        times, cpu_history, temp_history, switch_history
                        - lists used by the graphs (last HISTORY_LIMIT samples)
        graph_refreshers- functions that redraw the graph windows that are open
    Methods
        build_*         - create the widgets
        handle_new_data - store one reading and refresh the screen
        start_monitoring / stop_monitoring / check_queue / wait_for_worker
        open_graph / view_analysis
    """

    def __init__(self, root):
        self.root = root
        self.root.title("CORVO - Multi-core Processor Analyser")
        self.root.geometry("1180x800")
        self.root.minsize(1120, 720)
        self.root.configure(bg=BG)

        self.monitoring = False
        self.stopping = False        # True while the worker thread finishes
        self.after_id = None
        self.latest = None
        self.data_queue = queue.Queue()
        self.worker = None

        self.benchmark_running = False
        self.benchmark_queue = queue.Queue()
        self.benchmark_results = []

        self.times = []
        self.cpu_history = []
        self.temp_history = []
        self.switch_history = []

        self.graph_refreshers = []
        self.core_rows = []          # (progress bar, value label) per core

        self.setup_style()
        self.build_header()
        self.build_cards()
        self.build_buttons()     # packed before the body so it is never cut off
        self.build_body()

        self.root.protocol("WM_DELETE_WINDOW", self.close_app)

    # ----- building the screen -----------------------------------
    def setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")      # 'clam' lets us change widget colours

        style.configure("Core.Horizontal.TProgressbar", troughcolor="#E3E8EE",
                        background=ACCENT, bordercolor="#E3E8EE",
                        lightcolor=ACCENT, darkcolor=ACCENT, thickness=14)
        style.configure("CEI.Horizontal.TProgressbar", troughcolor="#E3E8EE",
                        background=ACCENT, bordercolor="#E3E8EE",
                        lightcolor=ACCENT, darkcolor=ACCENT, thickness=18)
        style.configure("Corvo.TButton", font=(FONT, 10), padding=(10, 8),
                        background="#FFFFFF", foreground=TEXT,
                        bordercolor=BORDER)
        style.map("Corvo.TButton", background=[("active", "#E8EEF5")],
                  foreground=[("disabled", "#A0A8B2")])
        style.configure("Start.TButton", font=(FONT, 10, "bold"),
                        padding=(12, 8), background=ACCENT,
                        foreground="#FFFFFF", bordercolor=ACCENT)
        style.map("Start.TButton", background=[("active", "#254C73"),
                                               ("disabled", "#B8C4D1")],
                  foreground=[("disabled", "#FFFFFF")])

    def build_header(self):
        header = tk.Frame(self.root, bg=HEADER_BG)
        header.pack(fill="x")

        left = tk.Frame(header, bg=HEADER_BG)
        left.pack(side="left", padx=20, pady=12)
        tk.Label(left, text="CORVO", font=(FONT, 20, "bold"), fg="#FFFFFF",
                 bg=HEADER_BG).pack(anchor="w")
        tk.Label(left, text="Multi-core Processor Analyser", font=(FONT, 10),
                 fg="#B8C2CE", bg=HEADER_BG).pack(anchor="w")

        right = tk.Frame(header, bg=HEADER_BG)
        right.pack(side="right", padx=20)
        self.status_label = tk.Label(right, text="\u25CF  Stopped",
                                     font=(FONT, 11, "bold"), fg="#B8C2CE",
                                     bg=HEADER_BG)
        self.status_label.pack(anchor="e")
        self.notice_base = "DUMMY DATA - test mode" if DUMMY_MODE else ""
        self.notice_label = tk.Label(right, text=self.notice_base,
                                     font=(FONT, 8), fg="#E0B15A",
                                     bg=HEADER_BG)
        self.notice_label.pack(anchor="e")

    def build_cards(self):
        row = tk.Frame(self.root, bg=BG)
        row.pack(fill="x", padx=16, pady=(14, 6))

        titles = [("cpu", "CPU Usage"), ("temp", "Temperature"),
                  ("physical", "Physical Cores"), ("logical", "Logical Cores"),
                  ("processes", "Processes"), ("threads", "Threads")]
        self.card_values = {}
        self.card_notes = {}

        for column, (key, title) in enumerate(titles):
            card, value, note = make_card(row, title)
            card.grid(row=0, column=column, sticky="nsew", padx=5)
            row.columnconfigure(column, weight=1, uniform="cards")
            self.card_values[key] = value
            self.card_notes[key] = note

    def build_body(self):
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=16, pady=6)
        body.columnconfigure(0, weight=2, uniform="body")
        body.columnconfigure(1, weight=3, uniform="body")
        body.rowconfigure(0, weight=1)

        # Left: per-core utilization
        core_panel, self.core_frame = make_panel(body, "Per-core utilization")
        core_panel.grid(row=0, column=0, sticky="nsew", padx=5)
        self.core_frame.columnconfigure(1, weight=1)
        tk.Label(self.core_frame, text="Start monitoring to see core usage.",
                 font=(FONT, 10), fg=MUTED, bg=CARD_BG).grid(row=0, column=0,
                                                           columnspan=3)

        # Right: CEI, analysis, recommendations
        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew", padx=5)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)

        # CEI
        cei_panel, cei = make_panel(right, "Core Efficiency Index")
        cei_panel.grid(row=0, column=0, sticky="ew")
        self.cei_label = tk.Label(cei, text="CEI: -- / 100",
                                  font=(FONT, 20, "bold"), fg=TEXT,
                                  bg=CARD_BG)
        self.cei_label.pack(anchor="w")
        self.cei_bar = ttk.Progressbar(cei, maximum=100, length=300,
                                       style="CEI.Horizontal.TProgressbar")
        self.cei_bar.pack(fill="x", pady=6)
        self.cei_status = tk.Label(cei, text="Status: Awaiting CEI thresholds",
                                   font=(FONT, 10), fg=MUTED, bg=CARD_BG)
        self.cei_status.pack(anchor="w")

        # Analysis
        analysis_panel, analysis = make_panel(right, "Analysis")
        analysis_panel.grid(row=1, column=0, sticky="ew", pady=8)
        analysis.columnconfigure(1, weight=1)
        self.analysis_values = {}
        items = [("Core Balance", "Core Balance"),
                 ("Active Cores", "Active Cores"),
                 ("Idle Cores", "Idle Cores"),
                 ("Average Threads per Process", "Avg Threads / Process"),
                 ("Context Switch Increase", "Context Switch Increase")]
        for r, (key, title) in enumerate(items):
            tk.Label(analysis, text=title, font=(FONT, 10), fg=MUTED,
                     bg=CARD_BG).grid(row=r, column=0, sticky="w", pady=1)
            value = tk.Label(analysis, text="--", font=(FONT, 10, "bold"),
                             fg=TEXT, bg=CARD_BG)
            value.grid(row=r, column=1, sticky="e", pady=1)
            self.analysis_values[key] = value

        # Recommendations
        rec_panel, rec = make_panel(right, "Recommendations")
        rec_panel.grid(row=2, column=0, sticky="nsew")
        self.rec_text = tk.Text(rec, height=6, wrap="word", font=(FONT, 10),
                                bg=CARD_BG, fg=TEXT, relief="flat",
                                state="disabled", cursor="arrow")
        self.rec_text.pack(fill="both", expand=True)
        set_text(self.rec_text, ["No analysis yet."])

    def build_buttons(self):
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(side="bottom", fill="x", padx=16, pady=(6, 16))

        self.start_button = ttk.Button(bar, text="Start Monitoring",
                                       style="Start.TButton",
                                       command=self.start_monitoring)
        self.start_button.pack(side="left", padx=5)
        self.stop_button = ttk.Button(bar, text="Stop Monitoring",
                                      style="Corvo.TButton", state="disabled",
                                      command=self.stop_monitoring)
        self.stop_button.pack(side="left", padx=5)

        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y",
                                                    padx=12)

        graph_buttons = [
            ("CPU Graph", self.show_cpu_graph),
            ("Core Graph", self.show_core_graph),
            ("Temperature Graph", self.show_temperature_graph),
            ("Context Switches", self.show_switch_graph),
            ("View Analysis", self.view_analysis),
        ]
        for text, command in graph_buttons:
            ttk.Button(bar, text=text, style="Corvo.TButton",
                       command=command).pack(side="left", padx=4)

        self.benchmark_button = ttk.Button(bar, text="Run Benchmark",
                                           style="Corvo.TButton",
                                           command=self.start_benchmark)
        self.benchmark_button.pack(side="left", padx=4)

    # ----- start / stop ------------------------------------------
    def start_monitoring(self):
        if self.monitoring or self.stopping:
            return
        while not self.data_queue.empty():        # forget old readings
            self.data_queue.get_nowait()

        self.monitoring = True
        self.worker = MonitorWorker(self.data_queue)
        self.worker.start()

        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.status_label.config(text="\u25CF  Monitoring", fg="#7FD18B")
        self.check_queue()

    def stop_monitoring(self):
        if not self.monitoring:
            return
        self.monitoring = False
        self.stopping = True
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self.worker.stop()

        self.stop_button.config(state="disabled")
        self.status_label.config(text="\u25CF  Stopping...", fg="#E0B15A")
        self.wait_for_worker()

    def wait_for_worker(self):
        """The worker may still be finishing its current reading (~2 s).
        Check again every 200 ms; enable Start only when it has ended."""
        if self.worker is not None and self.worker.is_running():
            self.root.after(200, self.wait_for_worker)
            return
        self.stopping = False
        self.start_button.config(state="normal")
        self.status_label.config(text="\u25CF  Stopped", fg="#B8C2CE")

    def check_queue(self):
        """Runs every QUEUE_CHECK_MS while monitoring is on.

        Takes every reading waiting in the queue and shows it.
        root.after() schedules the next check, so the window never freezes.
        """
        if not self.monitoring:
            return
        try:
            while True:
                kind, content = self.data_queue.get_nowait()
                if kind == "data":
                    self.handle_new_data(content)
                else:
                    raise RuntimeError(content)
        except queue.Empty:
            pass                                  # nothing new right now
        except Exception as error:
            self.stop_monitoring()
            messagebox.showerror("CORVO", "Monitoring stopped:\n" + str(error))
            return
        self.after_id = self.root.after(QUEUE_CHECK_MS, self.check_queue)

    # ----- handling one new reading ------------------------------
    def handle_new_data(self, data):
        self.latest = data

        self.times.append(data["Time"])
        self.cpu_history.append(data["CPU Usage"])
        self.temp_history.append(data["Temperature"])      # may be None
        self.switch_history.append(data["Context Switch Increase"])
        for history in (self.times, self.cpu_history, self.temp_history,
                        self.switch_history):
            del history[:-HISTORY_LIMIT]                   # keep the newest only

        self.update_display(data)
        for refresh in list(self.graph_refreshers):        # open graphs
            refresh()

    def update_display(self, data):
        # Cards
        self.card_values["cpu"].config(text=f"{data['CPU Usage']:.1f} %")
        self.card_values["physical"].config(text=str(data["Physical Cores"]))
        self.card_values["logical"].config(text=str(data["Logical Cores"]))
        self.card_values["processes"].config(text=str(data["Processes"]))
        self.card_values["threads"].config(text=str(data["Threads"]))

        temperature = data["Temperature"]
        if temperature is None:
            self.card_values["temp"].config(text="N/A")
            self.card_notes["temp"].config(text="Unavailable on this system")
        else:
            self.card_values["temp"].config(text=f"{temperature:.1f} \u00B0C")
            self.card_notes["temp"].config(text="")

        # Per-core bars
        self.update_core_rows(data["Core Usage"])

        # CEI (shown exactly as calculated by the analyzer)
        cei = data["CEI"]
        self.cei_label.config(text=f"CEI: {cei:.2f} / 100")
        self.cei_bar["value"] = cei
        self.cei_status.config(text="Status: Awaiting CEI thresholds")

        # Analysis numbers
        self.analysis_values["Core Balance"].config(
            text=f"{data['Core Balance']:.2f}")
        self.analysis_values["Active Cores"].config(
            text=str(data["Active Cores"]))
        self.analysis_values["Idle Cores"].config(text=str(data["Idle Cores"]))
        self.analysis_values["Average Threads per Process"].config(
            text=f"{data['Average Threads per Process']:.2f}")
        self.analysis_values["Context Switch Increase"].config(
            text=f"{data['Context Switch Increase']:,}")

        # Recommendations
        set_text(self.rec_text, data["Recommendations"])

        # Warning (for example: CSV could not be saved)
        save_error = data.get("Save Error")
        self.notice_label.config(text=save_error if save_error
                                 else self.notice_base)

    def update_core_rows(self, core_usage):
        """One row per core: name, progress bar, percentage."""
        if len(self.core_rows) != len(core_usage):       # (re)build rows
            for widget in self.core_frame.winfo_children():
                widget.destroy()
            self.core_rows = []
            for i in range(len(core_usage)):
                tk.Label(self.core_frame, text=f"Core {i + 1}",
                         font=(FONT, 10), fg=TEXT, bg=CARD_BG,
                         width=7, anchor="w").grid(row=i, column=0, pady=5)
                bar = ttk.Progressbar(self.core_frame, maximum=100,
                                      style="Core.Horizontal.TProgressbar")
                bar.grid(row=i, column=1, sticky="ew", padx=8)
                value = tk.Label(self.core_frame, text="", font=(FONT, 10, "bold"),
                                 fg=TEXT, bg=CARD_BG, width=7, anchor="e")
                value.grid(row=i, column=2)
                self.core_rows.append((bar, value))

        for (bar, value), usage in zip(self.core_rows, core_usage):
            bar["value"] = usage
            value.config(text=f"{usage:.1f} %")

    # ----- graph windows -----------------------------------------
    def open_graph(self, title, draw):
        """Open a window with a Matplotlib figure inside Tkinter.

        draw(ax) is a function from visualizer.py that draws on the axes.
        While the window is open it is redrawn after every new reading.
        """
        window = tk.Toplevel(self.root)
        window.title("CORVO - " + title)
        window.geometry("780x470")

        figure = Figure(figsize=(7.4, 4.2), dpi=100)
        ax = figure.add_subplot(111)
        canvas = FigureCanvasTkAgg(figure, master=window)
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)

        def refresh():
            draw(ax)
            figure.tight_layout()
            canvas.draw()

        def close_window():
            if refresh in self.graph_refreshers:
                self.graph_refreshers.remove(refresh)
            window.destroy()

        self.graph_refreshers.append(refresh)
        window.protocol("WM_DELETE_WINDOW", close_window)
        refresh()

    def show_cpu_graph(self):
        self.open_graph("CPU Usage", lambda ax: visualizer.plot_cpu_usage(
            ax, self.times, self.cpu_history))

    def show_core_graph(self):
        self.open_graph("Core Utilization", lambda ax: visualizer.plot_core_usage(
            ax, self.latest["Core Usage"] if self.latest else []))

    def show_temperature_graph(self):
        self.open_graph("Temperature", lambda ax: visualizer.plot_temperature(
            ax, self.times, self.temp_history))

    def show_switch_graph(self):
        self.open_graph("Context Switches", lambda ax: visualizer.plot_context_switches(
            ax, self.times, self.switch_history))

    # ----- benchmark (workload.py) -------------------------------
    def start_benchmark(self):
        """Run workload.run_benchmark() in its own thread (it takes a while)."""
        if self.benchmark_running:
            return
        self.benchmark_running = True
        self.benchmark_button.config(state="disabled")
        self.notice_label.config(text="Benchmark running... please wait")

        thread = threading.Thread(target=self.benchmark_thread, daemon=True)
        thread.start()
        self.check_benchmark()

    def benchmark_thread(self):
        """Runs in the background thread; only talks to the GUI via a queue."""
        try:
            results = workload.run_benchmark()
        except Exception as error:
            self.benchmark_queue.put(("error", str(error)))
            return
        self.benchmark_queue.put(("done", results))

    def check_benchmark(self):
        """Look for the benchmark result every 300 ms."""
        try:
            kind, content = self.benchmark_queue.get_nowait()
        except queue.Empty:
            self.root.after(300, self.check_benchmark)
            return

        self.benchmark_running = False
        self.benchmark_button.config(state="normal")
        self.notice_label.config(text=self.notice_base)

        if kind == "error":
            messagebox.showerror("CORVO", "Benchmark failed:\n" + content)
            return
        self.benchmark_results = content
        self.show_benchmark_graph()

    def show_benchmark_graph(self):
        self.open_graph("Benchmark", lambda ax: visualizer.plot_benchmark(
            ax, self.benchmark_results))

    # ----- View Analysis -----------------------------------------
    def view_analysis(self):
        lines = []

        if self.latest is not None:
            data = self.latest
            lines += [
                "THIS SESSION",
                f"Samples collected: {len(self.cpu_history)}",
                f"Average CPU usage: {sum(self.cpu_history) / len(self.cpu_history):.1f} %",
                f"Highest CPU usage: {max(self.cpu_history):.1f} %",
                f"Lowest CPU usage: {min(self.cpu_history):.1f} %",
                "",
                f"Latest CEI: {data['CEI']:.2f} / 100",
                f"Core balance: {data['Core Balance']:.2f}",
                f"Active / idle cores: {data['Active Cores']} / {data['Idle Cores']}",
                "",
                "Recommendations:",
            ]
            lines += ["  - " + r for r in data["Recommendations"]]
            lines.append("")

        lines += saved_data_lines()

        if self.benchmark_results:
            lines += ["", "BENCHMARK (matrix multiplication)"]
            for row in self.benchmark_results:
                lines.append(
                    f"   {row['Workers']} worker(s): {row['Time']:.2f} s, "
                    f"speedup {row['Speedup']:.2f}x, "
                    f"parallel efficiency {row['Parallel Efficiency']:.1f} %")

        window = tk.Toplevel(self.root)
        window.title("CORVO - Analysis Summary")
        window.geometry("600x640")
        scrollbar = ttk.Scrollbar(window, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        text = tk.Text(window, wrap="word", font=(FONT, 10), padx=14, pady=14,
                       yscrollcommand=scrollbar.set)
        text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=text.yview)
        text.insert("end", "\n".join(lines))
        text.config(state="disabled")

    # ----- closing -----------------------------------------------
    def close_app(self):
        self.monitoring = False
        if self.worker is not None:
            self.worker.stop()       # thread is a daemon, so it cannot block exit
        self.root.destroy()