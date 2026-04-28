"use client";

import { LoadScript } from "@react-google-maps/api";

const LIBRARIES: ("places")[] = ["places"];

export default function MapProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_KEY || "";

  if (!apiKey) {
    return (
      <div
        style={{
          padding: 32,
          background: "var(--paper-warm)",
          border: "2px solid var(--rule)",
          textAlign: "center",
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 12,
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          color: "var(--ink-faint)",
        }}
      >
        Map unavailable — set NEXT_PUBLIC_GOOGLE_MAPS_KEY
      </div>
    );
  }

  return (
    <LoadScript googleMapsApiKey={apiKey} libraries={LIBRARIES}>
      {children}
    </LoadScript>
  );
}
