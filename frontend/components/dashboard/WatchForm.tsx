"use client";

import { Button, Group, Slider, Stack, Text } from "@mantine/core";
import { useState, useRef, useEffect } from "react";
import { createWatcher } from "@/lib/api";

interface Props {
  onCreated: () => void;
}

export default function WatchForm({ onCreated }: Props) {
  const [address, setAddress] = useState("");
  const [radius, setRadius] = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lat, setLat] = useState<number | null>(null);
  const [lng, setLng] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Google Places Autocomplete
  useEffect(() => {
    if (!inputRef.current || typeof window === "undefined") return;
    const g = (window as any).google;
    if (!g?.maps?.places) return;

    const nswBounds = new g.maps.LatLngBounds(
      { lat: -37.51, lng: 140.99 },
      { lat: -28.15, lng: 153.64 },
    );
    const autocomplete = new g.maps.places.Autocomplete(inputRef.current, {
      componentRestrictions: { country: "au" },
      types: ["address"],
      bounds: nswBounds,
      strictBounds: true,
    });

    autocomplete.addListener("place_changed", () => {
      const place = autocomplete.getPlace();
      if (place?.formatted_address) {
        setAddress(place.formatted_address);
      }
      if (place?.geometry?.location) {
        setLat(place.geometry.location.lat());
        setLng(place.geometry.location.lng());
      }
    });
  }, []);

  const handleSubmit = async () => {
    if (!address.trim()) return;
    setLoading(true);
    setError(null);

    try {
      let finalLat = lat;
      let finalLng = lng;

      // If no coords from autocomplete, geocode manually
      if (!finalLat || !finalLng) {
        const { geocode } = await import("@/lib/api");
        const geo = await geocode(address);
        finalLat = geo.lat;
        finalLng = geo.lng;
      }

      await createWatcher({
        address,
        lat: finalLat!,
        lng: finalLng!,
        radius_km: radius,
      });

      setAddress("");
      setRadius(5);
      setLat(null);
      setLng(null);
      if (inputRef.current) inputRef.current.value = "";
      onCreated();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create watcher");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Stack gap="md">
      <div>
        <Text size="sm" fw={500} mb={4}>Address to watch</Text>
        <input
          ref={inputRef}
          type="text"
          placeholder="Enter an address in NSW..."
          defaultValue={address}
          onChange={(e) => setAddress(e.target.value)}
          style={{
            width: "100%",
            padding: "8px 12px",
            border: "2px solid var(--nsw-grey-03)",
            fontFamily: "'Public Sans', sans-serif",
            fontSize: 14,
            outline: "none",
          }}
          onFocus={(e) => (e.target.style.borderColor = "var(--nsw-brand-dark)")}
          onBlur={(e) => (e.target.style.borderColor = "var(--nsw-grey-03)")}
        />
      </div>
      <div style={{ paddingBottom: 16 }}>
        <Text size="sm" mb={8}>Radius: {radius} km</Text>
        <Slider
          value={radius}
          onChange={setRadius}
          min={1}
          max={50}
          step={1}
          marks={[
            { value: 1, label: "1km" },
            { value: 10, label: "10km" },
            { value: 25, label: "25km" },
            { value: 50, label: "50km" },
          ]}
        />
      </div>
      {error && <Text c="red" size="sm">{error}</Text>}
      <Group>
        <Button onClick={handleSubmit} loading={loading}>
          Watch this address
        </Button>
      </Group>
    </Stack>
  );
}
