"use client";

import { Badge, Loader, Group } from "@mantine/core";

const TOOL_LABELS: Record<string, string> = {
  search_documents: "Searching proposal documents",
  get_site_context: "Checking planning controls",
  query_spatial_layer: "Querying NSW planning data",
  check_compliance: "Analysing compliance",
  get_nearby_places: "Finding nearby amenities",
  get_proposal_metadata: "Loading proposal info",
  verify_citation: "Verifying citation",
};

interface Props {
  tool: string;
  status: "calling" | "done";
}

export default function ToolCallIndicator({ tool, status }: Props) {
  const label = TOOL_LABELS[tool] || tool;

  return (
    <Group gap={6} py={4}>
      {status === "calling" ? (
        <Loader size={12} color="dark" />
      ) : (
        <span style={{ fontSize: 12 }}>&#10003;</span>
      )}
      <Badge
        size="xs"
        variant="light"
        color={status === "calling" ? "blue" : "green"}
        style={{ fontFamily: "'Public Sans', sans-serif" }}
      >
        {label}{status === "calling" ? "..." : ""}
      </Badge>
    </Group>
  );
}
