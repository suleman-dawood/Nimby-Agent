"use client";

import {
  Container,
  Title,
  Text,
  Stack,
  Grid,
  Alert,
  Chip,
  Group,
} from "@mantine/core";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import MapProvider from "@/components/map/MapProvider";
import ProposalMap from "@/components/map/ProposalMap";
import PPCard from "@/components/proposals/PPCard";
import type { NearbyPP, NearbyResponse } from "@/lib/api";

const STAGE_COLORS: Record<string, string> = {
  "Under Exhibition": "green",
  "Under Assessment": "orange",
  "Post-Exhibition": "blue",
  "Pre-Gateway": "gray",
  "Exhibition Closed": "red",
  "Finalised": "violet",
};

interface SearchData extends NearbyResponse {
  lat: number;
  lng: number;
  address: string;
}

export default function ResultsPage() {
  const router = useRouter();
  const [data, setData] = useState<SearchData | null>(null);
  const [activeStages, setActiveStages] = useState<string[]>([]);
  const [compareSelection, setCompareSelection] = useState<string[]>([]);

  useEffect(() => {
    const stored = sessionStorage.getItem("nimby_search");
    if (stored) {
      const parsed = JSON.parse(stored);
      setData(parsed);
      // Default: all stages active
      const allStages = [...new Set(
        [...(parsed.results || []), ...(parsed.policy_results || [])]
          .map((pp: NearbyPP) => pp.stage)
          .filter(Boolean)
      )] as string[];
      setActiveStages(allStages);
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
  const allStages = [...new Set(allPPs.map((pp) => pp.stage).filter(Boolean))] as string[];

  const filteredResults = data.results.filter((pp) => !pp.stage || activeStages.includes(pp.stage));
  const filteredPolicy = data.policy_results.filter((pp) => !pp.stage || activeStages.includes(pp.stage));
  const filteredAll = [...filteredResults, ...filteredPolicy];

  const toggleStage = (stage: string) => {
    setActiveStages((prev) =>
      prev.includes(stage) ? prev.filter((s) => s !== stage) : [...prev, stage]
    );
  };

  const handlePPClick = (pp: NearbyPP) => {
    router.push(`/brief/${pp.pp_number}`);
  };

  return (
    <Container size="lg" py="md" className="results-container">
      <Stack gap="md">
        <div>
          <Text
            style={{
              fontFamily: "'Public Sans', Arial, sans-serif",
              fontSize: 11,
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              color: "var(--nsw-grey-04)",
              marginBottom: 4,
            }}
          >
            Search Results
          </Text>
          <Title order={2} className="results-title">
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
            {filteredAll.length} proposal{filteredAll.length !== 1 && "s"}{" "}
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

        {/* Stage Filters */}
        {allStages.length > 1 && (
          <Group gap={6} wrap="wrap">
            {allStages.map((stage) => (
              <Chip
                key={stage}
                checked={activeStages.includes(stage)}
                onChange={() => toggleStage(stage)}
                color={STAGE_COLORS[stage] || "gray"}
                size="xs"
              >
                {stage}
              </Chip>
            ))}
          </Group>
        )}

        {/* Compare bar */}
        {compareSelection.length > 0 && (
          <div style={{
            background: "var(--nsw-brand-dark)", color: "var(--nsw-white)", padding: "8px 16px",
            display: "flex", justifyContent: "space-between", alignItems: "center",
            fontFamily: "'Public Sans', sans-serif", fontSize: 12,
          }}>
            <span>Compare: {compareSelection.join(" vs ")}{compareSelection.length < 2 ? " — select one more" : ""}</span>
            <Group gap={8}>
              {compareSelection.length === 2 && (
                <button
                  onClick={() => router.push(`/compare?pp1=${compareSelection[0]}&pp2=${compareSelection[1]}`)}
                  style={{ background: "var(--nsw-white)", color: "var(--nsw-brand-dark)", border: "none", padding: "4px 12px", fontWeight: 600, cursor: "pointer", fontFamily: "'Public Sans', sans-serif", fontSize: 11 }}
                >
                  Compare
                </button>
              )}
              <button
                onClick={() => setCompareSelection([])}
                style={{ background: "none", color: "var(--nsw-white)", border: "1px solid rgba(255,255,255,0.4)", padding: "4px 8px", cursor: "pointer", fontSize: 11 }}
              >
                Clear
              </button>
            </Group>
          </div>
        )}

        <MapProvider>
          <ProposalMap
            center={{ lat: data.lat, lng: data.lng }}
            markers={filteredAll}
            onMarkerClick={handlePPClick}
          />
        </MapProvider>

        {filteredResults.length > 0 && (
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
              {filteredResults.map((pp) => (
                <Grid.Col key={pp.pp_number} span={{ base: 12, sm: 6, md: 4 }}>
                  <PPCard
                    pp={pp}
                    onClick={() => handlePPClick(pp)}
                    compareSelected={compareSelection.includes(pp.pp_number)}
                    onCompareToggle={(ppn) => setCompareSelection((prev) =>
                      prev.includes(ppn) ? prev.filter((p) => p !== ppn)
                        : prev.length < 2 ? [...prev, ppn] : prev
                    )}
                  />
                </Grid.Col>
              ))}
            </Grid>
          </>
        )}

        {filteredPolicy.length > 0 && (
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
              {filteredPolicy.map((pp) => (
                <Grid.Col key={pp.pp_number} span={{ base: 12, sm: 6, md: 4 }}>
                  <PPCard
                    pp={pp}
                    onClick={() => handlePPClick(pp)}
                    compareSelected={compareSelection.includes(pp.pp_number)}
                    onCompareToggle={(ppn) => setCompareSelection((prev) =>
                      prev.includes(ppn) ? prev.filter((p) => p !== ppn)
                        : prev.length < 2 ? [...prev, ppn] : prev
                    )}
                  />
                </Grid.Col>
              ))}
            </Grid>
          </>
        )}

        {filteredAll.length === 0 && (
          <div style={{ border: "2px dashed var(--nsw-grey-03)", padding: 32, textAlign: "center" }}>
            <Text style={{ fontFamily: "'Public Sans', sans-serif", fontSize: 16, fontWeight: 600, color: "var(--nsw-brand-dark)", marginBottom: 8 }}>
              No planning proposals found
            </Text>
            <Text style={{ fontSize: 13, color: "var(--nsw-grey-04)" }}>
              {allPPs.length === 0
                ? "No proposals found within your search radius. Try expanding the radius or searching a different address."
                : "No proposals match your selected stage filters. Try enabling more filters above."}
            </Text>
          </div>
        )}
      </Stack>
    </Container>
  );
}
