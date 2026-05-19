"use client";

import { Container, Title, Text, Stack, Card, Group, Loader, Center } from "@mantine/core";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { getBrief } from "@/lib/api";
import { Suspense } from "react";

interface SiteContextData {
  zoning?: string;
  max_height_m?: number;
  max_fsr?: number;
  heritage_item?: boolean;
  bushfire_prone?: boolean;
  flood_planning?: boolean;
}

function CompareContent() {
  const params = useSearchParams();
  const pp1 = params.get("pp1") || "";
  const pp2 = params.get("pp2") || "";

  const { data: brief1, isLoading: l1 } = useQuery({
    queryKey: ["brief", pp1],
    queryFn: () => getBrief(pp1),
    enabled: !!pp1,
  });

  const { data: brief2, isLoading: l2 } = useQuery({
    queryKey: ["brief", pp2],
    queryFn: () => getBrief(pp2),
    enabled: !!pp2,
  });

  const { data: ctx1 } = useQuery({
    queryKey: ["site-context", pp1],
    queryFn: () => fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/site-context/${pp1}`).then(r => r.json()) as Promise<SiteContextData>,
    enabled: !!pp1,
  });

  const { data: ctx2 } = useQuery({
    queryKey: ["site-context", pp2],
    queryFn: () => fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/site-context/${pp2}`).then(r => r.json()) as Promise<SiteContextData>,
    enabled: !!pp2,
  });

  if (!pp1 || !pp2) {
    return (
      <Container size="lg" py="xl">
        <Stack gap="md">
          <Title order={2}>Compare Proposals</Title>
          <Text style={{ fontSize: 13, color: "var(--nsw-grey-04)" }}>
            Use ?pp1=PP-XXXX-XXXX&pp2=PP-YYYY-YYYY to compare two proposals side by side.
          </Text>
        </Stack>
      </Container>
    );
  }

  if (l1 || l2) {
    return <Center py="xl"><Loader color="dark" /></Center>;
  }

  const rows = [
    { label: "Council", v1: brief1?.council, v2: brief2?.council },
    { label: "Stage", v1: brief1?.exhibition_end ? `Exhibition closes ${brief1.exhibition_end}` : "N/A", v2: brief2?.exhibition_end ? `Exhibition closes ${brief2.exhibition_end}` : "N/A" },
    { label: "Zoning", v1: ctx1?.zoning, v2: ctx2?.zoning },
    { label: "Max Height", v1: ctx1?.max_height_m ? `${ctx1.max_height_m}m` : "N/A", v2: ctx2?.max_height_m ? `${ctx2.max_height_m}m` : "N/A" },
    { label: "Max FSR", v1: ctx1?.max_fsr ? `${ctx1.max_fsr}:1` : "N/A", v2: ctx2?.max_fsr ? `${ctx2.max_fsr}:1` : "N/A" },
    { label: "Heritage", v1: ctx1?.heritage_item ? "Yes" : "No", v2: ctx2?.heritage_item ? "Yes" : "No" },
    { label: "Bushfire Prone", v1: ctx1?.bushfire_prone ? "Yes" : "No", v2: ctx2?.bushfire_prone ? "Yes" : "No" },
    { label: "Flood Planning", v1: ctx1?.flood_planning ? "Yes" : "No", v2: ctx2?.flood_planning ? "Yes" : "No" },
  ];

  return (
    <Container size="lg" py="xl">
      <Stack gap="lg">
        <div>
          <Text style={{ fontFamily: "'Public Sans', sans-serif", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--nsw-grey-04)", marginBottom: 4 }}>
            Comparison
          </Text>
          <Title order={2}>Compare Proposals</Title>
          <div style={{ width: 60, height: 3, background: "var(--nsw-brand-dark)", margin: "8px 0" }} />
        </div>

        {/* Headers */}
        <div style={{ display: "grid", gridTemplateColumns: "140px 1fr 1fr", gap: 0, border: "2px solid var(--nsw-brand-dark)" }}>
          <div style={{ padding: "10px 12px", background: "var(--nsw-brand-dark)", color: "var(--nsw-white)", fontFamily: "'Public Sans', sans-serif", fontSize: 11, fontWeight: 700, textTransform: "uppercase" }}>
            Field
          </div>
          <div style={{ padding: "10px 12px", background: "var(--nsw-brand-dark)", color: "var(--nsw-white)", fontFamily: "'Public Sans', sans-serif", fontSize: 12, fontWeight: 600, borderLeft: "1px solid rgba(255,255,255,0.2)" }}>
            {pp1}
          </div>
          <div style={{ padding: "10px 12px", background: "var(--nsw-brand-dark)", color: "var(--nsw-white)", fontFamily: "'Public Sans', sans-serif", fontSize: 12, fontWeight: 600, borderLeft: "1px solid rgba(255,255,255,0.2)" }}>
            {pp2}
          </div>

          {/* Title row */}
          <div style={{ padding: "10px 12px", fontWeight: 600, fontSize: 12, borderBottom: "1px solid var(--nsw-grey-02)" }}>Title</div>
          <div style={{ padding: "10px 12px", fontSize: 12, borderBottom: "1px solid var(--nsw-grey-02)", borderLeft: "1px solid var(--nsw-grey-02)" }}>{brief1?.title || "N/A"}</div>
          <div style={{ padding: "10px 12px", fontSize: 12, borderBottom: "1px solid var(--nsw-grey-02)", borderLeft: "1px solid var(--nsw-grey-02)" }}>{brief2?.title || "N/A"}</div>

          {rows.map((row) => {
            const differs = row.v1 !== row.v2;
            return [
              <div key={`${row.label}-label`} style={{ padding: "8px 12px", fontWeight: 600, fontSize: 12, borderBottom: "1px solid var(--nsw-grey-02)" }}>{row.label}</div>,
              <div key={`${row.label}-v1`} style={{ padding: "8px 12px", fontSize: 12, borderBottom: "1px solid var(--nsw-grey-02)", borderLeft: "1px solid var(--nsw-grey-02)", background: differs ? "var(--nsw-grey-01)" : undefined }}>{row.v1 || "N/A"}</div>,
              <div key={`${row.label}-v2`} style={{ padding: "8px 12px", fontSize: 12, borderBottom: "1px solid var(--nsw-grey-02)", borderLeft: "1px solid var(--nsw-grey-02)", background: differs ? "var(--nsw-grey-01)" : undefined }}>{row.v2 || "N/A"}</div>,
            ];
          })}
        </div>

        {/* Briefs side by side */}
        <Group grow align="flex-start" gap="md">
          <Card withBorder padding="md">
            <Text style={{ fontFamily: "'Public Sans', sans-serif", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--nsw-grey-04)", marginBottom: 8 }}>
              {pp1} Summary
            </Text>
            <Text style={{ fontSize: 12, lineHeight: 1.7, whiteSpace: "pre-wrap" }}>
              {brief1?.description || brief1?.markdown?.slice(0, 800) || "No brief available"}
            </Text>
          </Card>
          <Card withBorder padding="md">
            <Text style={{ fontFamily: "'Public Sans', sans-serif", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--nsw-grey-04)", marginBottom: 8 }}>
              {pp2} Summary
            </Text>
            <Text style={{ fontSize: 12, lineHeight: 1.7, whiteSpace: "pre-wrap" }}>
              {brief2?.description || brief2?.markdown?.slice(0, 800) || "No brief available"}
            </Text>
          </Card>
        </Group>
      </Stack>
    </Container>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={<Center py="xl"><Loader color="dark" /></Center>}>
      <CompareContent />
    </Suspense>
  );
}
