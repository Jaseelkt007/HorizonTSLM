/** Naming only — every number on the page comes from the JSON files. */
import type { Farm, Split } from "./types";

export const CLASS_LABEL: Record<string, string> = {
  generator_cooling: "generator cooling",
  gearbox_lubrication: "gearbox lubrication",
  pitch_system: "pitch system",
  structural_overspeed: "structural / overspeed",
  converter_grid: "converter / grid",
  brake_hydraulics: "brake / hydraulics",
  yaw_cable: "yaw / cable",
  sensor_comms: "sensor / comms",
  none: "no fault stop",
};

/** For tight spots (list chips). */
export const CLASS_SHORT: Record<string, string> = {
  generator_cooling: "gen. cooling",
  gearbox_lubrication: "gearbox oil",
  pitch_system: "pitch",
  structural_overspeed: "overspeed",
  converter_grid: "converter / grid",
  brake_hydraulics: "brake / hydr.",
  yaw_cable: "yaw / cable",
  sensor_comms: "sensor / comms",
};

export const FARM: Record<Farm, { name: string; type: string; tag: string; why: string }> = {
  kelmarsh: {
    name: "Kelmarsh",
    type: "Senvion MM92",
    tag: "unseen farm",
    why: "a farm and turbine type the model never saw",
  },
  penmanshiel: {
    name: "Penmanshiel",
    type: "Senvion MM82",
    tag: "unseen years",
    why: "the training farm in 2020–21, years the model never saw",
  },
};

export const FARMS: Farm[] = ["kelmarsh", "penmanshiel"];

/** Channel groups on the window page, in the order they are drawn; `sub` names the subsystem classes they inform. */
export const GROUPS: { title: string; sub: string; channels: string[] }[] = [
  { title: "Operating point", sub: "wind, load and rotor state", channels: ["wind_speed", "power", "rotor_speed", "pitch_angle", "power_curve_residual"] },
  {
    title: "Generator and drivetrain temperatures",
    sub: "generator cooling · gearbox lubrication",
    channels: ["gen_bearing_front_temperature", "gen_bearing_rear_temperature", "stator_temperature", "gear_oil_temperature", "main_bearing_temperature", "ambient_temperature"],
  },
  { title: "Lubrication and structure", sub: "gearbox lubrication · structural / overspeed", channels: ["gear_oil_inlet_pressure", "tower_acceleration_x"] },
  { title: "Grid", sub: "converter / grid", channels: ["grid_voltage", "grid_frequency", "reactive_power"] },
  { title: "Yaw", sub: "yaw / cable", channels: ["wind_direction", "nacelle_position", "yaw_misalignment"] },
];

/** Short channel names for chart captions (the JSON carries the full description). */
export const CHANNEL_SHORT: Record<string, string> = {
  wind_speed: "wind speed",
  wind_direction: "wind direction",
  ambient_temperature: "nacelle ambient temp.",
  power: "active power",
  rotor_speed: "rotor speed",
  pitch_angle: "blade pitch angle",
  nacelle_position: "nacelle position",
  gen_bearing_front_temperature: "gen. bearing front",
  gen_bearing_rear_temperature: "gen. bearing rear",
  stator_temperature: "stator temperature",
  gear_oil_temperature: "gear oil temperature",
  main_bearing_temperature: "main bearing temp.",
  gear_oil_inlet_pressure: "gear oil inlet pressure",
  reactive_power: "reactive power",
  grid_voltage: "grid voltage",
  grid_frequency: "grid frequency",
  tower_acceleration_x: "tower acceleration X",
  power_curve_residual: "power-curve residual",
  yaw_misalignment: "yaw misalignment",
};

/** Which channels an explanation "cites" — a text heuristic over the sentence templates the model uses. */
export const CITES: Record<string, RegExp> = {
  wind_speed: /wind (?:rose|fell|is|was|speed|stayed|dropped|picked)|m\/s|cut-in/i,
  power: /producing about|power (?:rose|fell|at|is|dropped)|kW/i,
  rotor_speed: /rotor at|rotor speed|rpm/i,
  pitch_angle: /feather|pitch/i,
  power_curve_residual: /power curve|power-curve/i,
  gen_bearing_front_temperature: /front bearing|hotter than the other side/i,
  gen_bearing_rear_temperature: /rear bearing|hotter than the other side/i,
  stator_temperature: /stator/i,
  gear_oil_temperature: /gear oil temperature/i,
  main_bearing_temperature: /main bearing/i,
  ambient_temperature: /ambient/i,
  gear_oil_inlet_pressure: /oil (?:inlet )?pressure/i,
  tower_acceleration_x: /tower/i,
  grid_voltage: /grid voltage|voltage/i,
  grid_frequency: /grid frequency|frequency/i,
  reactive_power: /reactive/i,
  wind_direction: /wind direction/i,
  nacelle_position: /nacelle/i,
  yaw_misalignment: /off the wind direction|yaw|misalign/i,
};

export const SPLITS: Split[] = ["val", "test_a", "test_b"];
export const SPLIT_NAME: Record<Split, string> = {
  val: "Val · unseen turbines",
  test_a: "Test A · unseen years",
  test_b: "Test B · unseen farm",
};
