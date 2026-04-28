"use client";

import {
  Container,
  Title,
  Text,
  Stack,
  Grid,
  Alert,
} from "@mantine/core";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import MapProvider from "@/components/map/MapProvider";
import ProposalMap from "@/components/map/ProposalMap";
import PPCard from "@/components/proposals/PPCard";
import type { NearbyPP, NearbyResponse } from "@/lib/api";

interface SearchData extends NearbyResponse {
  lat: number;
  lng: number;
  address: string;
}

export default function ResultsPage() {
  const router = useRouter();
  const [data, setData] = useState<SearchData | null>(null);

  useEffect(() => {
    const stored = sessionStorage.getItem("nimby_search");
    if (stored) {
      setData(JSON.parse(stored));
    }
  }, []);

  if (!data) {
    return (
      <Container size="md" py="xl">
        <Alert color="yellow" title="No results">
          Search for an address first.
        </Alert>
      </Container>
    );
  }

  const allPPs = [...data.results, ...data.policy_results];

  const handlePPClick = (pp: NearbyPP) => {
    router.push(`/brief/${pp.pp_number}`);
  };

  return (
    <Container size="lg" py="xl">
      <Stack gap="lg">
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
            Search Results
          </Text>
          <Title order={2} style={{ fontSize: 28 }}>
            Proposals near {data.address}
          </Title>
          <div
            style={{
              width: 60,
              height: 3,
              background: "var(--nsw-brand-dark)",
              margin: "8px 0 4px",
            }}
          />
          <Text style={{ fontSize: 13, color: "var(--nsw-text-light)" }}>
            {data.results.length} proposal{data.results.length !== 1 && "s"}{" "}
            within range
            {data.lga && (
              <span>
                {" "}
                &mdash;{" "}
                <span style={{ fontWeight: 600 }}>{data.lga}</span>
              </span>
            )}
          </Text>
        </div>

        <MapProvider>
          <ProposalMap
            center={{ lat: data.lat, lng: data.lng }}
            markers={allPPs}
            onMarkerClick={handlePPClick}
          />
        </MapProvider>

        {data.results.length > 0 && (
          <>
            <Text
              style={{
                fontFamily: "'Public Sans', Arial, sans-serif",
                fontSize: 11,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                color: "var(--nsw-grey-04)",
                borderBottom: "2px solid var(--nsw-brand-dark)",
                paddingBottom: 8,
              }}
            >
              Nearby Proposals
            </Text>
            <Grid>
              {data.results.map((pp) => (
                <Grid.Col key={pp.pp_number} span={{ base: 12, sm: 6, md: 4 }}>
                  <PPCard pp={pp} onClick={() => handlePPClick(pp)} />
                </Grid.Col>
              ))}
            </Grid>
          </>
        )}

        {data.policy_results.length > 0 && (
          <>
            <Text
              style={{
                fontFamily: "'Public Sans', Arial, sans-serif",
                fontSize: 11,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                color: "var(--nsw-grey-04)",
                borderBottom: "2px solid var(--nsw-brand-dark)",
                paddingBottom: 8,
                marginTop: 16,
              }}
            >
              LGA-Wide Policy Proposals
            </Text>
            <Grid>
              {data.policy_results.map((pp) => (
                <Grid.Col key={pp.pp_number} span={{ base: 12, sm: 6, md: 4 }}>
                  <PPCard pp={pp} onClick={() => handlePPClick(pp)} />
                </Grid.Col>
              ))}
            </Grid>
          </>
        )}

        {allPPs.length === 0 && (
          <Alert color="blue" title="No proposals found">
            No planning proposals are currently on exhibition near your address.
          </Alert>
        )}
      </Stack>
    </Container>
  );
}
