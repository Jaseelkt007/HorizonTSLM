"use client";

import styles from "./WeatherWidget.module.css";

interface Props {
  windSpeedMs?: number;
  windDirDeg?: number;
  ambientTempC?: number;
}

export default function WeatherWidget({
  windSpeedMs = 13.8,
  windDirDeg = 235,
  ambientTempC = 8.4,
}: Props) {
  const gustsMs = Math.round((windSpeedMs * 1.28) * 10) / 10;
  const baroHpa = 1014;
  const airDensity = 1.23; // kg/m^3

  // 6-hour forecast steps
  const forecast = [
    { time: "Now", speed: windSpeedMs, dir: "235° SW" },
    { time: "+1h", speed: Math.round((windSpeedMs + 0.6) * 10) / 10, dir: "238° SW" },
    { time: "+2h", speed: Math.round((windSpeedMs + 1.2) * 10) / 10, dir: "240° WSW" },
    { time: "+3h", speed: Math.round((windSpeedMs + 0.8) * 10) / 10, dir: "242° WSW" },
    { time: "+4h", speed: Math.round((windSpeedMs - 0.5) * 10) / 10, dir: "245° W" },
    { time: "+5h", speed: Math.round((windSpeedMs - 1.1) * 10) / 10, dir: "248° W" },
    { time: "+6h", speed: Math.round((windSpeedMs - 2.0) * 10) / 10, dir: "250° W" },
  ];

  return (
    <div className={`card ${styles.container}`} style={{ padding: "16px 18px" }}>
      <div className={styles.header}>
        <h3>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#38bdf8" }} />
          Meteorological Conditions & Wind Forecast
        </h3>
        <span className="hint">Nacelle LiDAR & Met Mast Telemetry</span>
      </div>

      <div className={styles.grid}>
        <div className={styles.metricCard}>
          <span className={styles.label}>Nacelle Wind Speed</span>
          <span className={`${styles.val} num`}>{windSpeedMs.toFixed(1)} m/s</span>
          <span className={styles.sub}>Optimal power band</span>
        </div>
        <div className={styles.metricCard}>
          <span className={styles.label}>Gust Velocity</span>
          <span className={`${styles.val} num`}>{gustsMs.toFixed(1)} m/s</span>
          <span className={styles.sub}>Dynamic load peak</span>
        </div>
        <div className={styles.metricCard}>
          <span className={styles.label}>Wind Direction</span>
          <span className={`${styles.val} num`}>{windDirDeg}° SW</span>
          <span className={styles.sub}>Nacelle yaw tracking</span>
        </div>
        <div className={styles.metricCard}>
          <span className={styles.label}>Ambient Temp</span>
          <span className={`${styles.val} num`}>{ambientTempC.toFixed(1)} °C</span>
          <span className={styles.sub}>No icing hazard</span>
        </div>
        <div className={styles.metricCard}>
          <span className={styles.label}>Barometric Pressure</span>
          <span className={`${styles.val} num`}>{baroHpa} hPa</span>
          <span className={styles.sub}>Stable frontal passage</span>
        </div>
        <div className={styles.metricCard}>
          <span className={styles.label}>Air Density</span>
          <span className={`${styles.val} num`}>{airDensity} kg/m³</span>
          <span className={styles.sub}>ISA sea level std</span>
        </div>
      </div>

      <div className={styles.forecastTimeline}>
        {forecast.map((f, i) => (
          <div key={i} className={styles.hourNode}>
            <span className={styles.hourTime}>{f.time}</span>
            <span className={`${styles.hourWind} num`}>{f.speed} m/s</span>
            <span className={styles.hourDir}>{f.dir}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
