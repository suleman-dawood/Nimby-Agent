"use client";

import { Button, Group, Slider, Stack, Text, TextInput } from "@mantine/core";
import { useState } from "react";
import { createWatcher } from "@/lib/api";

interface Props {
  onCreated: () => void;
}

export default function WatchForm({ onCreated }: Props) {
  const [address, setAddress] = useState("");
  const [radius, setRadius] = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!address.trim()) return;
    setLoading(true);
    setError(null);

    try {
      // Geocode the address first
      const { geocode } = await import("@/lib/api");
      const geo = await geocode(address);

      await createWatcher({
        address,
        lat: geo.lat,
        lng: geo.lng,
        radius_km: radius,
      });

      setAddress("");
      setRadius(5);
      onCreated();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create watcher");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Stack gap="sm">
      <TextInput
        label="Address to watch"
        placeholder="Enter an address in NSW..."
        value={address}
        onChange={(e) => setAddress(e.currentTarget.value)}
        style={{ fontFamily: "'Public Sans', sans-serif" }}
      />
      <div>
        <Text size="sm" mb={4}>Radius: {radius} km</Text>
        <Slider
          value={radius}
          onChange={setRadius}
          min={1}
          max={10}
          step={1}
          marks={[
            { value: 1, label: "1km" },
            { value: 5, label: "5km" },
            { value: 10, label: "10km" },
          ]}
        />
      </div>
      {error && <Text color="red" size="sm">{error}</Text>}
      <Group>
        <Button onClick={handleSubmit} loading={loading}>
          Watch this address
        </Button>
      </Group>
    </Stack>
  );
}
