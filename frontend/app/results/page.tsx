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
  const [compareMode, setCompareMode] = useState(false);
  const [compareSelection, setCompareSelection] = useState<string[]>([]);

  useEffect(() => {
    const stored = sessionStorage.getItem("nimby_search");
    if (stored) {
      const parsed = JSON.parse(stored);
      setData(parsed);
      const allStages = [...new Set(
        [...(parsed.results || []), ...(parsed.policy_results || [])]
          .map((pp: NearbyPP) => pp.stage)
          .filter(Boolean)
      )] as string[];
      // Restore saved filters or default to all
      const savedFilters = sessionStorage.getItem("nimby_stage_filters");
      if (savedFilters) {
        const parsed2 = JSON.parse(savedFilters) as string[];
        setActiveStages(parsed2.filter((s) => allStages.includes(s)));
      } else {
        setActiveStages(allStages);
      }
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
    setActiveStages((prev) => {
      const next = prev.includes(stage) ? prev.filter((s) => s !== stage) : [...prev, stage];
      sessionStorage.setItem("nimby_stage_filters", JSON.stringify(next));
      return next;
    });
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

        {/* Compare toggle */}
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button
            onClick={() => { setCompareMode(!compareMode); if (compareMode) setCompareSelection([]); }}
            style={{
              background: compareMode ? "var(--nsw-brand-dark)" : "var(--nsw-grey-01)",
              color: compareMode ? "var(--nsw-white)" : "var(--nsw-grey-04)",
              border: "none", padding: "6px 14px", cursor: "pointer",
              fontFamily: "'Public Sans', sans-serif", fontSize: 11,
              fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em",
            }}
          >
            {compareMode ? "Exit compare" : "Compare proposals"}
          </button>
          {compareMode && compareSelection.length > 0 && (
            <span style={{ fontFamily: "'Public Sans', sans-serif", fontSize: 12, color: "var(--nsw-grey-04)" }}>
              {compareSelection.join(" vs ")}{compareSelection.length < 2 ? " — select at least one more" : ` (${compareSelection.length}/4)`}
            </span>
          )}
          {compareMode && compareSelection.length >= 2 && (
            <button
              onClick={() => {
                const params = compareSelection.map((pp, i) => `pp${i + 1}=${pp}`).join("&");
                router.push(`/compare?${params}`);
              }}
              style={{
                background: "var(--nsw-brand-dark)", color: "var(--nsw-white)",
                border: "none", padding: "6px 14px", cursor: "pointer",
                fontFamily: "'Public Sans', sans-serif", fontSize: 11, fontWeight: 600,
              }}
            >
              Compare now &rarr;
            </button>
          )}
        </div>

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
                    onClick={compareMode ? undefined : () => handlePPClick(pp)}
                    compareSelected={compareSelection.includes(pp.pp_number)}
                    onCompareToggle={compareMode ? (ppn) => setCompareSelection((prev) =>
                      prev.includes(ppn) ? prev.filter((p) => p !== ppn)
                        : prev.length < 4 ? [...prev, ppn] : prev
                    ) : undefined}
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
                    onClick={compareMode ? undefined : () => handlePPClick(pp)}
                    compareSelected={compareSelection.includes(pp.pp_number)}
                    onCompareToggle={compareMode ? (ppn) => setCompareSelection((prev) =>
                      prev.includes(ppn) ? prev.filter((p) => p !== ppn)
                        : prev.length < 4 ? [...prev, ppn] : prev
                    ) : undefined}
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
