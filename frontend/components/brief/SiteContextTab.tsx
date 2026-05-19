"use client";

import {
  Card,
  Text,
  Badge,
  Group,
  Stack,
  SimpleGrid,
  Loader,
  Center,
  Alert,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { getSiteContext } from "@/lib/api";
import HazardBadges from "./HazardBadges";

const ZONE_COLORS: Record<string, string> = {
  R1: "green", R2: "green", R3: "lime", R4: "lime", R5: "green",
  B1: "blue", B2: "blue", B3: "blue", B4: "blue", B5: "blue", B6: "blue", B7: "blue", B8: "blue",
  IN1: "gray", IN2: "gray", IN3: "gray", IN4: "gray",
  SP1: "violet", SP2: "violet", SP3: "violet", SP5: "violet",
  RE1: "teal", RE2: "teal",
  E1: "emerald", E2: "emerald", E3: "emerald", E4: "emerald",
  RU1: "orange", RU2: "orange", RU3: "orange", RU4: "orange", RU5: "orange", RU6: "orange",
  C1: "green", C2: "teal", C3: "lime", C4: "yellow",
  W1: "blue", W2: "blue",
};

function getZoneColor(zoning: string | null): string {
  if (!zoning) return "gray";
  const code = zoning.split(" ")[0];
  return ZONE_COLORS[code] || "gray";
}

interface Props {
  ppNumber: string;
}

export default function SiteContextTab({ ppNumber }: Props) {
  const { data: ctx, isLoading, error } = useQuery({
    queryKey: ["siteContext", ppNumber],
    queryFn: () => getSiteContext(ppNumber),
  });

  if (isLoading) {
    return (
      <Center py="xl">
        <Loader size="sm" color="dark" />
      </Center>
    );
  }

  if (error || !ctx) {
    return (
      <Alert color="yellow" title="No site context">
        Planning controls data is not available for this proposal. The site may not have been geocoded yet.
      </Alert>
    );
  }

  const zoneCode = ctx.zoning?.split(" ")[0] || "N/A";
  const zoneName = ctx.zoning?.replace(/^[A-Z0-9]+ - /, "") || "N/A";

  return (
    <Stack gap="md">
      {/* Zoning */}
      <Card withBorder padding="md">
        <Group gap={8} mb={4}>
          <Badge color={getZoneColor(ctx.zoning)} size="lg" variant="filled">
            {zoneCode || "N/A"}
          </Badge>
          <Text style={{ fontFamily: "'Public Sans', sans-serif", fontSize: 15, fontWeight: 600 }}>
            {zoneName}
          </Text>
        </Group>
      </Card>

      {/* Planning Controls */}
      <Card withBorder padding="md">
        <Text
          style={{
            fontFamily: "'Public Sans', sans-serif",
            fontSize: 11,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "var(--nsw-grey-04)",
            marginBottom: 12,
          }}
        >
          Planning Controls
        </Text>
        <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md">
          <div>
            <Text style={{ fontSize: 11, color: "var(--nsw-grey-04)" }}>Max Height</Text>
            <Text style={{ fontSize: 20, fontWeight: 700 }}>
              {ctx.max_height_m ? `${ctx.max_height_m}m` : "N/A"}
            </Text>
          </div>
          <div>
            <Text style={{ fontSize: 11, color: "var(--nsw-grey-04)" }}>Max FSR</Text>
            <Text style={{ fontSize: 20, fontWeight: 700 }}>
              {ctx.max_fsr ? `${ctx.max_fsr}:1` : "N/A"}
            </Text>
          </div>
          <div>
            <Text style={{ fontSize: 11, color: "var(--nsw-grey-04)" }}>Min Lot Size</Text>
            <Text style={{ fontSize: 20, fontWeight: 700 }}>
              {ctx.min_lot_size_sqm ? `${ctx.min_lot_size_sqm} sqm` : "N/A"}
            </Text>
          </div>
        </SimpleGrid>
      </Card>

      {/* Heritage */}
      {(ctx.heritage_item || ctx.heritage_state) && (
        <Card withBorder padding="md">
          <Text
            style={{
              fontFamily: "'Public Sans', sans-serif",
              fontSize: 11,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "var(--nsw-grey-04)",
              marginBottom: 8,
            }}
          >
            Heritage
          </Text>
          {ctx.heritage_item && (
            <Group gap={8}>
              <Badge color="violet" variant="light" size="sm">Local Heritage</Badge>
              <Text style={{ fontSize: 13 }}>{ctx.heritage_item}</Text>
            </Group>
          )}
          {ctx.heritage_state && (
            <Group gap={8} mt={4}>
              <Badge color="red" variant="filled" size="sm">State Heritage</Badge>
              <Text style={{ fontSize: 13 }}>State Heritage Register listed</Text>
            </Group>
          )}
        </Card>
      )}

      {/* Hazards & Environmental */}
      <Card withBorder padding="md">
        <Text
          style={{
            fontFamily: "'Public Sans', sans-serif",
            fontSize: 11,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "var(--nsw-grey-04)",
            marginBottom: 8,
          }}
        >
          Hazards & Environmental
        </Text>
        <HazardBadges ctx={ctx} />
      </Card>
    </Stack>
  );
}
