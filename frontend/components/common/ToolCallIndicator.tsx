"use client";

const TOOL_LABELS: Record<string, string> = {
  search_documents: "Searching proposal documents",
  get_site_context: "Checking planning controls",
  query_spatial_layer: "Querying NSW planning data",
  check_compliance: "Analysing compliance",
  get_nearby_places: "Finding nearby amenities",
  get_proposal_metadata: "Loading proposal info",
  verify_citation: "Verifying citation",
  "Searching documents": "Searching documents",
  "Checking spatial data": "Checking spatial data",
  "Checking compliance": "Checking compliance",
};

// Hide internal routing events
const HIDDEN_TOOLS = new Set([
  "transfer_to_agent",
  "TRANSFER_TO_AGENT",
]);

interface Props {
  tool: string;
  status: "calling" | "done";
}

export default function ToolCallIndicator({ tool, status }: Props) {
  if (HIDDEN_TOOLS.has(tool)) return null;

  const label = TOOL_LABELS[tool] || tool.replace(/_/g, " ");
  const isDone = status === "done";

  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "3px 0",
      }}
    >
      {isDone ? (
        <span
          style={{
            fontSize: 11,
            color: "var(--nsw-brand-dark)",
            fontWeight: 700,
          }}
        >
          &#10003;
        </span>
      ) : (
        <span
          style={{
            display: "inline-block",
            width: 10,
            height: 10,
            border: "2px solid var(--nsw-brand-dark)",
            borderTopColor: "transparent",
            borderRadius: "50%",
            animation: "tool-spin 0.6s linear infinite",
          }}
        />
      )}
      <span
        style={{
          fontFamily: "'Public Sans', sans-serif",
          fontSize: 11,
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          color: isDone ? "var(--nsw-brand-dark)" : "var(--nsw-grey-04)",
          fontWeight: 600,
        }}
      >
        {label}{!isDone ? "..." : ""}
      </span>
      <style>{`
        @keyframes tool-spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
