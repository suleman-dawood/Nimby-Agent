"use client";

import { GoogleMap, Marker, Circle, InfoWindow } from "@react-google-maps/api";
import { useState, useCallback } from "react";
import type { NearbyPP } from "@/lib/api";

const MAP_STYLES = {
  width: "100%",
  height: "420px",
  border: "2px solid var(--rule-heavy)",
};

const MAP_OPTIONS: google.maps.MapOptions = {
  zoomControl: true,
  zoomControlOptions: {
    position: typeof window !== "undefined" ? google?.maps?.ControlPosition?.RIGHT_BOTTOM : undefined,
  },
  mapTypeControl: false,
  streetViewControl: false,
  fullscreenControl: true,
  styles: [
    { elementType: "geometry", stylers: [{ color: "#e8e4dd" }] },
    { elementType: "labels.text.fill", stylers: [{ color: "#4a4a4a" }] },
    { elementType: "labels.text.stroke", stylers: [{ color: "#f5f2ed" }] },
    {
      featureType: "road",
      elementType: "geometry",
      stylers: [{ color: "#d4cfc7" }],
    },
    {
      featureType: "road",
      elementType: "geometry.stroke",
      stylers: [{ color: "#c4bfb6" }],
    },
    {
      featureType: "water",
      elementType: "geometry",
      stylers: [{ color: "#b8ccd4" }],
    },
    {
      featureType: "poi.park",
      elementType: "geometry",
      stylers: [{ color: "#c8d4c0" }],
    },
    {
      featureType: "poi",
      elementType: "labels",
      stylers: [{ visibility: "off" }],
    },
  ],
};

const DEFAULT_CENTER = { lat: -33.87, lng: 151.21 };

interface Props {
  center?: { lat: number; lng: number };
  markers?: NearbyPP[];
  radiusKm?: number;
  onMarkerClick?: (pp: NearbyPP) => void;
}

export default function ProposalMap({
  center = DEFAULT_CENTER,
  markers = [],
  radiusKm = 10,
  onMarkerClick,
}: Props) {
  const [selected, setSelected] = useState<NearbyPP | null>(null);

  const onLoad = useCallback(
    (map: google.maps.Map) => {
      if (markers.length > 0) {
        const bounds = new google.maps.LatLngBounds();
        bounds.extend(center);
        markers.forEach((pp) => {
          if (pp.latitude && pp.longitude) {
            bounds.extend({ lat: pp.latitude, lng: pp.longitude });
          }
        });
        map.fitBounds(bounds, 50);
      }
    },
    [markers, center]
  );

  return (
    <GoogleMap
      mapContainerStyle={MAP_STYLES}
      center={center}
      zoom={12}
      onLoad={onLoad}
      options={MAP_OPTIONS}
    >
      <Marker
        position={center}
        icon={{
          path: google.maps.SymbolPath.CIRCLE,
          scale: 8,
          fillColor: "#b8432f",
          fillOpacity: 1,
          strokeColor: "#1a1a1a",
          strokeWeight: 2,
        }}
      />

      <Circle
        center={center}
        radius={radiusKm * 1000}
        options={{
          fillColor: "#1a1a1a",
          fillOpacity: 0.04,
          strokeColor: "#1a1a1a",
          strokeOpacity: 0.2,
          strokeWeight: 1,
        }}
      />

      {markers.map(
        (pp) =>
          pp.latitude &&
          pp.longitude && (
            <Marker
              key={pp.pp_number}
              position={{ lat: pp.latitude, lng: pp.longitude }}
              icon={{
                path: google.maps.SymbolPath.BACKWARD_CLOSED_ARROW,
                scale: 5,
                fillColor: "#1a1a1a",
                fillOpacity: 0.9,
                strokeColor: "#1a1a1a",
                strokeWeight: 1,
              }}
              onClick={() => {
                setSelected(pp);
                onMarkerClick?.(pp);
              }}
            />
          )
      )}

      {selected && selected.latitude && selected.longitude && (
        <InfoWindow
          position={{ lat: selected.latitude, lng: selected.longitude }}
          onCloseClick={() => setSelected(null)}
        >
          <div
            style={{
              fontFamily: "'IBM Plex Sans', sans-serif",
              padding: "8px 4px",
              maxWidth: 220,
            }}
          >
            <div
              style={{
                fontFamily: "'IBM Plex Mono', monospace",
                fontSize: 11,
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                marginBottom: 4,
              }}
            >
              {selected.pp_number}
            </div>
            {selected.title && (
              <div style={{ fontSize: 13, lineHeight: 1.4, marginBottom: 4 }}>
                {selected.title.slice(0, 100)}
              </div>
            )}
            <div
              style={{
                fontSize: 11,
                color: "var(--ink-faint)",
                borderTop: "1px solid var(--rule)",
                paddingTop: 4,
                marginTop: 4,
              }}
            >
              {selected.distance_km} km away
            </div>
          </div>
        </InfoWindow>
      )}
    </GoogleMap>
  );
}
