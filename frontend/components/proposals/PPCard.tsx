"use client";

import { Card, Text, Badge, Group, Stack } from "@mantine/core";
import type { NearbyPP } from "@/lib/api";

function daysBadge(exhibitionEnd: string | null) {
  if (!exhibitionEnd) return <Badge color="gray">No date</Badge>;
  const days = Math.ceil(
    (new Date(exhibitionEnd).getTime() - Date.now()) / 86400000
  );
  if (days < 0) return <Badge color="red">Closed</Badge>;
  if (days <= 7) return <Badge color="orange">{days}d left</Badge>;
  return <Badge color="green">{days}d left</Badge>;
}

function distanceLabel(km: number, geoSource: string | null) {
  if (geoSource === "lga_policy") return "LGA-wide";
  return `${km} km`;
}

interface Props {
  pp: NearbyPP;
  onClick?: () => void;
}

export default function PPCard({ pp, onClick }: Props) {
  return (
    <Card
      padding="md"
      withBorder
      onClick={onClick}
      style={{ cursor: onClick ? "pointer" : "default" }}
    >
      <Group justify="space-between" mb={8}>
        <Text
          style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: 11,
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          {pp.pp_number}
        </Text>
        {daysBadge(pp.exhibition_end)}
      </Group>

      <Text
        size="sm"
        lineClamp={2}
        mb={8}
        style={{ fontFamily: "'DM Serif Display', serif", fontSize: 15 }}
      >
        {pp.title || "Untitled proposal"}
      </Text>

      <div
        style={{
          borderTop: "1px solid var(--rule)",
          paddingTop: 8,
          display: "flex",
          justifyContent: "space-between",
        }}
      >
        <Text
          style={{
            fontSize: 11,
            color: "var(--ink-faint)",
            fontFamily: "'IBM Plex Sans', sans-serif",
          }}
        >
          {pp.council || "Unknown council"}
        </Text>
        <Text
          style={{
            fontSize: 11,
            color: "var(--ink-faint)",
            fontFamily: "'IBM Plex Mono', monospace",
          }}
        >
          {distanceLabel(pp.distance_km, pp.geo_source)}
        </Text>
      </div>
    </Card>
  );
}
