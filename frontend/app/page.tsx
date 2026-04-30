"use client";

import { Container, Title, Text, Stack, Alert } from "@mantine/core";
import { useRouter } from "next/navigation";
import { useState } from "react";
import MapProvider from "@/components/map/MapProvider";
import AddressSearch from "@/components/map/AddressSearch";
import ProposalMap from "@/components/map/ProposalMap";
import { searchNearby } from "@/lib/api";

export default function SearchPage() {
  const router = useRouter();
  const [location, setLocation] = useState<{
    lat: number;
    lng: number;
    address: string;
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handlePlaceSelected = async (
    lat: number,
    lng: number,
    address: string
  ) => {
    setLocation({ lat, lng, address });
    setLoading(true);
    setError(null);

    try {
      const data = await searchNearby(lat, lng);
      sessionStorage.setItem(
        "nimby_search",
        JSON.stringify({ lat, lng, address, ...data })
      );
      router.push("/results");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container size="md" py="xl">
      <Stack gap="xl">
        <div>
          <Text
            style={{
              fontFamily: "'Public Sans', Arial, sans-serif",
              fontSize: 11,
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              color: "var(--nsw-grey-04)",
              marginBottom: 8,
            }}
          >
            Planning Proposals on Exhibition
          </Text>
          <Title
            order={1}
            mb="xs"
            style={{ fontSize: 36, lineHeight: 1.15 }}
          >
            What&apos;s being planned near you?
          </Title>
          <div
            style={{
              width: 60,
              height: 3,
              background: "var(--nsw-brand-dark)",
            }}
          />
        </div>

        <div
          className="search-box"
          style={{
            border: "2px solid var(--nsw-brand-dark)",
            padding: 24,
            background: "var(--nsw-white)",
          }}
        >
          <MapProvider>
            <Stack gap="md">
              <AddressSearch
                onPlaceSelected={handlePlaceSelected}
                loading={loading}
              />
              <ProposalMap
                center={
                  location
                    ? { lat: location.lat, lng: location.lng }
                    : undefined
                }
              />
            </Stack>
          </MapProvider>
        </div>

        {error && (
          <Alert color="red" title="Error">
            {error}
          </Alert>
        )}
      </Stack>
    </Container>
  );
}
