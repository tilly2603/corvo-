"""
main.py  -  CORVO Multi-core Processor Analyser

Start the program with:   python main.py

All project files must be in the same folder:
    monitor.py, storage.py, analyzer.py, workload.py, visualizer.py, gui.py, main.py
"""

import os
import tkinter as tk

# data/cpu_data.csv is a relative path, so always work from this folder
os.chdir(os.path.dirname(os.path.abspath(__file__)))

def main():
    # gui is imported here (not at the top) so that the benchmark's worker
    # processes, which re-import this file, do not load the whole GUI.
    try:
        from gui import CorvoApp
    except ImportError as error:
        print("CORVO could not start because a module is missing:")
        print("   ", error)
        print("Install the libraries with:  pip install -r requirements.txt")
        print("and make sure monitor.py, storage.py, analyzer.py, workload.py "
              "and visualizer.py are in the same folder as main.py.")
        raise SystemExit(1)

    root = tk.Tk()
    CorvoApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()