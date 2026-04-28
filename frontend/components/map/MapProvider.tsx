"use client";

import { useJsApiLoader } from "@react-google-maps/api";

const LIBRARIES: ("places")[] = ["places"];

export default function MapProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_KEY || "";

  const { isLoaded, loadError } = useJsApiLoader({
    googleMapsApiKey: apiKey,
    libraries: LIBRARIES,
  });

  if (!apiKey) {
    return (
      <div
        style={{
          padding: 32,
          background: "var(--nsw-grey-01)",
          border: "2px solid var(--nsw-grey-02)",
          textAlign: "center",
          fontFamily: "'Public Sans', Arial, sans-serif",
          fontSize: 12,
          color: "var(--nsw-grey-04)",
        }}
      >
        Map unavailable — set NEXT_PUBLIC_GOOGLE_MAPS_KEY
      </div>
    );
  }

  if (loadError) {
    return (
      <div style={{ padding: 32, textAlign: "center", color: "var(--nsw-error)" }}>
        Failed to load Google Maps
      </div>
    );
  }

  if (!isLoaded) {
    return (
      <div style={{ padding: 32, textAlign: "center", color: "var(--nsw-grey-04)" }}>
        Loading map...
      </div>
    );
  }

  return <>{children}</>;
}
