import { useEffect } from 'react';
import { MapContainer, Polyline, TileLayer, useMap } from 'react-leaflet';

function FitBounds({ points }) {
  const map = useMap();

  useEffect(() => {
    if (!points.length) return;
    const latlngs = points.map((p) => [p[0], p[1]]);
    map.fitBounds(latlngs, { padding: [20, 20] });
  }, [map, points]);

  return null;
}

export default function RouteMap({ points }) {
  if (!points || !points.length) {
    return <div className="route-placeholder">Route preview</div>;
  }

  const lat = points[0][0];
  const lng = points[0][1];

  return (
    <MapContainer
      center={[lat, lng]}
      zoom={13}
      className="route-map"
      scrollWheelZoom={false}
      dragging={false}
      zoomControl={false}
      attributionControl
    >
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        attribution="&copy; OpenStreetMap contributors &copy; CARTO"
      />
      <Polyline
        positions={points.map((p) => [p[0], p[1]])}
        pathOptions={{ color: '#0B1220', weight: 7, opacity: 0.7 }}
      />
      <Polyline
        positions={points.map((p) => [p[0], p[1]])}
        pathOptions={{ color: '#0EA5E9', weight: 4, opacity: 0.95 }}
      />
      <FitBounds points={points} />
    </MapContainer>
  );
}
