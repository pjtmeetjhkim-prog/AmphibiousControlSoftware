(function () {
  let map, robotMarker, pyBridge = null;

  function cssAngleFromHeading(headingDeg) {
    const h = (headingDeg || 0);
    return 90 - h;
  }
  function makeRobotIcon(headingDeg) {
    const html =
      '<div class="robot-wrap">' +
        '<div class="robot-arrow" style="transform: translate(-50%, -60%) rotate(' + cssAngleFromHeading(headingDeg) + 'deg)"></div>' +
        '<div class="robot-core"></div>' +
      '</div>';
    return L.divIcon({ html, className: '', iconSize: [36,36], iconAnchor: [18,18] });
  }

  function initMap(lat, lon, zoom) {
    map = L.map('map').setView([lat, lon], zoom);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 20,
      attribution: '&copy; OpenStreetMap'
    }).addTo(map);

    if (typeof qt !== "undefined") {
      new QWebChannel(qt.webChannelTransport, function (channel) {
        pyBridge = channel.objects.pyBridge;
      });
    }

    const onStart = () => { if (pyBridge) pyBridge.onDrag(true); };
    const onEnd   = () => { if (pyBridge) pyBridge.onDrag(false); };
    map.on('movestart', onStart);
    map.on('dragstart', onStart);
    map.on('zoomstart', onStart);
    map.on('moveend', onEnd);
    map.on('dragend', onEnd);
    map.on('zoomend', onEnd);
  }

  function updateRobot(lat, lon, headingDeg, center=true) {
    if (!map) return;
    const pos = [lat, lon];
    if (!robotMarker) {
      robotMarker = L.marker(pos, { icon: makeRobotIcon(headingDeg) }).addTo(map);
    } else {
      robotMarker.setLatLng(pos);
      robotMarker.setIcon(makeRobotIcon(headingDeg));
    }
    if (center) map.setView(pos, map.getZoom(), { animate: false });
  }

  // ✅ 전역 바인딩 (PySide에서 runJavaScript로 호출 가능하게)
  window.initMap = initMap;
  window.updateRobot = updateRobot;
})();
