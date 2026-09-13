"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

import { cls, tcode } from "@/lib/format";
import { computeImpact, fmtGbp, fmtMWh } from "@/lib/impact";
import { FARM } from "@/lib/labels";
import type { Farm, WindowSummary } from "@/lib/types";

import { IconArrow } from "./Icons";
import styles from "./PlantMap3D.module.css";

interface Props {
  farm: Farm;
  windows: WindowSummary[];
  onSelectTurbine?: (turbine: number) => void;
}

// 3D coordinates on ground plane (X, Z)
const TURBINE_COORDS: Record<Farm, Record<number, [number, number]>> = {
  kelmarsh: {
    1: [-90, -40],
    2: [-20, -60],
    3: [60, -45],
    4: [-60, 50],
    5: [15, 60],
    6: [90, 40],
  },
  penmanshiel: {
    1: [-110, -70],
    2: [-65, -75],
    4: [-15, -65],
    5: [40, -70],
    6: [95, -55],
    7: [-85, -5],
    8: [-30, -10],
    9: [25, 0],
    10: [80, -10],
    11: [-95, 65],
    12: [-40, 55],
    13: [15, 60],
    14: [65, 50],
    15: [110, 65],
  },
};

export default function PlantMap3D({ farm, windows, onSelectTurbine }: Props) {
  const mountRef = useRef<HTMLDivElement>(null);
  const [selectedTurbine, setSelectedTurbine] = useState<number>(farm === "kelmarsh" ? 1 : 7);

  const farmWindows = useMemo(() => windows.filter((w) => w.farm === farm), [windows, farm]);

  const turbineStats = useMemo(() => {
    const map = new Map<number, { w: WindowSummary; impact: ReturnType<typeof computeImpact> }>();
    const turbines = [...new Set(farmWindows.map((w) => w.turbine))];
    for (const t of turbines) {
      const list = farmWindows
        .filter((w) => w.turbine === t)
        .sort((a, b) => a.anchor.localeCompare(b.anchor));
      const latest = list[list.length - 1];
      map.set(t, { w: latest, impact: computeImpact(latest) });
    }
    return map;
  }, [farmWindows]);

  const selectedData = turbineStats.get(selectedTurbine);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    // 1. Scene, Camera, Renderer
    const width = container.clientWidth || 900;
    const height = container.clientHeight || 440;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a101d);
    scene.fog = new THREE.FogExp2(0x0a101d, 0.0028);

    const camera = new THREE.PerspectiveCamera(42, width / height, 1, 1000);
    camera.position.set(0, 160, 240);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.maxPolarAngle = Math.PI / 2 - 0.06; // Prevent camera from dipping below ground
    controls.minDistance = 60;
    controls.maxDistance = 450;
    controls.target.set(0, 15, 0);

    // 2. Lighting
    const hemiLight = new THREE.HemisphereLight(0xddeeff, 0x182030, 1.2);
    scene.add(hemiLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 1.8);
    dirLight.position.set(120, 200, 80);
    dirLight.castShadow = true;
    scene.add(dirLight);

    // 3. Ground Terrain & Grid
    const groundGeo = new THREE.PlaneGeometry(600, 500, 32, 32);
    const groundMat = new THREE.MeshStandardMaterial({
      color: 0x0f172a,
      roughness: 0.85,
      metalness: 0.1,
    });
    const ground = new THREE.Mesh(groundGeo, groundMat);
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);

    const gridHelper = new THREE.GridHelper(500, 35, 0x1e293b, 0x131c2e);
    gridHelper.position.y = 0.1;
    scene.add(gridHelper);

    // 4. Turbines
    const coords = TURBINE_COORDS[farm] || {};
    const rotors: THREE.Group[] = [];
    const interactiveMeshes: THREE.Mesh[] = [];

    const towerMat = new THREE.MeshStandardMaterial({ color: 0xe2e8f0, roughness: 0.35, metalness: 0.2 });
    const nacelleMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.3, metalness: 0.2 });
    const bladeMat = new THREE.MeshStandardMaterial({ color: 0xf1f5f9, roughness: 0.25 });

    // Wind direction is 235° SW (convert to radians for nacelle yaw)
    const windRad = (235 * Math.PI) / 180;

    Object.entries(coords).forEach(([tStr, [x, z]]) => {
      const tNum = parseInt(tStr, 10);
      const data = turbineStats.get(tNum);
      const isCritical = data?.impact.urgency === "critical";
      const isAdvisory = data?.impact.urgency === "advisory";

      const turbineGroup = new THREE.Group();
      turbineGroup.position.set(x, 0, z);

      // Tower
      const towerHeight = 36;
      const towerGeo = new THREE.CylinderGeometry(0.8, 1.6, towerHeight, 18);
      const tower = new THREE.Mesh(towerGeo, towerMat);
      tower.position.y = towerHeight / 2;
      tower.castShadow = true;
      tower.userData = { turbineId: tNum };
      turbineGroup.add(tower);
      interactiveMeshes.push(tower);

      // Nacelle (oriented to wind)
      const nacelleGeo = new THREE.BoxGeometry(3.5, 3.2, 8.5);
      const nacelle = new THREE.Mesh(nacelleGeo, nacelleMat);
      nacelle.position.y = towerHeight;
      nacelle.rotation.y = windRad;
      nacelle.castShadow = true;
      nacelle.userData = { turbineId: tNum };
      turbineGroup.add(nacelle);
      interactiveMeshes.push(nacelle);

      // Status Beacon on top of nacelle
      const beaconColor = isCritical ? 0xef4444 : isAdvisory ? 0xf59e0b : 0x10b981;
      const beaconGeo = new THREE.SphereGeometry(1.2, 16, 16);
      const beaconMat = new THREE.MeshBasicMaterial({ color: beaconColor });
      const beacon = new THREE.Mesh(beaconGeo, beaconMat);
      beacon.position.set(0, towerHeight + 2.5, 0);
      turbineGroup.add(beacon);

      // Base Halo ring
      const ringGeo = new THREE.RingGeometry(3.5, 5.0, 32);
      const ringMat = new THREE.MeshBasicMaterial({
        color: beaconColor,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: isCritical ? 0.8 : 0.4,
      });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.rotation.x = -Math.PI / 2;
      ring.position.y = 0.2;
      turbineGroup.add(ring);

      // Rotor & Blades (attached to front of nacelle)
      const rotorGroup = new THREE.Group();
      const hubOffsetZ = 4.2;
      rotorGroup.position.set(
        x + Math.sin(windRad) * hubOffsetZ,
        towerHeight,
        z + Math.cos(windRad) * hubOffsetZ,
      );
      rotorGroup.rotation.y = windRad;

      // Hub
      const hubGeo = new THREE.SphereGeometry(1.4, 16, 16);
      const hub = new THREE.Mesh(hubGeo, nacelleMat);
      rotorGroup.add(hub);

      // 3 Blades
      const bladeLen = 22;
      for (let b = 0; b < 3; b++) {
        const angle = (b * 2 * Math.PI) / 3;
        const bladeGeo = new THREE.ConeGeometry(0.7, bladeLen, 6);
        const blade = new THREE.Mesh(bladeGeo, bladeMat);
        blade.position.set(Math.sin(angle) * (bladeLen / 2), Math.cos(angle) * (bladeLen / 2), 0);
        blade.rotation.z = -angle;
        blade.castShadow = true;
        rotorGroup.add(blade);
      }

      scene.add(turbineGroup);
      scene.add(rotorGroup);
      rotors.push(rotorGroup);
    });

    // 5. Wind Vector Particle Stream
    const pCount = 300;
    const pGeo = new THREE.BufferGeometry();
    const pPos = new Float32Array(pCount * 3);
    const pSpeed = new Float32Array(pCount);

    const windDirX = Math.sin(windRad);
    const windDirZ = Math.cos(windRad);

    for (let i = 0; i < pCount; i++) {
      pPos[i * 3] = (Math.random() - 0.5) * 400;
      pPos[i * 3 + 1] = 10 + Math.random() * 50;
      pPos[i * 3 + 2] = (Math.random() - 0.5) * 400;
      pSpeed[i] = 0.8 + Math.random() * 0.7;
    }
    pGeo.setAttribute("position", new THREE.BufferAttribute(pPos, 3));

    const pMat = new THREE.PointsMaterial({
      color: 0x38bdf8,
      size: 1.8,
      transparent: true,
      opacity: 0.55,
      blending: THREE.AdditiveBlending,
    });
    const particles = new THREE.Points(pGeo, pMat);
    scene.add(particles);

    // 6. Raycasting for click interaction
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    const handleClick = (e: MouseEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(interactiveMeshes);
      if (intersects.length > 0) {
        const tId = intersects[0].object.userData.turbineId;
        if (typeof tId === "number") {
          setSelectedTurbine(tId);
          onSelectTurbine?.(tId);
        }
      }
    };

    renderer.domElement.addEventListener("click", handleClick);

    // 7. Animation Loop
    let animId: number;
    const clock = new THREE.Clock();

    const animate = () => {
      animId = requestAnimationFrame(animate);
      const delta = clock.getDelta();

      // Spin blades (approx 14 rpm)
      rotors.forEach((r, idx) => {
        r.rotation.z += (1.4 + (idx % 3) * 0.1) * delta;
      });

      // Move wind particles
      const positions = pGeo.attributes.position.array as Float32Array;
      for (let i = 0; i < pCount; i++) {
        positions[i * 3] += windDirX * pSpeed[i];
        positions[i * 3 + 2] += windDirZ * pSpeed[i];

        // Wrap around boundaries
        if (positions[i * 3] > 220 || positions[i * 3] < -220 || positions[i * 3 + 2] > 220 || positions[i * 3 + 2] < -220) {
          positions[i * 3] = -windDirX * 180 + (Math.random() - 0.5) * 120;
          positions[i * 3 + 2] = -windDirZ * 180 + (Math.random() - 0.5) * 120;
        }
      }
      pGeo.attributes.position.needsUpdate = true;

      controls.update();
      renderer.render(scene, camera);
    };

    animate();

    const handleResize = () => {
      if (!container) return;
      const nw = container.clientWidth;
      const nh = container.clientHeight || 440;
      camera.aspect = nw / nh;
      camera.updateProjectionMatrix();
      renderer.setSize(nw, nh);
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      renderer.domElement.removeEventListener("click", handleClick);
      cancelAnimationFrame(animId);
      controls.dispose();
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [farm, turbineStats, onSelectTurbine]);

  return (
    <div className={styles.container}>
      <div className={styles.overlayTop}>
        <div className={styles.mapTitle}>
          <h3>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#38bdf8" }} />
            3D Plant Map & Wake Aerodynamics — {FARM[farm].name}
          </h3>
          <p>
            {FARM[farm].type} · 3D real-time simulation · Click any turbine node to inspect telemetry
          </p>
        </div>

        <div className={styles.windBadge}>
          <span className={styles.windArrow} style={{ transform: "rotate(235deg)" }}>
            ⬆
          </span>
          <span>Prevailing Wind: 235° SW @ 13.8 m/s</span>
        </div>
      </div>

      <div ref={mountRef} className={styles.canvasWrapper} />

      <div className={styles.controlsHelp}>
        Left Click + Drag: Orbit Camera · Right Click + Drag: Pan · Scroll: Zoom · Click Turbine: Select
      </div>

      {selectedData && (
        <div className={styles.previewCard}>
          <div className={styles.previewHeader}>
            <h4>{tcode({ turbine: selectedTurbine })} — {FARM[farm].name}</h4>
            <span
              className="chip"
              style={{
                background:
                  selectedData.impact.urgency === "critical"
                    ? "rgba(239, 68, 68, 0.15)"
                    : selectedData.impact.urgency === "advisory"
                      ? "rgba(245, 158, 11, 0.15)"
                      : "rgba(16, 185, 129, 0.15)",
                color:
                  selectedData.impact.urgency === "critical"
                    ? "#ef4444"
                    : selectedData.impact.urgency === "advisory"
                      ? "#f59e0b"
                      : "#10b981",
                fontWeight: 700,
                fontSize: 11,
              }}
            >
              {selectedData.impact.urgency.toUpperCase()}
            </span>
          </div>

          <div className={styles.previewStats}>
            <div className={styles.statBox}>
              <div className={styles.statLabel}>Subsystem</div>
              <div className={styles.statVal} style={{ fontSize: 13 }}>
                {selectedData.w.pred !== "none" ? cls(selectedData.w.pred) : "Nominal Envelope"}
              </div>
            </div>
            <div className={styles.statBox}>
              <div className={styles.statLabel}>Loss at Risk</div>
              <div className={styles.statVal}>
                {selectedData.impact.lostMWh > 0 ? fmtMWh(selectedData.impact.lostMWh) : "0.0 MWh"}
              </div>
            </div>
            <div className={styles.statBox}>
              <div className={styles.statLabel}>Financial Exposure</div>
              <div className={styles.statVal} style={{ color: selectedData.impact.revenueAtRiskGbp > 0 ? "#ef4444" : undefined }}>
                {selectedData.impact.totalFinancialRiskGbp > 0 ? fmtGbp(selectedData.impact.totalFinancialRiskGbp) : "£0"}
              </div>
            </div>
            <div className={styles.statBox}>
              <div className={styles.statLabel}>Lead Time</div>
              <div className={styles.statVal}>
                {selectedData.impact.leadTimeHours ? `${selectedData.impact.leadTimeHours} h ahead` : "Nominal"}
              </div>
            </div>
          </div>

          <Link href={`/turbines/${farm}/${selectedTurbine}`} className={styles.previewAction}>
            Step into Turbine Diagnostics <IconArrow />
          </Link>
        </div>
      )}
    </div>
  );
}
