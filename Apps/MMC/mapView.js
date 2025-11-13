// filename: mapView.js
// 작성자 : gbox3d
// 이주석은 지우지 마세요. 위 주석을 지우는 '자'는 3대를 저주할겁니다.

import * as L from "https://unpkg.com/leaflet@1.9.4/dist/leaflet-src.esm.js"; // map api usage
import { getMetadataByKey, mergeMetadata, saveMetadata } from "/libs/apiHelper.js";

// --- 모듈 내부 상태 ---
let _leaflet = {
  map: null,
  layers: {
    base: null,

    // ✅ 로봇별 마커/정확도 원을 인덱스 키로 관리
    robot_markers: {},   // { [unitIndex: number]: L.Marker }
    robot_accuracy: {},  // { [unitIndex: number]: L.Circle }

    wpGroup: null,
    wpLine: null,
    gpGroup: null,
    gpLine: null,
    selHalo: null,
  },
  selectedMarker: null,

  // ✅ 로봇 공통 아이콘(미리 생성해 재사용)
  robotIcon: null,
};

// ---------------------- 공용 유틸 ----------------------
export async function _getSelectedUnitIndex1() {
  const res = await getMetadataByKey("currentSelectUnit");
  const idx0 = (res?.value ?? 0) | 0;
  return idx0 + 1; // 1,2,3...
}

//kiro via point
export async function _getWaypoints(unitIndex1) {
  const r = await getMetadataByKey(`robot_${unitIndex1}.waypoints`);
  return Array.isArray(r?.value) ? r.value : [];
}

//set gui goal point
export async function _getGoalpoints(unitIndex1) {
  const r = await getMetadataByKey(`robot_${unitIndex1}.goalpoint`);
  return Array.isArray(r?.value) ? r.value : [];
}

function _clearWaypointLayers() {
  if (_leaflet.layers.wpGroup) {
    _leaflet.layers.wpGroup.clearLayers();
    _leaflet.map.removeLayer(_leaflet.layers.wpGroup);
    _leaflet.layers.wpGroup = null;
  }
  if (_leaflet.layers.wpLine) {
    _leaflet.map.removeLayer(_leaflet.layers.wpLine);
    _leaflet.layers.wpLine = null;
  }
}

function _clearGoalpointLayers() {
  if (_leaflet.layers.gpGroup) {
    _leaflet.layers.gpGroup.clearLayers();
    _leaflet.map.removeLayer(_leaflet.layers.gpGroup);
    _leaflet.layers.gpGroup = null;
  }
  if (_leaflet.layers.gpLine) {
    _leaflet.map.removeLayer(_leaflet.layers.gpLine);
    _leaflet.layers.gpLine = null;
  }
  if (_leaflet.layers.selHalo) {
    _leaflet.map.removeLayer(_leaflet.layers.selHalo);
    _leaflet.layers.selHalo = null;
  }
  _leaflet.selectedMarker = null;
}

// 선택 하이라이트(오렌지 링)
function _highlightSelectedMarker(marker) {
  if (!_leaflet.map) return;

  // 기존 하이라이트 제거
  if (_leaflet.layers.selHalo) {
    _leaflet.map.removeLayer(_leaflet.layers.selHalo);
    _leaflet.layers.selHalo = null;
  }

  _leaflet.selectedMarker = marker;

  // 마커 주변에 오렌지 링 추가(시각적 선택 표시)
  const { lat, lng } = marker.getLatLng();
  _leaflet.layers.selHalo = L.circleMarker([lat, lng], {
    radius: 16, color: "orange", weight: 2,
    fillColor: "orange", fillOpacity: 0.15
  }).addTo(_leaflet.map);

  // 하이라이트가 항상 마커 좌표를 따라가도록 드래그 시 갱신
  marker.on("drag", () => {
    const pos = marker.getLatLng();
    _leaflet.layers.selHalo?.setLatLng(pos);
  });
}

// 현재 선택 마커 삭제(Del)
async function _deleteSelectedMarker() {
  const m = _leaflet.selectedMarker;
  if (!m) return;

  // 마커에 저장해둔 인덱스로 삭제
  const idx = m.__wpIndex;
  const unitIndex1 = await _getSelectedUnitIndex1();
  //const wps = await _getWaypoints(unitIndex1);
  const goalpoints = await _getGoalpoints(unitIndex1);

  if (Number.isInteger(idx) && idx >= 0 && idx < goalpoints.length) {
    const newGps = goalpoints.slice(0, idx).concat(goalpoints.slice(idx + 1));
    await mergeMetadata({ [`robot_${unitIndex1}`]: { goalpoint: newGps } });
    await saveMetadata();
    await updateGoalpointsForUnit(unitIndex1);
    _leaflet.selectedMarker = null;
    console.log(`[goalpoints] delete idx=${idx} robot_${unitIndex1}`);
  }
}

// ---------------------- Waypoints 렌더링 ----------------------
export async function updateWaypointsForUnit(unitIndex1) {
  if (!_leaflet.map) await initMap();

  const wps = await _getWaypoints(unitIndex1);
  _clearWaypointLayers(); // 기존 웨이포인트 레이어 제거
  if (!wps.length) return;

  _leaflet.layers.wpGroup = L.layerGroup().addTo(_leaflet.map);

  const latlngs = [];
  wps.forEach((pt, i) => {
    if (typeof pt?.lat !== "number" || typeof pt?.lng !== "number") return;
    const ll = [pt.lat, pt.lng];
    latlngs.push(ll);

    const m = L.marker(ll, {
        draggable: false,
        icon: L.icon({
        iconUrl: "/res/marker-icon.png",
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        shadowUrl: "/res/marker-shadow.png",
        shadowSize: [41, 41],
      })
    }).addTo(_leaflet.layers.wpGroup);

    // ✅ 항상 보이는 인덱스 라벨 (✔ Tooltip 영구 표시)
    m.bindTooltip(String(i + 1), {
      permanent: true,
      direction: "top",
      offset: L.point(0, -24),
      className: "wp-index-label",
    });

    // 인덱스 보관(삭제/이동 시 사용)
    m.__wpIndex = i;

    // 클릭 → 선택 표시
    m.on("click", (e) => {
      L.DomEvent.stop(e.originalEvent); // 전파 차단
      _highlightSelectedMarker(m);
    });
  });

  // 경로(점선)
  if (latlngs.length >= 2) {
    _leaflet.layers.wpLine = L.polyline(latlngs, { dashArray: "6,6" }).addTo(_leaflet.map);
  }
}

// ----------------------Goalpoints 렌더링 ----------------------
export async function updateGoalpointsForUnit(unitIndex1) {
  if (!_leaflet.map) await initMap();

  const gps = await _getGoalpoints(unitIndex1);
  _clearGoalpointLayers(); // 기존 골포인트 레이어 제거
  if (!gps.length) return;

  _leaflet.layers.gpGroup = L.layerGroup().addTo(_leaflet.map);

  const latlngs = [];
  gps.forEach((pt, i) => {
    if (typeof pt?.lat !== "number" || typeof pt?.lng !== "number") return;
    const ll = [pt.lat, pt.lng];
    latlngs.push(ll);

    const m = L.marker(ll, {
      draggable: true,
      icon: L.icon({
        iconUrl: "/res/maker-goal.png",
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        shadowUrl: "/res/marker-shadow.png",
        shadowSize: [41, 41],
      })
    }).addTo(_leaflet.layers.gpGroup);

    // ✅ 항상 보이는 인덱스 라벨 (✔ Tooltip 영구 표시)
    m.bindTooltip(String(i + 1), {
      permanent: true,
      direction: "top",
      offset: L.point(0, -24),
      className: "wp-index-label",
    });

    // 인덱스 보관(삭제/이동 시 사용)
    m.__wpIndex = i;

    // 클릭 → 선택 표시
    m.on("click", (e) => {
      L.DomEvent.stop(e.originalEvent); // 전파 차단
      _highlightSelectedMarker(m);
    });

    // 드래그 종료 → 좌표 저장 & 재렌더
    m.on("dragend", async (e) => {
      const { lat, lng } = e.target.getLatLng();
      const unitIdx1 = await _getSelectedUnitIndex1();
      const cur = await _getGoalpoints(unitIdx1);

      const idx = e.target.__wpIndex;
      if (Number.isInteger(idx) && idx >= 0 && idx < cur.length) {
        const newGps = cur.slice();
        newGps[idx] = { lat, lng };
        await mergeMetadata({ [`robot_${unitIdx1}`]: { goalpoint: newGps } });
        await saveMetadata();

        // 재렌더 후 동일 인덱스 마커 다시 선택(하이라이트 복구)
        await updateGoalpointsForUnit(unitIdx1);
        if (_leaflet.layers.gpGroup) {
          let k = 0;
          _leaflet.layers.gpGroup.eachLayer((lyr) => {
            if (lyr instanceof L.Marker) {
              lyr.__wpIndex = k;
              if (k === idx) _highlightSelectedMarker(lyr);
              k++;
            }
          });
        }
      }
    });
  });

  // 경로(점선)
  if (latlngs.length >= 2) {
    _leaflet.layers.gpLine = L.polyline(latlngs, { dashArray: "6,6" }).addTo(_leaflet.map);
  }
}

// ---------------------- Ctrl+클릭 추가/Del 삭제 ----------------------
export function enableCtrlClickToAppendGoalpoint() {
  if (!_leaflet.map) return;

  // Ctrl+클릭 → 현재 유닛에 골포인트 추가
  _leaflet.map.on("click", async (e) => {
    const ev = e?.originalEvent;
    if (!ev || !ev.ctrlKey) return;

    const { lat, lng } = e.latlng;
    const unitIndex1 = await _getSelectedUnitIndex1();
    const gps = await _getGoalpoints(unitIndex1);
    const newGps = [...gps, { lat, lng }];

    await mergeMetadata({ [`robot_${unitIndex1}`]: { goalpoint: newGps } });
    await saveMetadata();
    //await updateWaypointsForUnit(unitIndex1);
    await updateGoalpointsForUnit(unitIndex1);
    console.log(`[goalpoints] add robot_${unitIndex1}:`, { lat, lng });
  });

  // Delete 키:
  //  - Ctrl(or Cmd)+Delete  : 모든 웨이포인트 일괄 삭제(확인창)
  //  - Delete 단독          : 선택된 마커만 삭제
  document.addEventListener("keydown", async (e) => {
    if (e.key !== "Delete") return;
    e.preventDefault();

    // Ctrl(Win/Linux) 또는 Cmd(macOS) 눌린 경우 → 전체 삭제
    if (e.ctrlKey || e.metaKey) {
      const unitIndex1 = await _getSelectedUnitIndex1();
      const gps = await _getGoalpoints(unitIndex1);
      if (!gps.length) {
        alert("삭제할 골포인트가 없습니다.");
        return;
      }
      const ok = confirm(
        `정말로 robot_${unitIndex1}의 모든 골포인트(${gps.length})를 삭제할까요?`
      );
      if (!ok) return;

      try {
        await mergeMetadata({ [`robot_${unitIndex1}`]: { goalpoint: [] } });
        await saveMetadata();
        await updateGoalpointsForUnit(unitIndex1);
        _leaflet.selectedMarker = null;
        console.log(`[goalpoints] cleared all for robot_${unitIndex1}`);
      } catch (err) {
        console.error("[goalpoints] clear-all failed:", err);
        alert("골포인트 전체 삭제 실패");
      }
      return;
    }

    // Ctrl/Cmd 없이 Delete → 단일(선택된) 마커만 삭제
    await _deleteSelectedMarker();
  });
}

// ---------------------- 지도/상태 관련 기존 API 유지 ----------------------
export async function initMap(opts = {}) {
  if (_leaflet.map) return _leaflet.map;

  const center = Array.isArray(opts.center) ? opts.center : [37.5665, 126.9780];
  const zoom = Number.isFinite(opts.zoom) ? opts.zoom : 13;

  _leaflet.map = L.map("map-frame").setView(center, zoom);
  _leaflet.layers.base = L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    { maxZoom: 19, attribution: "&copy; OpenStreetMap contributors" }
  ).addTo(_leaflet.map);

  // ✅ 로봇 마커 아이콘(요청 경로 사용)
  _leaflet.robotIcon = L.icon({
    iconUrl: "res/marker_robot.png",   // ← 요청하신 경로 그대로
    iconSize: [48, 48],
    iconAnchor: [24, 30],              // 원점 중앙
    // shadowUrl: ... (필요 시)
  });

  return _leaflet.map;
}

function _setOrUpdateRobot(unitIndex, lat, lng, acc = null, center = true) {
  if (!_leaflet.map) return;

  let m = _leaflet.layers.robot_markers[unitIndex];
  if (!m) {
    m = L.marker([lat, lng], {
      icon: _leaflet.robotIcon || undefined,
      title: `robot_${unitIndex}`,
      zIndexOffset: 1000, // (선택) 위로 올리고 싶으면
    }).addTo(_leaflet.map);

    // ✅ 아이콘 위에 굵고 큰 “호기 번호” 항상 표시
    m.bindTooltip(`${unitIndex}`, {
      permanent: true,
      direction: "top",
      offset: L.point(0, -22),     // 아이콘 윗부분 살짝 띄우기
      className: "robot-index-label",
      opacity: 1,
    });

    _leaflet.layers.robot_markers[unitIndex] = m;
  } else {
    m.setLatLng([lat, lng]);

    // (안전) 이미 라벨이 없다면 붙여주기
    if (!m.getTooltip()) {
      m.bindTooltip(`${unitIndex}`, {
        permanent: true,
        direction: "top",
        offset: L.point(0, -22),
        className: "robot-index-label",
        opacity: 1,
      });
    } else {
      m.setTooltipContent(`${unitIndex}`);
    }
  }

  // 정확도 원 갱신
  if (Number.isFinite(acc) && acc > 0) {
    let c = _leaflet.layers.robot_accuracy[unitIndex];
    if (!c) {
      c = L.circle([lat, lng], { radius: acc }).addTo(_leaflet.map);
      _leaflet.layers.robot_accuracy[unitIndex] = c;
    } else {
      c.setLatLng([lat, lng]);
      c.setRadius(acc);
    }
  } else if (_leaflet.layers.robot_accuracy[unitIndex]) {
    _leaflet.map.removeLayer(_leaflet.layers.robot_accuracy[unitIndex]);
    delete _leaflet.layers.robot_accuracy[unitIndex];
  }

  if (center) {
    _leaflet.map.setView([lat, lng], _leaflet.map.getZoom(), { animate: false });
  }
}

//get robot GPS position
export async function getUnitLatLngFromMetadata(unitIndex) {
  const i = unitIndex;
  try {
    const resPos = await getMetadataByKey(`robot_${i}.position`);
    if (resPos?.r === "ok" && resPos?.value && typeof resPos.value === "object") {
      const { lat, lng, acc } = resPos.value;
      if (typeof lat === "number" && typeof lng === "number") {
        return { lat, lng, acc: (typeof acc === "number" ? acc : null) };
      }
    }
  } catch (_) { }

  try {
    const [resLat, resLng] = await Promise.all([
      getMetadataByKey(`robot_${i}.lat`),
      getMetadataByKey(`robot_${i}.lon`),
    ]);
    const lat = resLat?.r === "ok" ? resLat.value : null;
    const lng = resLng?.r === "ok" ? resLng.value : null;
    if (typeof lat === "number" && typeof lng === "number") {
      return { lat, lng, acc: null };
    }
  } catch (_) { }

  return null;
}

//clear map
export function destroyMap() {
  if (_leaflet.map) {
    // 로봇 레이어 전부 제거
    clearAllRobots();

    // 나머지 레이어/맵 정리
    if (_leaflet.layers.wpGroup) _leaflet.layers.wpGroup.clearLayers();
    if (_leaflet.layers.wpLine) _leaflet.map.removeLayer(_leaflet.layers.wpLine);
    
    if (_leaflet.layers.gpGroup) _leaflet.layers.gpGroup.clearLayers();
    if (_leaflet.layers.gpLine) _leaflet.map.removeLayer(_leaflet.layers.gpLine);

    if (_leaflet.layers.selHalo) _leaflet.map.removeLayer(_leaflet.layers.selHalo);
    if (_leaflet.layers.base) _leaflet.map.removeLayer(_leaflet.layers.base);

    _leaflet.map.remove();
    _leaflet = {
      map: null,
      layers: { base: null, robot_markers: {}, robot_accuracy: {}, wpGroup: null, wpLine: null, gpGroup:null, gpLine:null, selHalo: null },
      selectedMarker: null,
      robotIcon: null,
    };
  }
}

// 배너 표시/숨김 + 상태 렌더 (기존 index.js와의 호환 유지) >> map api
export function showNoLocationBanner(text = "위치 데이터 없음") {
  if (!_leaflet.map) return;

  if (_leaflet.layers.noDataCtl) {
    const el = _leaflet.layers.noDataCtl._container?.querySelector(".no-data-text");
    if (el) el.textContent = text;
    return;
  }

  const NoDataControl = L.Control.extend({
    onAdd: function () {
      const div = L.DomUtil.create("div", "leaflet-control no-data-banner");
      div.innerHTML = `<span class="no-data-text">${text}</span>`;
      L.DomEvent.disableClickPropagation(div);
      return div;
    },
  });

  _leaflet.layers.noDataCtl = new NoDataControl({ position: "topright" });
  _leaflet.map.addControl(_leaflet.layers.noDataCtl);

  if (_leaflet.layers.marker) { _leaflet.map.removeLayer(_leaflet.layers.marker); _leaflet.layers.marker = null; }
  if (_leaflet.layers.accuracy) { _leaflet.map.removeLayer(_leaflet.layers.accuracy); _leaflet.layers.accuracy = null; }
}

export function hideNoLocationBanner() {
  if (_leaflet.map && _leaflet.layers.noDataCtl) {
    _leaflet.map.removeControl(_leaflet.layers.noDataCtl);
    _leaflet.layers.noDataCtl = null;
  }
}

export function updateMapWithStatusData(unitIndex, status, center = true) {
  if (!_leaflet.map || !status) return;

  const lat = Number(status.latitude);
  const lng = Number(status.longitude);
  const acc = Number(status.accuracy); // 없으면 NaN

  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;

  // hideNoLocationBanner();
  _setOrUpdateRobot(unitIndex, lat, lng, Number.isFinite(acc) ? acc : null, center);
}

export function removeRobot(unitIndex) {
  const m = _leaflet.layers.robot_markers[unitIndex];
  if (m) {
    _leaflet.map.removeLayer(m);
    delete _leaflet.layers.robot_markers[unitIndex];
  }
  const c = _leaflet.layers.robot_accuracy[unitIndex];
  if (c) {
    _leaflet.map.removeLayer(c);
    delete _leaflet.layers.robot_accuracy[unitIndex];
  }
}

export function clearAllRobots() {
  Object.values(_leaflet.layers.robot_markers).forEach(m => _leaflet.map.removeLayer(m));
  Object.values(_leaflet.layers.robot_accuracy).forEach(c => _leaflet.map.removeLayer(c));
  _leaflet.layers.robot_markers = {};
  _leaflet.layers.robot_accuracy = {};
}
