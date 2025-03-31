import time
import enum
import json
import os
import datetime
import random

#---------------------------
# 1. State Definitions
#---------------------------
class ADCSState(enum.Enum):
    DETUMBLING = 1
    SUN_ACQUISITION = 2
    NOMINAL_POINTING = 3
    SAFE_MODE = 4

#---------------------------
# 2. Global Constants and Files
#---------------------------
STATE_FILE = 'adcs_state.json'
LOG_FILE = 'adcs_log.txt'
CONTROL_LOOP_INTERVAL = 5  # seconds per control cycle

# Fault thresholds
ANGULAR_RATE_THRESHOLD = 5.0      # Degrees per second threshold for detumbling
SUN_ALIGNMENT_THRESHOLD = 5.0     # Acceptable sun alignment error (degrees)
SAFE_POWER_THRESHOLD = 19         # Critical power threshold (%)

# Persistence counters for fault conditions
HIGH_RATE_PERSISTENCE_COUNT = 3   # Consecutive cycles with high angular rate
SENSOR_FAIL_PERSISTENCE_COUNT = 3 # Consecutive sensor failures

# Global counters (persist across cycles)
high_rate_counter = 0
sensor_fail_counter = 0

#---------------------------
# 3. Logging Function (Error Handling)
#---------------------------
def log_event(message):
    timestamp = datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] {message}\n")
    print(message)

#---------------------------
# 4. Simulated Sensor & System Functions
#---------------------------
def get_angular_rate():
    """Return simulated angular rate (deg/s) with noise."""
    return random.uniform(0, 10)

def get_sun_vector():
    """Return simulated sun alignment error (degrees)."""
    return random.uniform(0, 30)

def get_quaternion_error():
    """Return simulated orientation error for nominal pointing (degrees)."""
    return random.uniform(0, 5)

def check_power():
    """Simulate power level monitoring; log power level and return True if above threshold."""
    power_level = random.uniform(10, 100)
    log_event(f"Power level: {power_level:.1f}%")
    return power_level > SAFE_POWER_THRESHOLD

def check_sensors():
    """Simulate sensor health check with 10% failure probability."""
    failure_probability = 0.1
    return random.random() > failure_probability

def in_eclipse():
    """Simulate eclipse detection (assume 40% chance of being in eclipse)."""
    return random.random() < 0.4

#---------------------------
# 5. ADCS Operation Functions
#---------------------------
def detumbling_control():
    """Detumbling: reduce angular rate using magnetorquers (Bang-Bang control)."""
    angular_rate = get_angular_rate()
    if angular_rate > ANGULAR_RATE_THRESHOLD:
        torque = -0.1 if angular_rate > 0 else 0.1
        log_event(f"[DETUMBLING] Angular rate: {angular_rate:.2f}°/s, applying torque: {torque:.3f} Nm")
    else:
        log_event("[DETUMBLING] Angular rate within safe limits; ready to transition.")

def sun_acquisition():
    """Sun Acquisition: align solar panels via proportional control."""
    sun_error = get_sun_vector()
    if sun_error > SUN_ALIGNMENT_THRESHOLD:
        control_torque = -0.05 * sun_error
        log_event(f"[SUN_ACQUISITION] Sun error: {sun_error:.2f}°, applying control torque: {control_torque:.3f} Nm")
    else:
        log_event("[SUN_ACQUISITION] Sun alignment achieved; ready to transition to NOMINAL POINTING.")

def nominal_pointing():
    """Nominal Pointing: maintain desired attitude using PD control (reaction wheels)."""
    error = get_quaternion_error()
    if error > 0.5:
        reaction_wheel_torque = -0.1 * error
        log_event(f"[NOMINAL_POINTING] Orientation error: {error:.2f}°, applying reaction wheel torque: {reaction_wheel_torque:.3f} Nm")
    else:
        log_event("[NOMINAL_POINTING] Attitude stable and within tolerance.")

def safe_mode():
    """Safe Mode: minimal operations to conserve power and protect system."""
    log_event("[SAFE_MODE] Entering safe mode. Minimizing actuator usage and conserving power.")

#---------------------------
# 6. Persistence Functions for Recovery
#---------------------------
def save_state(state):
    """Persist the current state to non-volatile memory."""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump({'state': state.name}, f)
    except IOError as e:
        log_event(f"Error saving state: {e}")

def load_state():
    """Load the last known state from non-volatile memory; default to DETUMBLING if not available."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                data = json.load(f)
                return ADCSState[data['state']]
        except (IOError, KeyError, json.JSONDecodeError) as e:
            log_event(f"Error loading state: {e}")
    log_event("No valid saved state found, defaulting to DETUMBLING.")
    return ADCSState.DETUMBLING

#---------------------------
# 7. State Transition Logic
#---------------------------
def state_transition(current_state):
    """Determine the next state based on all cases and persistent fault conditions."""
    global high_rate_counter, sensor_fail_counter

    # Obtain current sensor/system measurements
    angular_rate = get_angular_rate()
    sun_error = get_sun_vector()
    power_ok = check_power()
    eclipse = in_eclipse()

    # -------------------------------
    # Case 1: Sensor Anomalies
    # -------------------------------
    sensor_ok = False
    for _ in range(3):
        if check_sensors():
            sensor_ok = True
            break
        time.sleep(0.5)
    if not sensor_ok:
        sensor_fail_counter += 1
        log_event(f"Sensor check failed ({sensor_fail_counter} consecutive failures).")
    else:
        sensor_fail_counter = 0
    if sensor_fail_counter >= SENSOR_FAIL_PERSISTENCE_COUNT:
        log_event("Persistent sensor anomalies detected. Transitioning to SAFE_MODE.")
        return ADCSState.SAFE_MODE

    # -------------------------------
    # Case 2: High Angular Rate
    # -------------------------------
    if angular_rate > ANGULAR_RATE_THRESHOLD:
        high_rate_counter += 1
        log_event(f"High angular rate detected ({high_rate_counter} consecutive cycles).")
    else:
        high_rate_counter = 0
    if high_rate_counter >= HIGH_RATE_PERSISTENCE_COUNT:
        log_event("Angular rate remains high persistently. Transitioning to DETUMBLING.")
        return ADCSState.DETUMBLING

    # -------------------------------
    # Case 3: Low Power Handling
    # -------------------------------
    if not power_ok and eclipse:
        log_event("Critical fault: Low power during eclipse. Transitioning to SAFE_MODE.")
        return ADCSState.SAFE_MODE

    # -------------------------------
    # Case 4: Nominal Operations
    # -------------------------------
    # If sun alignment error is within acceptable limits, transition to NOMINAL_POINTING.
    if sun_error < SUN_ALIGNMENT_THRESHOLD:
        log_event("Sun alignment is acceptable. Transitioning to NOMINAL_POINTING.")
        return ADCSState.NOMINAL_POINTING
    else:
        log_event("Sun alignment not achieved. Remaining in SUN_ACQUISITION.")
        return ADCSState.SUN_ACQUISITION

#---------------------------
# 8. Main Loop (Event-Driven FSM)
#---------------------------
def main():
    current_state = load_state()  # Load persistent state (processor reset recovery)
    log_event(f"System starting in state: {current_state.name}")

    while True:
        # Execute the operation corresponding to the current state
        if current_state == ADCSState.DETUMBLING:
            detumbling_control()
        elif current_state == ADCSState.SUN_ACQUISITION:
            sun_acquisition()
        elif current_state == ADCSState.NOMINAL_POINTING:
            nominal_pointing()
        elif current_state == ADCSState.SAFE_MODE:
            safe_mode()
        
        # Persist current state for recovery
        save_state(current_state)
        
        # Determine next state based on persistent fault checks and system conditions
        next_state = state_transition(current_state)
        if next_state != current_state:
            log_event(f"Transitioning from {current_state.name} to {next_state.name}")
            current_state = next_state
        
        # Wait for the next control loop iteration
        time.sleep(CONTROL_LOOP_INTERVAL)

if __name__ == "__main__":
    main()
