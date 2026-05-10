"use client";

import { Badge, Group } from "@mantine/core";
import type { SiteContextResponse } from "@/lib/api";

interface Props {
  ctx: SiteContextResponse;
}

export default function HazardBadges({ ctx }: Props) {
  const hazards: { label: string; color: string; active: boolean }[] = [
    { label: "Bushfire Prone", color: "red", active: ctx.bushfire_prone },
    { label: "Flood Zone", color: "blue", active: ctx.flood_planning },
    { label: "Landslide Risk", color: "orange", active: !!ctx.landslide_risk },
    { label: "Acid Sulfate", color: "yellow", active: !!ctx.acid_sulfate_class && ctx.acid_sulfate_class <= 3 },
    { label: "Biodiversity", color: "teal", active: ctx.biodiversity_sensitive },
    { label: "Drinking Water Catchment", color: "cyan", active: ctx.drinking_water_catchment },
    { label: "Wetlands", color: "indigo", active: ctx.wetlands_nearby },
  ];

  const active = hazards.filter((h) => h.active);

  if (active.length === 0) {
    return (
      <Badge color="green" variant="light" size="sm">
        No identified hazards
      </Badge>
    );
  }

  return (
    <Group gap={6} wrap="wrap">
      {active.map((h) => (
        <Badge key={h.label} color={h.color} variant="filled" size="sm">
          {h.label}
        </Badge>
      ))}
    </Group>
  );
}
