#!/bin/bash

# Default values for parameters
INTER_SESSION_TIME=10
ITERATIONS=15
BASELINE_SESSION_TIME=300
TRAINING_SESSION_TIME=300

# Timestamp for log files
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DATE=$(date)

# Environment override-able paths
UNITY_EXE="${UNITY_EXE:-/home/kazama/Unity_Builds/turning_foraging/turning_foraging.x86_64}"
FICTRAC_EXE="${FICTRAC_EXE:-/home/kazama/fictrac/bin/fictrac}"
FICTRAC_CONFIG="${FICTRAC_CONFIG:-/home/kazama/fictrac/fictrac_config/config.txt}"
calc_path_exe="${CALC_PATH:-/home/kazama/Experiment_builds/turning_foraging/calc_path_closed_end.py}"
con_led_exe="${CON_LED:-/home/kazama/Experiment_builds/turning_foraging/con_led.py}"
WORKING_MAIN_DIR="${WORKING_DIR:-/home/kazama/Experiment_log/foraging}"
RAW_CSV_MAIN_DIR="${CSV_MAIN_DIR:-/home/kazama/Raw_data/foraging}"
FICTRAC_WORKING_MAIN_DIR="${FICTRAC_WORKING_DIR:-/home/kazama/fictrac/foraging}"

# Subdirectories
LOG_DIR="$WORKING_DIR/logs"
BASELINE_CSV_DIR="$RAW_CSV_MAIN_DIR/${TIMESTAMP}/baseline"
EXPERIMENT_CSV_DIR="$RAW_CSV_MAIN_DIR/${TIMESTAMP}/training"
FICTRAC_WORKING_DIR="$FICTRAC_WORKING_MAIN_DIR/{Timestamp}"
WORKING_DIR="$WORKING_MAIN_DIR/{Timestamp}"
mkdir -p "$LOG_DIR" "$WORKING_DIR" "$RAW_CSV_MAIN_DIR" "$BASELINE_CSV_DIR" "$EXPERIMENT_CSV_DIR" "$FICTRAC_WORKING_DIR"

# Log file paths
SCRIPT_LOG="$LOG_DIR/run_experiment_${TIMESTAMP}.log"
CALC_PATH_LOG="$LOG_DIR/calc_path_${TIMESTAMP}.log"
CON_LED_LOG="$LOG_DIR/con_led_${TIMESTAMP}.log"
FICTRAC_LOG="$LOG_DIR/fictrac_${TIMESTAMP}.log"
UNITY_BASELINE_LOG="$LOG_DIR/unity_baseline_${TIMESTAMP}.log"
UNITY_EXPERIMENT_LOG="$LOG_DIR/unity_training_${TIMESTAMP}.log"

# Track background process IDs
PIDS=()

cleanup() {
    echo "Terminating all running processes..." | tee -a "$SCRIPT_LOG"
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            echo "Killing process with PID $pid" | tee -a "$SCRIPT_LOG"
            kill -9 "$pid" 2>/dev/null
        fi
    done
    echo "All processes terminated." | tee -a "$SCRIPT_LOG"
}
trap cleanup EXIT

# Parse command-line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --inter-session-time) INTER_SESSION_TIME="$2"; shift ;;
        --iterations) ITERATIONS="$2"; shift ;;
        --baseline-session-time) BASELINE_SESSION_TIME="$2"; shift ;;
        --training-session-time) TRAINING_SESSION_TIME="$2"; shift ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

activate_conda() {
    echo "Activating conda environment 'daqcon'..." | tee -a "$SCRIPT_LOG"
    source ~/miniconda3/bin/activate daqcon || {
        echo "Error: Failed to activate Conda environment 'daqcon'" | tee -a "$SCRIPT_LOG"
        exit 1
    }
}

# Modified run_python_scripts: accepts additional parameters for con_led.py via "$@"
run_python_scripts() {
    echo "Running calc_path.py..." | tee -a "$SCRIPT_LOG"
    python3 "$calc_path_exe" >> "$CALC_PATH_LOG" 2>&1 &
    PIDS+=($!)
    echo "Running con_led.py with arguments: $*" | tee -a "$SCRIPT_LOG"
    python3 "$con_led_exe" "$@" >> "$CON_LED_LOG" 2>&1 &
    PIDS+=($!)
}

run_executables() {
    local unity_exe=$1
    local unity_log=$2
    local csv_dir=$3

    echo "Changing directory to $FICTRAC_WORKING_DIR" | tee -a "$SCRIPT_LOG"
    cd "$FICTRAC_WORKING_DIR" || { echo "Directory $FICTRAC_WORKING_DIR not found" | tee -a "$SCRIPT_LOG"; exit 1; }

    echo "Running fictrac..." | tee -a "$SCRIPT_LOG"
    "$FICTRAC_EXE" "$FICTRAC_CONFIG" >> "$FICTRAC_LOG" 2>&1 &
    PIDS+=($!)

    echo "Switching back to $WORKING_DIR" | tee -a "$SCRIPT_LOG"
    cd "$WORKING_DIR" || { echo "Directory $WORKING_DIR not found" | tee -a "$SCRIPT_LOG"; exit 1; }

    echo "Running Unity executable: $unity_exe with --csvDirectory $csv_dir" | tee -a "$SCRIPT_LOG"
    "$unity_exe" --csvDirectory "$csv_dir" >> "$unity_log" 2>&1 &
    PIDS+=($!)
}

countdown() {
    local duration=$1
    local start_time=$(date +%s)

    while [ $duration -gt 0 ]; do
        local now=$(date +%s)
        local remaining=$((start_time + duration - now))
        if [ $remaining -le 0 ]; then
            break
        fi
        echo -ne "\r⏳ Time remaining: ${remaining}s "
        sleep 1
    done
    echo -e "\r✅ Countdown finished.         "
}

stop_processes() {
    echo "Stopping all running processes..." | tee -a "$SCRIPT_LOG"
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            echo "Stopping process with PID $pid" | tee -a "$SCRIPT_LOG"
            kill -9 "$pid" 2>/dev/null
        fi
    done
    PIDS=()
}

# ----------------- BASELINE SESSION -----------------
activate_conda
# Run con_led.py without extra parameters (baseline session)
run_python_scripts
run_executables "$UNITY_EXE" "$UNITY_BASELINE_LOG" "$BASELINE_CSV_DIR"
echo "Baseline session running for $BASELINE_SESSION_TIME seconds..." | tee -a "$SCRIPT_LOG"
countdown "$BASELINE_SESSION_TIME"
stop_processes

echo "Waiting for $INTER_SESSION_TIME seconds before next session..." | tee -a "$SCRIPT_LOG"
countdown "$INTER_SESSION_TIME"

# ----------------- TRAINING/EXPERIMENT ITERATIONS -----------------
for ((i=1; i<=ITERATIONS; i++)); do
    echo "Starting iteration $i of $ITERATIONS: Training Session" | tee -a "$SCRIPT_LOG"
    activate_conda
    # Run con_led.py with the --zones parameter for training session
    run_python_scripts --zones "0:0.02,1:0.01"
    run_executables "$UNITY_EXE" "$UNITY_EXPERIMENT_LOG" "$EXPERIMENT_CSV_DIR"
    echo "Training session running for $TRAINING_SESSION_TIME seconds..." | tee -a "$SCRIPT_LOG"
    countdown "$TRAINING_SESSION_TIME"
    stop_processes

    echo "Waiting for $INTER_SESSION_TIME seconds before Probing Session..." | tee -a "$SCRIPT_LOG"
    countdown "$INTER_SESSION_TIME"
done

echo "All iterations completed." | tee -a "$SCRIPT_LOG"
cleanup

