"""Signal taxonomy, units, and anomaly classifications for Kelmarsh SCADA data."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SignalSpec:
    greenbyte_id: int
    csv_column_prefix: str
    canonical_name: str
    unit: str
    description: str
    min_val: float
    max_val: float


# Selected 8 high-signal channels for the TSLM model footprint
SELECTED_SIGNALS: list[SignalSpec] = [
    SignalSpec(
        greenbyte_id=1,
        csv_column_prefix="Wind speed",
        canonical_name="wind_speed",
        unit="m/s",
        description="Hub wind speed",
        min_val=0.0,
        max_val=35.0,
    ),
    SignalSpec(
        greenbyte_id=5,
        csv_column_prefix="Power",
        canonical_name="power",
        unit="kW",
        description="Active electrical power generation",
        min_val=-50.0,
        max_val=2200.0,
    ),
    SignalSpec(
        greenbyte_id=54,
        csv_column_prefix="Rotor speed",
        canonical_name="rotor_speed",
        unit="RPM",
        description="Low speed shaft rotor rotation speed",
        min_val=0.0,
        max_val=25.0,
    ),
    SignalSpec(
        greenbyte_id=86,
        csv_column_prefix="Generator RPM",
        canonical_name="generator_rpm",
        unit="RPM",
        description="High speed shaft generator rotation speed",
        min_val=0.0,
        max_val=2000.0,
    ),
    SignalSpec(
        greenbyte_id=178,
        csv_column_prefix="Gear oil temperature",
        canonical_name="gear_oil_temp",
        unit="degC",
        description="Gearbox lubrication oil bulk temperature",
        min_val=-10.0,
        max_val=100.0,
    ),
    SignalSpec(
        greenbyte_id=119,
        csv_column_prefix="Generator bearing front temperature",
        canonical_name="gen_bearing_temp",
        unit="degC",
        description="Drive-end generator bearing temperature",
        min_val=-10.0,
        max_val=110.0,
    ),
    SignalSpec(
        greenbyte_id=80,
        csv_column_prefix="Blade angle (pitch position) A",
        canonical_name="pitch_angle",
        unit="deg",
        description="Blade 1 pitch angle",
        min_val=-5.0,
        max_val=95.0,
    ),
    SignalSpec(
        greenbyte_id=456,
        csv_column_prefix="Drive train acceleration",
        canonical_name="drivetrain_accel",
        unit="mm/s^2",
        description="Nacelle drivetrain vibration acceleration",
        min_val=0.0,
        max_val=1000.0,
    ),
]

SIGNAL_NAMES = [s.canonical_name for s in SELECTED_SIGNALS]

# Status / Fault label taxonomy (Coarse 5-class benchmark)
FAULT_CLASSES = [
    "Normal Operation",
    "Gearbox Overheating",
    "Generator Bearing Anomaly",
    "Pitch / Aerodynamic Fault",
    "Turbine Trip / Forced Outage",
]

FAULT_CLASS_TO_IDX = {name: idx for idx, name in enumerate(FAULT_CLASSES)}
IDX_TO_FAULT_CLASS = {idx: name for idx, name in enumerate(FAULT_CLASSES)}

# Canonical Subsystem Taxonomy (11 Subsystems + Normal Operation)
# Aligned with docs/problem-statement.md section 8 and src/turbine_tslm/data/taxonomy.yaml
SUBSYSTEM_CLASSES = [
    "normal_operation",
    "gearbox_lubrication",
    "generator_cooling",
    "generator_bearing",
    "pitch_system",
    "brake_hydraulics",
    "converter_grid",
    "yaw_cable",
    "structural_overspeed",
    "sensor_comms",
    "environmental_stop",
    "curtailment_external",
    "manual_safety",
]

SUBSYSTEM_CLASS_TO_IDX = {name: idx for idx, name in enumerate(SUBSYSTEM_CLASSES)}
IDX_TO_SUBSYSTEM_CLASS = {idx: name for idx, name in enumerate(SUBSYSTEM_CLASSES)}

# Operational Triage Taxonomy (Task T3 in Problem Statement)
TRIAGE_CLASSES = [
    "normal",
    "benign_stop",
    "fault",
]

TRIAGE_CLASS_TO_IDX = {name: idx for idx, name in enumerate(TRIAGE_CLASSES)}
IDX_TO_TRIAGE_CLASS = {idx: name for idx, name in enumerate(TRIAGE_CLASSES)}

# Mapping between Subsystem classes and coarse 5-class benchmark
SUBSYSTEM_TO_COARSE_FAULT: dict[str, str] = {
    "normal_operation": "Normal Operation",
    "gearbox_lubrication": "Gearbox Overheating",
    "generator_cooling": "Generator Bearing Anomaly",
    "generator_bearing": "Generator Bearing Anomaly",
    "pitch_system": "Pitch / Aerodynamic Fault",
    "structural_overspeed": "Pitch / Aerodynamic Fault",
    "brake_hydraulics": "Turbine Trip / Forced Outage",
    "converter_grid": "Turbine Trip / Forced Outage",
    "yaw_cable": "Turbine Trip / Forced Outage",
    "sensor_comms": "Turbine Trip / Forced Outage",
    "manual_safety": "Turbine Trip / Forced Outage",
    "environmental_stop": "Normal Operation",
    "curtailment_external": "Normal Operation",
}


# Window definitions (Problem Statement Section 6 specifies 24-hour windows at 10-min resolution)
SAMPLING_PERIOD_MINUTES = 10
WINDOW_DURATION_HOURS = 24
WINDOW_STEPS = 144  # 144 steps * 10 min = 24 hours
WINDOW_STEPS_12H = 72
WINDOW_STEPS_24H = 144

# Structured OpenTSLM Chain-of-Thought output template
COT_OUTPUT_TEMPLATE = """Triage: {triage}
Subsystem: {subsystem}
Alarm Event: {alarm_event}
Rationale: {rationale}
Recommendation: {action}
Answer: {answer}"""


# Dataset IDs & Zenodo Records
PENMANSHIEL_DATASET_ID = "energy/penmanshiel-wind-scada"
KELMARSH_DATASET_ID = "energy/kelmarsh-wind-scada"

PENMANSHIEL_ZENODO_RECORD_ID = "16807304"  # Concept 5946807
KELMARSH_ZENODO_RECORD_ID = "16807551"     # Concept 5841833

# Wind Farm Turbine Definitions
# Penmanshiel: 14 Senvion MM82 turbines (WT01-WT15, WT03 does not exist per Cubico)
PENMANSHIEL_TURBINES = [
    f"Penmanshiel WT{i:02d}"
    for i in [1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
]

# Kelmarsh: 6 Senvion MM92 turbines
KELMARSH_TURBINES = [f"Kelmarsh {i}" for i in range(1, 7)]

# Penmanshiel Zero-Leakage Data Splits (Turbine-level)
PENMANSHIEL_TRAIN_TURBINES = tuple(PENMANSHIEL_TURBINES[:9])   # WT01..WT10 (9 turbines)
PENMANSHIEL_VAL_TURBINES = tuple(PENMANSHIEL_TURBINES[9:11])   # WT11, WT12 (2 turbines)
PENMANSHIEL_TEST_TURBINES = tuple(PENMANSHIEL_TURBINES[11:])   # WT13, WT14, WT15 (3 turbines)

# Kelmarsh Zero-Shot / Demo Turbines (100% held-out, blank data)
KELMARSH_DEMO_TURBINES = tuple(KELMARSH_TURBINES)


# Empirical Service Contract Categories (23 distinct classes from Greenbyte SCADA logs)
# Documented in mk/data_structure_report.md Section 4.3
SERVICE_CONTRACT_CATEGORY_MAP: dict[str, dict[str, str]] = {
    "System OK (32)": {"subsystem": "normal_operation", "coarse_fault": "Normal Operation", "triage": "normal"},
    "External stop (low wind speed)  (5)": {"subsystem": "environmental_stop", "coarse_fault": "Normal Operation", "triage": "benign_stop"},
    "External stop (low wind speed) (5)": {"subsystem": "environmental_stop", "coarse_fault": "Normal Operation", "triage": "benign_stop"},
    "Operating states  (28)": {"subsystem": "environmental_stop", "coarse_fault": "Normal Operation", "triage": "benign_stop"},
    "Operating states (28)": {"subsystem": "environmental_stop", "coarse_fault": "Normal Operation", "triage": "benign_stop"},
    "Warnings (27)": {"subsystem": "normal_operation", "coarse_fault": "Normal Operation", "triage": "benign_stop"},
    "Manual stop (service)  (9)": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "benign_stop"},
    "Manual stop (service) (9)": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "benign_stop"},
    "External stop (grid) (4)": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault"},
    "Generator and Converter errors (20)": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault"},
    "Safety stop of WEC (15)": {"subsystem": "structural_overspeed", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault"},
    "Remote stop (30)": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "benign_stop"},
    "Sensor error (21)": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault"},
    "Mechanical error (23)": {"subsystem": "gearbox_lubrication", "coarse_fault": "Gearbox Overheating", "triage": "fault"},
    "Pitch errors (18)": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault"},
    "Repeated error  (25)": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault"},
    "Repeated error (25)": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault"},
    "Electrical error (24)": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault"},
    "External stop (climate) (6)": {"subsystem": "environmental_stop", "coarse_fault": "Normal Operation", "triage": "benign_stop"},
    "Safety chain (13)": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault"},
    "Techical Curtailments (just for calculation)": {"subsystem": "curtailment_external", "coarse_fault": "Normal Operation", "triage": "benign_stop"},
    "Emergency stop switch (Converter) (12)": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault"},
    "Controller error of the WP3100 (16)": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault"},
    "Temperature error (22)": {"subsystem": "generator_bearing", "coarse_fault": "Generator Bearing Anomaly", "triage": "fault"},
    "Emergency stop switch (Nacelle) (11)": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault"},
    "WEC Shutdown (1)": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault"},
    "Overspeed (14)": {"subsystem": "structural_overspeed", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault"},
}

# Empirical IEC 61400-26 Availability Categories (8 distinct classes)
# Documented in mk/data_structure_report.md Section 4.2
IEC_CATEGORY_MAP: dict[str, dict[str, str]] = {
    "Full Performance": {"subsystem": "normal_operation", "coarse_fault": "Normal Operation", "triage": "normal"},
    "Partial Performance": {"subsystem": "curtailment_external", "coarse_fault": "Normal Operation", "triage": "benign_stop"},
    "Technical Standby": {"subsystem": "environmental_stop", "coarse_fault": "Normal Operation", "triage": "benign_stop"},
    "Out of Environmental Specification": {"subsystem": "environmental_stop", "coarse_fault": "Normal Operation", "triage": "benign_stop"},
    "Out of Electrical Specification": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault"},
    "Forced outage": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault"},
    "Scheduled Maintenance": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "benign_stop"},
    "Requested Shutdown": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "benign_stop"},
}

# Comprehensive Alarm & Status Code Taxonomy (from mk/data_structure_report.md Section 6)
HIGH_FREQUENCY_CODE_MAP: dict[str, dict[str, str]] = {
    # 1. Curtailment & Active Power Control
    "108": {"subsystem": "curtailment_external", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "WARNING"},
    "111": {"subsystem": "curtailment_external", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "WARNING"},
    "9000": {"subsystem": "curtailment_external", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "WARNING"},
    "9003": {"subsystem": "curtailment_external", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "INFO"},
    "9004": {"subsystem": "curtailment_external", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "INFO"},
    "9150": {"subsystem": "curtailment_external", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "WARNING"},
    "245": {"subsystem": "curtailment_external", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "INFO"},
    "248": {"subsystem": "curtailment_external", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "INFO"},
    "75": {"subsystem": "gearbox_lubrication", "coarse_fault": "Gearbox Overheating", "triage": "fault", "severity": "WARNING"},
    "77": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},

    # 2. Communications, SCADA, & Sensors
    "9997": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "8100": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "8102": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "8105": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "8400": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "8402": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "8405": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "benign_stop", "severity": "INFO"},
    "1160": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "1161": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "7324": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "7325": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "6515": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "6525": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "6530": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "6620": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "6622": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "6630": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "6635": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "6432": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "2510": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "2673": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "4600": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "7050": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "4022": {"subsystem": "sensor_comms", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},

    # 3. Gearbox & Lubrication
    "1550": {"subsystem": "gearbox_lubrication", "coarse_fault": "Gearbox Overheating", "triage": "fault", "severity": "TRIP"},
    "1548": {"subsystem": "gearbox_lubrication", "coarse_fault": "Gearbox Overheating", "triage": "fault", "severity": "TRIP"},
    "1510": {"subsystem": "gearbox_lubrication", "coarse_fault": "Gearbox Overheating", "triage": "fault", "severity": "TRIP"},
    "1620": {"subsystem": "gearbox_lubrication", "coarse_fault": "Gearbox Overheating", "triage": "fault", "severity": "TRIP"},
    "1630": {"subsystem": "gearbox_lubrication", "coarse_fault": "Gearbox Overheating", "triage": "fault", "severity": "TRIP"},
    "1700": {"subsystem": "gearbox_lubrication", "coarse_fault": "Gearbox Overheating", "triage": "fault", "severity": "WARNING"},
    "1725": {"subsystem": "gearbox_lubrication", "coarse_fault": "Gearbox Overheating", "triage": "fault", "severity": "WARNING"},
    "1729": {"subsystem": "gearbox_lubrication", "coarse_fault": "Gearbox Overheating", "triage": "fault", "severity": "WARNING"},
    "1800": {"subsystem": "gearbox_lubrication", "coarse_fault": "Gearbox Overheating", "triage": "fault", "severity": "TRIP"},
    "1810": {"subsystem": "gearbox_lubrication", "coarse_fault": "Gearbox Overheating", "triage": "fault", "severity": "WARNING"},
    "1815": {"subsystem": "gearbox_lubrication", "coarse_fault": "Gearbox Overheating", "triage": "fault", "severity": "TRIP"},
    "1825": {"subsystem": "gearbox_lubrication", "coarse_fault": "Gearbox Overheating", "triage": "fault", "severity": "WARNING"},
    "1860": {"subsystem": "gearbox_lubrication", "coarse_fault": "Gearbox Overheating", "triage": "fault", "severity": "WARNING"},
    "1920": {"subsystem": "gearbox_lubrication", "coarse_fault": "Gearbox Overheating", "triage": "fault", "severity": "WARNING"},
    "1922": {"subsystem": "gearbox_lubrication", "coarse_fault": "Gearbox Overheating", "triage": "fault", "severity": "WARNING"},
    "1924": {"subsystem": "gearbox_lubrication", "coarse_fault": "Gearbox Overheating", "triage": "fault", "severity": "TRIP"},
    "1552": {"subsystem": "gearbox_lubrication", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "INFO"},
    "1555": {"subsystem": "gearbox_lubrication", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "INFO"},
    "1560": {"subsystem": "gearbox_lubrication", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "INFO"},
    "1565": {"subsystem": "gearbox_lubrication", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "INFO"},
    "1570": {"subsystem": "gearbox_lubrication", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "INFO"},
    "1575": {"subsystem": "gearbox_lubrication", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "INFO"},

    # 4. Generator Cooling & Bearings
    "2605": {"subsystem": "generator_bearing", "coarse_fault": "Generator Bearing Anomaly", "triage": "fault", "severity": "TRIP"},
    "2600": {"subsystem": "generator_bearing", "coarse_fault": "Generator Bearing Anomaly", "triage": "fault", "severity": "WARNING"},
    "2660": {"subsystem": "generator_bearing", "coarse_fault": "Generator Bearing Anomaly", "triage": "fault", "severity": "TRIP"},
    "2810": {"subsystem": "generator_bearing", "coarse_fault": "Generator Bearing Anomaly", "triage": "fault", "severity": "TRIP"},
    "1320": {"subsystem": "generator_bearing", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "INFO"},
    "2550": {"subsystem": "generator_cooling", "coarse_fault": "Generator Bearing Anomaly", "triage": "fault", "severity": "WARNING"},
    "2650": {"subsystem": "generator_cooling", "coarse_fault": "Generator Bearing Anomaly", "triage": "fault", "severity": "WARNING"},
    "2655": {"subsystem": "generator_cooling", "coarse_fault": "Generator Bearing Anomaly", "triage": "fault", "severity": "WARNING"},
    "2674": {"subsystem": "generator_cooling", "coarse_fault": "Generator Bearing Anomaly", "triage": "fault", "severity": "WARNING"},
    "2900": {"subsystem": "generator_cooling", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "INFO"},
    "2910": {"subsystem": "generator_cooling", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "INFO"},
    "2920": {"subsystem": "generator_cooling", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "INFO"},
    "2930": {"subsystem": "generator_cooling", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "INFO"},

    # 5. Pitch System
    "650": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "656": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "657": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "658": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "665": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "670": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "675": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "WARNING"},
    "681": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "WARNING"},
    "682": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "WARNING"},
    "683": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "WARNING"},
    "692": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "697": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "WARNING"},
    "700": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "711": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "WARNING"},
    "712": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "WARNING"},
    "713": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "WARNING"},
    "714": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "WARNING"},
    "715": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "716": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "WARNING"},
    "717": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "WARNING"},
    "718": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "WARNING"},
    "720": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "WARNING"},
    "725": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "735": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "550": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "555": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "564": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "570": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "581": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "582": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "583": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "630": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "850": {"subsystem": "pitch_system", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "WARNING"},
    "200": {"subsystem": "pitch_system", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "INFO"},

    # 6. Converter, Grid, & Electrical Subsystems
    "3000": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "3110": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "3125": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "3130": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "3160": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "3200": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "3205": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "3210": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "3220": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "3260": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "3400": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "3410": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "3500": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "3501": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "3530": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "3532": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "3537": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "3543": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "3545": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "3547": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "3555": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "3570": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "3575": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "3585": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "3590": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "3591": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "3650": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "3750": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "3805": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "3820": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "3830": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "3835": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "3860": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "3870": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "3875": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "440": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "455": {"subsystem": "converter_grid", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},

    # 7. Structural Dynamics, Tower & Overspeed
    "4510": {"subsystem": "structural_overspeed", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "4520": {"subsystem": "structural_overspeed", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "4530": {"subsystem": "structural_overspeed", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "4540": {"subsystem": "structural_overspeed", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "4502": {"subsystem": "structural_overspeed", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "WARNING"},
    "805": {"subsystem": "structural_overspeed", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "815": {"subsystem": "structural_overspeed", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "820": {"subsystem": "structural_overspeed", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "59": {"subsystem": "structural_overspeed", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "WARNING"},
    "1050": {"subsystem": "structural_overspeed", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "WARNING"},
    "1070": {"subsystem": "structural_overspeed", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "WARNING"},

    # 8. Brake & Hydraulic Systems
    "2000": {"subsystem": "brake_hydraulics", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "2100": {"subsystem": "brake_hydraulics", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "2110": {"subsystem": "brake_hydraulics", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "2125": {"subsystem": "brake_hydraulics", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "305": {"subsystem": "brake_hydraulics", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "5510": {"subsystem": "brake_hydraulics", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "5600": {"subsystem": "brake_hydraulics", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "5710": {"subsystem": "brake_hydraulics", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "5720": {"subsystem": "brake_hydraulics", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "5730": {"subsystem": "brake_hydraulics", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "5750": {"subsystem": "brake_hydraulics", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "INFO"},
    "5760": {"subsystem": "brake_hydraulics", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "benign_stop", "severity": "INFO"},
    "785": {"subsystem": "brake_hydraulics", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "100100": {"subsystem": "brake_hydraulics", "coarse_fault": "Normal Operation", "triage": "normal", "severity": "INFO"},

    # 9. Yaw System & Cable Twist
    "6052": {"subsystem": "yaw_cable", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "6054": {"subsystem": "yaw_cable", "coarse_fault": "Normal Operation", "triage": "normal", "severity": "INFO"},
    "6056": {"subsystem": "yaw_cable", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "6111": {"subsystem": "yaw_cable", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "6120": {"subsystem": "yaw_cable", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "6200": {"subsystem": "yaw_cable", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "benign_stop", "severity": "INFO"},
    "6300": {"subsystem": "yaw_cable", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "6350": {"subsystem": "yaw_cable", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "WARNING"},
    "6410": {"subsystem": "yaw_cable", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "INFO"},

    # 10. Environmental & Meteorological Stoppages
    "10": {"subsystem": "environmental_stop", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "INFO"},
    "64": {"subsystem": "environmental_stop", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "TRIP"},
    "65": {"subsystem": "environmental_stop", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "INFO"},
    "68": {"subsystem": "environmental_stop", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "TRIP"},
    "63": {"subsystem": "environmental_stop", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "TRIP"},
    "45": {"subsystem": "environmental_stop", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "WARNING"},
    "60": {"subsystem": "environmental_stop", "coarse_fault": "Pitch / Aerodynamic Fault", "triage": "fault", "severity": "TRIP"},
    "6690": {"subsystem": "environmental_stop", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "TRIP"},
    "6540": {"subsystem": "environmental_stop", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "TRIP"},
    "6542": {"subsystem": "environmental_stop", "coarse_fault": "Normal Operation", "triage": "normal", "severity": "INFO"},
    "6682": {"subsystem": "environmental_stop", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "WARNING"},
    "6750": {"subsystem": "environmental_stop", "coarse_fault": "Normal Operation", "triage": "benign_stop", "severity": "INFO"},

    # 11. Manual Stops, Safety Circuit, & Maintenance
    "20": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "benign_stop", "severity": "TRIP"},
    "21": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "benign_stop", "severity": "TRIP"},
    "25": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "benign_stop", "severity": "TRIP"},
    "26": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "benign_stop", "severity": "WARNING"},
    "55": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "100": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "110": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "117": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "150": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "210": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "benign_stop", "severity": "TRIP"},
    "400": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "benign_stop", "severity": "INFO"},
    "402": {"subsystem": "manual_safety", "coarse_fault": "Normal Operation", "triage": "normal", "severity": "INFO"},
    "707": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "benign_stop", "severity": "INFO"},
    "710": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "benign_stop", "severity": "INFO"},
    "8000": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "benign_stop", "severity": "TRIP"},
    "9200": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "benign_stop", "severity": "TRIP"},
    "9210": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "benign_stop", "severity": "TRIP"},
    "4215": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "4225": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "7003": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},
    "7335": {"subsystem": "manual_safety", "coarse_fault": "Turbine Trip / Forced Outage", "triage": "fault", "severity": "TRIP"},

    # 12. Normal Operation & Nominal SCADA Codes
    "0": {"subsystem": "normal_operation", "coarse_fault": "Normal Operation", "triage": "normal", "severity": "NOMINAL"},
    "100130": {"subsystem": "normal_operation", "coarse_fault": "Normal Operation", "triage": "normal", "severity": "INFO"},
    "100180": {"subsystem": "normal_operation", "coarse_fault": "Normal Operation", "triage": "normal", "severity": "INFO"},
    "100190": {"subsystem": "normal_operation", "coarse_fault": "Normal Operation", "triage": "normal", "severity": "INFO"},
    "100200": {"subsystem": "normal_operation", "coarse_fault": "Normal Operation", "triage": "normal", "severity": "INFO"},
    "100210": {"subsystem": "normal_operation", "coarse_fault": "Normal Operation", "triage": "normal", "severity": "INFO"},
    "100300": {"subsystem": "normal_operation", "coarse_fault": "Normal Operation", "triage": "normal", "severity": "INFO"},
}


@dataclass
class StatusEventRecord:
    """Parsed SCADA status log event with full contractual and IEC taxonomy."""

    start: object  # pd.Timestamp or datetime
    end: object
    duration: float  # duration in seconds
    status: str      # e.g., "Stop", "Warning", "Informational", "Curtailment", "Communication"
    code: str        # manufacturer numerical code, e.g., "0", "10", "41", "2125"
    message: str     # standardized SCADA alarm text
    service_contract_category: str  # e.g., "System OK (32)", "Warnings (27)", "External stop (low wind speed)  (5)"
    iec_category: str               # e.g., "Full Performance", "Forced outage", "Technical Standby"
    comment: str = ""               # manual operator / technician log note
    global_contract_category: str = ""  # 2021+ schema
    custom_contract_category: str = ""  # 2021+ schema

    def to_dict(self) -> dict[str, object]:
        return {
            "start": str(self.start),
            "end": str(self.end),
            "duration": self.duration,
            "status": self.status,
            "code": self.code,
            "message": self.message,
            "service_contract_category": self.service_contract_category,
            "iec_category": self.iec_category,
            "comment": self.comment,
            "global_contract_category": self.global_contract_category,
            "custom_contract_category": self.custom_contract_category,
        }


@dataclass
class StructuredLMTarget:
    """Structured Time-Series Language Model target report (Aionic / OpenTSLM standard)."""

    finding: str
    evidence: str
    cause: str
    impact: str
    action: str
    subsystem: str
    triage: str = "normal"
    coarse_fault: str = "Normal Operation"
    comment: str = ""
    code: str = ""
    iec_category: str = ""
    service_contract_category: str = ""

    def to_formatted_target(self) -> str:
        """Format as standardized 5-line report ending in Answer: <subsystem>."""
        return (
            f"FINDING   {self.finding}\n"
            f"EVIDENCE  {self.evidence}\n"
            f"CAUSE     {self.cause}\n"
            f"IMPACT    {self.impact}\n"
            f"ACTION    {self.action}\n"
            f"Answer: {self.subsystem}"
        )

    def to_triage_target(self) -> str:
        """Format as immediate alarm explanation, operational triage, and subsystem diagnosis."""
        return (
            f"Triage: {self.triage}\n"
            f"Subsystem: {self.subsystem}\n"
            f"FINDING   {self.finding}\n"
            f"EVIDENCE  {self.evidence}\n"
            f"CAUSE     {self.cause}\n"
            f"IMPACT    {self.impact}\n"
            f"ACTION    {self.action}\n"
            f"Answer: {self.subsystem}"
        )

    def to_cot_text(self) -> str:
        """Return rationale + recommendation format for backward compatibility."""
        return f"Rationale: {self.evidence} {self.cause}\nRecommendation: {self.action}"



