import time
import enum
import json
import os
import datetime
import random  # Simulated sensor data

# Enumerate ADCS States
class ADCSState(enum.Enum):
    DETUMBLING = 1
    SUN_ACQUISITION = 2
    NOMINAL_POINTING = 3
    SAFE_MODE = 4

# Define thresholds and control parameters (tuned based on IotaSat constraints)
ANGULAR_RATE_THRESHOLD = 5.0      # Degrees per second (beyond which detumbling is needed)
SUN_ALIGNMENT_THRESHOLD = 5.0     # Maximum acceptable sun misalignment (degrees)
CONTROL_LOOP_INTERVAL = 1         # seconds between control loop iterations
MAGNETORQUER_MAX = 0.1            # Maximum torque available from magnetorquers (Nm)
REACTION_WHEEL_MAX = 0.2          # Maximum torque available from reaction wheels (Nm)
SAFE_POWER_THRESHOLD = 20         # Example power level threshold (in %)

STATE_FILE = 'adcs_state.json'
LOG_FILE = 'adcs_log.txt'

# State Transition Logging for diagnostics (inspired by historical docking challenges)
def log_event(event):
    """Log important events for debugging and analysis."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] {event}\n")
    print(event)  # Also output to console

# Simulated Sensor & Power Functions (with randomness to mimic noise and possible faults)
def get_angular_rate():
    """Simulate angular velocity measurement (deg/sec) with noise."""
    return random.uniform(0, 10)

def get_sun_vector():
    """Simulate sun sensor readings: angular error from sun direction."""
    return random.uniform(0, 30)

def get_quaternion_error():
    """Simulate orientation error in nominal pointing mode."""
    return random.uniform(0, 5)

def check_power():
    """Simulate power level monitoring."""
    power_level = random.uniform(10, 100)  # Simulated power percentage
    log_event(f"Power level: {power_level:.1f}%")
    return power_level > SAFE_POWER_THRESHOLD

def check_sensors():
    """Simulate sensor health check with a chance of transient failure."""
    failure_probability = 0.1  # 10% chance a sensor read fails transiently
    return random.random() > failure_probability

# ADCS Operation Functions with realistic control logic

def detumbling_control():
    """Apply Bang-Bang control using magnetorquers to reduce angular rate."""
    angular_rate = get_angular_rate()
    if angular_rate > ANGULAR_RATE_THRESHOLD:
        torque = -MAGNETORQUER_MAX if angular_rate > 0 else MAGNETORQUER_MAX
        log_event(f"[DETUMBLING] Angular rate: {angular_rate:.2f}°/s, applying torque: {torque:.3f} Nm")
    else:
        log_event("[DETUMBLING] Angular rate within safe limits, preparing to transition.")

def sun_acquisition():
    """Align the satellite with the sun using proportional control."""
    sun_error = get_sun_vector()
    if sun_error > SUN_ALIGNMENT_THRESHOLD:
        control_torque = -0.05 * sun_error  # Proportional control
        log_event(f"[SUN_ACQUISITION] Sun error: {sun_error:.2f}°, applying control torque: {control_torque:.3f} Nm")
    else:
        log_event("[SUN_ACQUISITION] Sun alignment achieved, transitioning to NOMINAL_POINTING.")

def nominal_pointing():
    """Maintain precise attitude using PD control with reaction wheels."""
    error = get_quaternion_error()
    if error > 0.5:
        reaction_wheel_torque = -0.1 * error  # Simplified PD control (only proportional part)
        log_event(f"[NOMINAL_POINTING] Orientation error: {error:.2f}°, applying reaction wheel torque: {reaction_wheel_torque:.3f} Nm")
    else:
        log_event("[NOMINAL_POINTING] Attitude stable and within tolerance.")

def safe_mode():
    """Enter a low-power state with minimal operations for fault tolerance."""
    log_event("[SAFE_MODE] Entering safe mode. Minimizing actuator usage and reducing processing load.")

# Persistence functions for state recovery
def save_state(state):
    """Persist the current state to non-volatile memory."""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump({'state': state.name}, f)
    except IOError as e:
        log_event(f"Error saving state: {e}")

def load_state():
    """Load the last known state from non-volatile memory."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                data = json.load(f)
                return ADCSState[data['state']]
        except (IOError, KeyError, json.JSONDecodeError) as e:
            log_event(f"Error loading state: {e}")
    log_event("No valid saved state found, defaulting to DETUMBLING.")
    return ADCSState.DETUMBLING

# State Transition Logic with fault handling and recovery
def state_transition(current_state):
    """Determine the next state based on current system conditions."""
    angular_rate = get_angular_rate()
    sun_error = get_sun_vector()
    power_ok = check_power()

    # Verify sensor functionality with retries
    sensor_ok = False
    for _ in range(3):
        if check_sensors():
            sensor_ok = True
            break
        time.sleep(0.5)

    # Immediate safety: if power or sensor failures persist, transition to SAFE_MODE.
    if not power_ok or not sensor_ok:
        log_event("Critical fault: Low power or sensor anomaly detected. Transitioning to SAFE_MODE.")
        return ADCSState.SAFE_MODE

    # If angular rate exceeds threshold, force DETUMBLING.
    if angular_rate > ANGULAR_RATE_THRESHOLD:
        log_event("High angular rate detected. Transitioning to DETUMBLING.")
        return ADCSState.DETUMBLING

    # If sun alignment error is minimal, then proceed to NOMINAL_POINTING.
    if sun_error < SUN_ALIGNMENT_THRESHOLD:
        log_event("Sun alignment within acceptable limits. Transitioning to NOMINAL_POINTING.")
        return ADCSState.NOMINAL_POINTING

    # Otherwise, continue in SUN_ACQUISITION to further adjust alignment.
    return ADCSState.SUN_ACQUISITION

def main():
    # Processor Reset Recovery: Load last known state
    current_state = load_state()
    log_event(f"System starting in state: {current_state.name}")

    while True:
        # Execute state-specific operations
        if current_state == ADCSState.DETUMBLING:
            detumbling_control()
        elif current_state == ADCSState.SUN_ACQUISITION:
            sun_acquisition()
        elif current_state == ADCSState.NOMINAL_POINTING:
            nominal_pointing()
        elif current_state == ADCSState.SAFE_MODE:
            safe_mode()

        # Save the current state for recovery purposes
        save_state(current_state)

        # Evaluate system conditions to determine the next state
        next_state = state_transition(current_state)
        if next_state != current_state:
            log_event(f"Transitioning from {current_state.name} to {next_state.name}")
            current_state = next_state

        # Wait for the next control loop iteration
        time.sleep(CONTROL_LOOP_INTERVAL)

if __name__ == "__main__":
    main()
