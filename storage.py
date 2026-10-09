import csv
import os


def save_cpu_data(data):
    file_path = "data/cpu_data.csv"

    os.makedirs("data", exist_ok=True)

    file_exists = os.path.isfile(file_path)

    with open(file_path, "a", newline="") as file:
        writer = csv.writer(file)

        if not file_exists:
            writer.writerow([
                "Time",
                "CPU Usage",
                "Core Usage",
                "Context Switches",
                "Processes",
                "Threads",
                "Temperature"
            ])

        writer.writerow(data)