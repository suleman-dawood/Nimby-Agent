"use client";

import { GoogleMap, Marker, Circle, InfoWindow } from "@react-google-maps/api";
import { useState, useCallback, useMemo } from "react";
import type { NearbyPP } from "@/lib/api";

const MAP_STYLES = {
  width: "100%",
  height: "420px",
  border: "2px solid var(--nsw-brand-dark)",
};

const MAP_VISUAL_STYLES = [
  { elementType: "geometry", stylers: [{ color: "#f2f2f2" }] },
  { elementType: "labels.text.fill", stylers: [{ color: "#22272B" }] },
  { elementType: "labels.text.stroke", stylers: [{ color: "#ffffff" }] },
  { featureType: "road", elementType: "geometry", stylers: [{ color: "#e4e4e6" }] },
  { featureType: "road.highway", elementType: "geometry", stylers: [{ color: "#CDD3D6" }] },
  { featureType: "water", elementType: "geometry", stylers: [{ color: "#CBEDFD" }] },
  { featureType: "poi.park", elementType: "geometry", stylers: [{ color: "#d4e8d0" }] },
  { featureType: "poi", elementType: "labels", stylers: [{ visibility: "off" }] },
];

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

  const mapOptions = useMemo(() => ({
    zoomControl: true,
    mapTypeControl: false,
    streetViewControl: false,
    fullscreenControl: true,
    styles: MAP_VISUAL_STYLES,
  }), []);

  const userIcon = useMemo(() => {
    if (typeof window === "undefined" || !window.google) return undefined;
    return {
      path: google.maps.SymbolPath.CIRCLE,
      scale: 8,
      fillColor: "#D7153A",
      fillOpacity: 1,
      strokeColor: "#002664",
      strokeWeight: 2,
    };
  }, []);

  const ppIcon = useMemo(() => {
    if (typeof window === "undefined" || !window.google) return undefined;
    return {
      path: google.maps.SymbolPath.BACKWARD_CLOSED_ARROW,
      scale: 5,
      fillColor: "#002664",
      fillOpacity: 0.9,
      strokeColor: "#002664",
      strokeWeight: 1,
    };
  }, []);

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
      options={mapOptions}
    >
      <Marker position={center} icon={userIcon} />

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
              icon={ppIcon}
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
              fontFamily: "'Public Sans', Arial, sans-serif",
              padding: "8px 4px",
              maxWidth: 220,
            }}
          >
            <div
              style={{
                fontFamily: "'Public Sans', Arial, sans-serif",
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
                color: "var(--nsw-grey-04)",
                borderTop: "1px solid var(--nsw-grey-02)",
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
