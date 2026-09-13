"use client";

import styles from "./WeatherWidget.module.css";

interface Props {
  windSpeedMs?: number;
  windDirDeg?: number;
  ambientTempC?: number;
  gustsMs?: number;
}

function dirToCompass(deg: number): string {
  const sectors = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
  const idx = Math.round(((deg % 360) / 22.5)) % 16;
  return sectors[idx] ?? "SW";
}

export default function WeatherWidget({
  windSpeedMs = 12.4,
  windDirDeg = 235,
  ambientTempC = 8.4,
  gustsMs: propGusts,
}: Props) {
  const gustsMs = propGusts ?? Math.round(windSpeedMs * 1.25 * 10) / 10;
  const baroHpa = 1014;
  const airDensity = 1.23; // kg/m^3 standard
  const compass = dirToCompass(windDirDeg);

  // 6-hour trend relative to current SCADA reading
  const forecast = [
    { time: "Now", speed: windSpeedMs, dir: `${windDirDeg}° ${compass}` },
    { time: "+1h", speed: Math.round((windSpeedMs + 0.4) * 10) / 10, dir: `${(windDirDeg + 3) % 360}° ${dirToCompass(windDirDeg + 3)}` },
    { time: "+2h", speed: Math.round((windSpeedMs + 0.8) * 10) / 10, dir: `${(windDirDeg + 5) % 360}° ${dirToCompass(windDirDeg + 5)}` },
    { time: "+3h", speed: Math.round((windSpeedMs + 0.5) * 10) / 10, dir: `${(windDirDeg + 7) % 360}° ${dirToCompass(windDirDeg + 7)}` },
    { time: "+4h", speed: Math.round((windSpeedMs - 0.3) * 10) / 10, dir: `${(windDirDeg + 8) % 360}° ${dirToCompass(windDirDeg + 8)}` },
    { time: "+5h", speed: Math.round((windSpeedMs - 0.7) * 10) / 10, dir: `${(windDirDeg + 10) % 360}° ${dirToCompass(windDirDeg + 10)}` },
    { time: "+6h", speed: Math.round((windSpeedMs - 1.2) * 10) / 10, dir: `${(windDirDeg + 12) % 360}° ${dirToCompass(windDirDeg + 12)}` },
  ];

  return (
    <div className={`card ${styles.container}`} style={{ padding: "16px 18px" }}>
      <div className={styles.header}>
        <h3>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#38bdf8" }} />
          Meteorological Conditions &amp; Wind Trend
        </h3>
        <span className="hint">Nacelle LiDAR &amp; Met Mast Telemetry</span>
      </div>

      <div className={styles.grid}>
        <div className={styles.metricCard}>
          <span className={styles.label}>Nacelle Wind Speed</span>
          <span className={`${styles.val} num`}>{windSpeedMs.toFixed(1)} m/s</span>
          <span className={styles.sub}>{windSpeedMs >= 3.5 && windSpeedMs <= 25 ? "Optimal power band" : "Sub-optimal wind"}</span>
        </div>
        <div className={styles.metricCard}>
          <span className={styles.label}>Gust Velocity</span>
          <span className={`${styles.val} num`}>{gustsMs.toFixed(1)} m/s</span>
          <span className={styles.sub}>Peak instantaneous gust</span>
        </div>
        <div className={styles.metricCard}>
          <span className={styles.label}>Wind Direction</span>
          <span className={`${styles.val} num`}>{windDirDeg}° {compass}</span>
          <span className={styles.sub}>Prevailing nacelle yaw</span>
        </div>
        <div className={styles.metricCard}>
          <span className={styles.label}>Ambient Temp</span>
          <span className={`${styles.val} num`}>{ambientTempC.toFixed(1)} °C</span>
          <span className={styles.sub}>{ambientTempC > 2 ? "No icing hazard" : "Icing advisory"}</span>
        </div>
        <div className={styles.metricCard}>
          <span className={styles.label}>Barometric Pressure</span>
          <span className={`${styles.val} num`}>{baroHpa} hPa</span>
          <span className={styles.sub}>Standard atmospheric</span>
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

