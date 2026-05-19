"use client";

import { Text, Stack } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface TimelineEvent {
  date: string;
  event_type: string;
  title: string;
  detail: string | null;
}

const EVENT_ICONS: Record<string, string> = {
  scraped: "\u2022",
  exhibition_start: "\u25B6",
  exhibition_end: "\u25A0",
  document_added: "\u2709",
  spatial_enriched: "\u2316",
  brief_generated: "\u2605",
};

const EVENT_COLORS: Record<string, string> = {
  scraped: "var(--nsw-grey-04)",
  exhibition_start: "#008A07",
  exhibition_end: "#D7153A",
  document_added: "var(--nsw-brand-dark)",
  spatial_enriched: "#6B21A8",
  brief_generated: "#C95000",
};

export default function TimelineTab({ ppNumber }: { ppNumber: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["timeline", ppNumber],
    queryFn: () =>
      fetch(`${API_BASE}/api/briefs/${ppNumber}/timeline`)
        .then((r) => {
          if (!r.ok) return [];
          return r.json();
        })
        .then((d) => (d?.events as TimelineEvent[]) || []),
  });

  if (isLoading) {
    return (
      <div>
        {[1, 2, 3].map((i) => (
          <div key={i} style={{ height: 16, width: `${60 + i * 10}%`, background: "var(--nsw-grey-02)", marginBottom: 12, animation: "chatPulse 1.5s ease-in-out infinite", animationDelay: `${i * 0.15}s` }} />
        ))}
        <style>{`@keyframes chatPulse { 0%,100% { opacity:1 } 50% { opacity:0.3 } }`}</style>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return <Text style={{ fontSize: 13, color: "var(--nsw-grey-04)" }}>No timeline data available.</Text>;
  }

  return (
    <Stack gap={0}>
      {data.map((event, i) => (
        <div
          key={i}
          style={{
            display: "flex",
            gap: 12,
            padding: "10px 0",
            borderLeft: `2px solid ${i < data.length - 1 ? "var(--nsw-grey-02)" : "transparent"}`,
            marginLeft: 8,
            paddingLeft: 16,
            position: "relative",
          }}
        >
          <div
            style={{
              position: "absolute",
              left: -7,
              top: 12,
              width: 12,
              height: 12,
              background: EVENT_COLORS[event.event_type] || "var(--nsw-grey-04)",
              borderRadius: "50%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 7,
              color: "white",
            }}
          >
            {EVENT_ICONS[event.event_type] || "\u2022"}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <Text style={{ fontSize: 10, color: "var(--nsw-grey-04)", fontFamily: "'Public Sans', sans-serif" }}>
              {new Date(event.date).toLocaleDateString("en-AU", { day: "numeric", month: "short", year: "numeric" })}
            </Text>
            <Text style={{ fontSize: 13, fontWeight: 500, fontFamily: "'Public Sans', sans-serif" }}>
              {event.title}
            </Text>
            {event.detail && (
              <Text style={{ fontSize: 11, color: "var(--nsw-grey-04)" }}>{event.detail}</Text>
            )}
          </div>
        </div>
      ))}
    </Stack>
  );
}
