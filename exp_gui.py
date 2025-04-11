import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from ttkbootstrap import Style
from ttkbootstrap.constants import *
from ttkbootstrap.widgets import Button
import subprocess
import threading
import os
import json
import signal

CONFIG_FILE = "experiment_config.json"
process = None  # Track running experiment process

paths = {
    "bash_script": "",
    "unity_exe": "",
    "fictrac_exe": "",
    "fictrac_config": "",
    "calc_path_py": "",
    "con_led_py": "",
    "working_dir": "",
    "csv_main_dir": "",
    "baseline_time": "300",
    "training_time": "300",
    "iterations": "30",
    "inter_session_time": "60"
}

# Setup dark style
style = Style("darkly")
root = style.master
root.title("Foraging Experiment GUI")
entry_vars = {}

def browse_path(key, is_dir=False):
    path = (
        filedialog.askdirectory(title=f"Select {key.replace('_', ' ').title()}")
        if is_dir else
        filedialog.askopenfilename(title=f"Select {key.replace('_', ' ').title()}")
    )
    if path:
        paths[key] = path
        entry_vars[key].set(path)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            saved = json.load(f)
            for key in paths:
                paths[key] = saved.get(key, paths[key])
                if key in entry_vars:
                    entry_vars[key].set(paths[key])
        baseline_time_var.set(saved.get("baseline_time", "300"))
        training_time_var.set(saved.get("training_time", "300"))
        iterations_var.set(saved.get("iterations", "30"))
        inter_time_var.set(saved.get("inter_session_time", "60"))

def save_config():
    for key in entry_vars:
        paths[key] = entry_vars[key].get()
    paths["baseline_time"] = baseline_time_var.get()
    paths["training_time"] = training_time_var.get()
    paths["iterations"] = iterations_var.get()
    paths["inter_session_time"] = inter_time_var.get()
    with open(CONFIG_FILE, "w") as f:
        json.dump(paths, f, indent=2)
    messagebox.showinfo("Saved", "Default paths saved!")

# File path inputs
file_fields = [
    ("Bash Script", "bash_script", False),
    ("Unity Executable", "unity_exe", False),
    ("FicTrac Executable", "fictrac_exe", False),
    ("FicTrac Config", "fictrac_config", False),
    ("calc_path.py", "calc_path_py", False),
    ("con_led0.py", "con_led_py", False),
    ("Working Directory", "working_dir", True),
    ("CSV Main Directory", "csv_main_dir", True),
]

row = 0
for label, key, is_dir in file_fields:
    tk.Label(root, text=f"{label}:", font=("Segoe UI", 10)).grid(row=row, column=0, sticky="e", padx=5, pady=2)
    var = tk.StringVar()
    entry_vars[key] = var
    tk.Entry(root, textvariable=var, width=60, font=("Segoe UI", 10)).grid(row=row, column=1, padx=5, pady=2)
    Button(root, text="Browse", command=lambda k=key, d=is_dir: browse_path(k, d)).grid(row=row, column=2, padx=5)
    row += 1

# Time/iteration parameters
def add_param(label, var, default):
    global row
    tk.Label(root, text=label, font=("Segoe UI", 10)).grid(row=row, column=0, sticky="e", padx=5, pady=2)
    var.set(default)
    tk.Entry(root, textvariable=var, font=("Segoe UI", 10)).grid(row=row, column=1, padx=5)
    row += 1

baseline_time_var = tk.StringVar()
training_time_var = tk.StringVar()
iterations_var = tk.StringVar()
inter_time_var = tk.StringVar()

add_param("Baseline Session Time (s):", baseline_time_var, "300")
add_param("Training Session Time (s):", training_time_var, "300")
add_param("Iterations:", iterations_var, "30")
add_param("Inter-session Time (s):", inter_time_var, "60")

# Buttons
start_button = Button(root, text="Start Experiment", bootstyle=SUCCESS)
stop_button = Button(root, text="Stop Experiment", bootstyle=DANGER)
save_button = Button(root, text="Save as Default", command=save_config, bootstyle=INFO)

start_button.grid(row=row, column=0, pady=10)
save_button.grid(row=row, column=1, pady=10)
stop_button.grid(row=row, column=2, pady=10)
row += 1

# Log output
log_output = scrolledtext.ScrolledText(root, width=100, height=25, font=("Consolas", 10))
log_output.grid(row=row, column=0, columnspan=3, padx=10, pady=10)

def run_experiment():
    global process
    baseline_time = baseline_time_var.get()
    training_time = training_time_var.get()
    iterations = iterations_var.get()
    inter_session_time = inter_time_var.get()

    if not os.path.isfile(paths["bash_script"]):
        messagebox.showerror("Error", f"Bash script not found: {paths['bash_script']}")
        return

    env = os.environ.copy()
    env.update({
        "UNITY_EXE": paths["unity_exe"],
        "FICTRAC_EXE": paths["fictrac_exe"],
        "FICTRAC_CONFIG": paths["fictrac_config"],
        "CALC_PATH": paths["calc_path_py"],
        "CON_LED": paths["con_led_py"],
        "WORKING_DIR": paths["working_dir"],
        "CSV_MAIN_DIR": paths["csv_main_dir"]
    })

    command = [
        "bash", paths["bash_script"],
        "--baseline-session-time", baseline_time,
        "--training-session-time", training_time,
        "--iterations", iterations,
        "--inter-session-time", inter_session_time
    ]

    start_button.config(state="disabled")
    stop_button.config(state="normal")
    log_output.delete(1.0, tk.END)
    log_output.insert(tk.END, "Starting experiment...\n")

    def target():
        global process
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            preexec_fn=os.setsid  # Allows killing the whole process group
        )
        for line in process.stdout:
            log_output.insert(tk.END, line)
            log_output.see(tk.END)
        process.wait()
        log_output.insert(tk.END, "\nExperiment finished.\n")
        start_button.config(state="normal")
        stop_button.config(state="disabled")

    threading.Thread(target=target, daemon=True).start()

def stop_experiment():
    global process
    if process and process.poll() is None:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        log_output.insert(tk.END, "\nExperiment stopped by user.\n")
        start_button.config(state="normal")
        stop_button.config(state="disabled")

start_button.config(command=run_experiment)
stop_button.config(command=stop_experiment)
stop_button.config(state="disabled")

load_config()
root.mainloop()

