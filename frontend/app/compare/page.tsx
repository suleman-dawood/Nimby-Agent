"use client";

import { Container, Title, Text, Stack, Card, Group, Loader, Center, Textarea, ActionIcon } from "@mantine/core";
import { useSearchParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { getBrief, streamAgentAsk, streamAsk } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";
import { Suspense, useState, useRef, useCallback, useEffect } from "react";
import ReactMarkdown from "react-markdown";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface SiteContextData {
  zoning?: string;
  max_height_m?: number;
  max_fsr?: number;
  heritage_item?: boolean;
  bushfire_prone?: boolean;
  flood_planning?: boolean;
}

interface BriefData {
  pp_number: string;
  title: string | null;
  council: string | null;
  exhibition_start: string | null;
  exhibition_end: string | null;
  description: string | null;
  markdown: string;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

function useProposalData(pp: string) {
  const brief = useQuery({
    queryKey: ["brief", pp],
    queryFn: () => getBrief(pp),
    enabled: !!pp,
  });
  const ctx = useQuery({
    queryKey: ["site-context", pp],
    queryFn: () => fetch(`${API_BASE}/api/site-context/${pp}`).then(r => r.ok ? r.json() : null) as Promise<SiteContextData | null>,
    enabled: !!pp,
  });
  return { brief: brief.data, ctx: ctx.data, loading: brief.isLoading };
}

function CompareContent() {
  const params = useSearchParams();
  const router = useRouter();

  // Support up to 4 PPs
  const initialPPs = [
    params.get("pp1"), params.get("pp2"), params.get("pp3"), params.get("pp4"),
  ].filter(Boolean) as string[];

  const [pps, setPPs] = useState<string[]>(initialPPs);
  const [chatOpen, setChatOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Fetch data for each PP
  const d1 = useProposalData(pps[0] || "");
  const d2 = useProposalData(pps[1] || "");
  const d3 = useProposalData(pps[2] || "");
  const d4 = useProposalData(pps[3] || "");
  const allData = [d1, d2, d3, d4].slice(0, pps.length);

  const removePP = (idx: number) => {
    const next = pps.filter((_, i) => i !== idx);
    setPPs(next);
    // Update URL
    const params = new URLSearchParams();
    next.forEach((pp, i) => params.set(`pp${i + 1}`, pp));
    router.replace(`/compare?${params.toString()}`);
  };

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight));
  }, []);

  const handleSend = () => {
    const q = input.trim();
    if (!q || isStreaming) return;

    // Prefix question with all PP numbers for context
    const context = `[Comparing: ${pps.join(", ")}] ${q}`;
    setMessages(prev => [...prev, { role: "user", content: q }]);
    setInput("");
    setIsStreaming(true);

    setMessages(prev => [...prev, { role: "assistant", content: "", streaming: true }]);
    let accumulated = "";

    // Use first PP as the primary for the agent endpoint
    const streamFn = isAuthenticated() ? streamAgentAsk : streamAsk;
    streamFn(pps[0], context, {
      onToken: (token) => {
        accumulated += token;
        setMessages(prev => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.role === "assistant") updated[updated.length - 1] = { ...last, content: accumulated };
          return updated;
        });
        scrollToBottom();
      },
      onCitations: () => {},
      onError: (err) => {
        setMessages(prev => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.role === "assistant") updated[updated.length - 1] = { ...last, content: err || "Error", streaming: false };
          return updated;
        });
        setIsStreaming(false);
      },
      onDone: () => {
        setMessages(prev => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last?.role === "assistant") updated[updated.length - 1] = { ...last, streaming: false };
          return updated;
        });
        setIsStreaming(false);
        scrollToBottom();
      },
    });
  };

  if (pps.length === 0) {
    return (
      <Container size="lg" py="xl">
        <Stack gap="md">
          <Title order={2}>Compare Proposals</Title>
          <Text style={{ fontSize: 13, color: "var(--nsw-grey-04)" }}>
            Select proposals from the results page using "Compare proposals" mode, or add PP numbers to the URL: /compare?pp1=PP-XXXX&pp2=PP-YYYY
          </Text>
        </Stack>
      </Container>
    );
  }

  const anyLoading = allData.some(d => d.loading);
  if (anyLoading) {
    return (
      <Container size="lg" py="xl">
        {[1, 2, 3].map(i => (
          <div key={i} style={{ height: 16, background: "var(--nsw-grey-02)", marginBottom: 12, width: `${70 + i * 8}%`, animation: "skeletonPulse 1.5s ease-in-out infinite", animationDelay: `${i * 0.15}s` }} />
        ))}
        <style>{`@keyframes skeletonPulse { 0%,100% { opacity:1 } 50% { opacity:0.4 } }`}</style>
      </Container>
    );
  }

  const ROWS: { label: string; getValue: (b: BriefData | undefined, c: SiteContextData | null | undefined) => string }[] = [
    { label: "Title", getValue: (b) => b?.title || "N/A" },
    { label: "Council", getValue: (b) => b?.council || "N/A" },
    { label: "Exhibition", getValue: (b) => b?.exhibition_end ? `Closes ${b.exhibition_end}` : "N/A" },
    { label: "Zoning", getValue: (_, c) => c?.zoning || "N/A" },
    { label: "Max Height", getValue: (_, c) => c?.max_height_m ? `${c.max_height_m}m` : "N/A" },
    { label: "Max FSR", getValue: (_, c) => c?.max_fsr ? `${c.max_fsr}:1` : "N/A" },
    { label: "Heritage", getValue: (_, c) => c?.heritage_item ? "Yes" : "No" },
    { label: "Bushfire", getValue: (_, c) => c?.bushfire_prone ? "Yes" : "No" },
    { label: "Flood", getValue: (_, c) => c?.flood_planning ? "Yes" : "No" },
  ];

  const colTemplate = `100px ${pps.map(() => "1fr").join(" ")}`;

  return (
    <>
      <div
        className="compare-main"
        style={{
          transition: "margin-right 0.2s ease",
          ...(chatOpen ? { marginRight: 420 } : {}),
        }}
      >
        <Container size="xl" py="md">
          <Stack gap="md">
            {/* Header */}
            <div>
              <Text style={{ fontFamily: "'Public Sans', sans-serif", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--nsw-grey-04)", marginBottom: 4 }}>
                Comparison
              </Text>
              <Group justify="space-between" align="flex-end">
                <Title order={2} style={{ fontSize: 22 }}>Compare {pps.length} Proposals</Title>
                <button
                  onClick={() => setChatOpen(!chatOpen)}
                  style={{
                    background: chatOpen ? "var(--nsw-grey-01)" : "var(--nsw-brand-dark)",
                    color: chatOpen ? "var(--nsw-brand-dark)" : "var(--nsw-white)",
                    border: "none", padding: "6px 14px", cursor: "pointer",
                    fontFamily: "'Public Sans', sans-serif", fontSize: 11, fontWeight: 600,
                  }}
                >
                  {chatOpen ? "Close chat" : "Ask about these proposals"}
                </button>
              </Group>
              <div style={{ width: 60, height: 3, background: "var(--nsw-brand-dark)", margin: "8px 0" }} />
            </div>

            {/* Comparison grid */}
            <div className="compare-grid" style={{ display: "grid", gridTemplateColumns: colTemplate, gap: 0, border: "2px solid var(--nsw-brand-dark)", overflowX: "auto" }}>
              {/* Header row */}
              <div style={{ padding: "8px 10px", background: "var(--nsw-brand-dark)", color: "var(--nsw-white)", fontFamily: "'Public Sans', sans-serif", fontSize: 10, fontWeight: 700, textTransform: "uppercase" }}>
                Field
              </div>
              {pps.map((pp, i) => (
                <div key={pp} style={{ padding: "8px 10px", background: "var(--nsw-brand-dark)", color: "var(--nsw-white)", fontFamily: "'Public Sans', sans-serif", fontSize: 11, fontWeight: 600, borderLeft: "1px solid rgba(255,255,255,0.2)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <a href={`/brief/${pp}`} style={{ color: "var(--nsw-white)", textDecoration: "underline" }}>{pp}</a>
                  {pps.length > 1 && (
                    <span onClick={() => removePP(i)} style={{ cursor: "pointer", opacity: 0.7, fontSize: 14 }}>&times;</span>
                  )}
                </div>
              ))}

              {/* Data rows */}
              {ROWS.map((row) => {
                const values = allData.map(d => row.getValue(d.brief as BriefData | undefined, d.ctx));
                const allSame = values.every(v => v === values[0]);
                return [
                  <div key={`${row.label}-l`} style={{ padding: "6px 10px", fontWeight: 600, fontSize: 11, borderBottom: "1px solid var(--nsw-grey-02)", fontFamily: "'Public Sans', sans-serif" }}>{row.label}</div>,
                  ...values.map((v, i) => (
                    <div key={`${row.label}-${i}`} style={{
                      padding: "6px 10px", fontSize: 11, borderBottom: "1px solid var(--nsw-grey-02)",
                      borderLeft: "1px solid var(--nsw-grey-02)",
                      background: !allSame ? "var(--nsw-grey-01)" : undefined,
                      fontFamily: "'Public Sans', sans-serif",
                    }}>{v}</div>
                  )),
                ];
              })}
            </div>

            {/* Summary cards */}
            <div className="compare-summaries" style={{ display: "grid", gridTemplateColumns: `repeat(${pps.length}, 1fr)`, gap: 12 }}>
              {pps.map((pp, i) => {
                const d = allData[i];
                return (
                  <Card key={pp} withBorder padding="sm">
                    <Group justify="space-between" mb={4}>
                      <Text style={{ fontFamily: "'Public Sans', sans-serif", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--nsw-grey-04)" }}>
                        {pp}
                      </Text>
                      <a href={`/brief/${pp}`} style={{ fontSize: 10, color: "var(--nsw-brand-dark)", fontWeight: 600 }}>View &rarr;</a>
                    </Group>
                    <Text style={{ fontSize: 12, lineHeight: 1.6 }} lineClamp={8}>
                      {d?.brief?.description || (d?.brief as BriefData | undefined)?.markdown?.slice(0, 400) || "No summary"}
                    </Text>
                  </Card>
                );
              })}
            </div>
          </Stack>
        </Container>
      </div>

      {/* Chat panel */}
      {chatOpen && (
        <div
          className="compare-chat"
          style={{
            position: "fixed", right: 0, top: 52, bottom: 0, width: 420,
            background: "var(--nsw-white)", borderLeft: "2px solid var(--nsw-brand-dark)",
            display: "flex", flexDirection: "column", zIndex: 100,
          }}
        >
          <div style={{ padding: "10px 14px", borderBottom: "2px solid var(--nsw-brand-dark)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <Text style={{ fontFamily: "'Public Sans', sans-serif", fontSize: 14 }}>
              Compare Chat
            </Text>
            <ActionIcon variant="subtle" onClick={() => setChatOpen(false)} color="dark">
              <span style={{ fontSize: 18 }}>&times;</span>
            </ActionIcon>
          </div>

          <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", padding: 14 }}>
            <Stack gap="sm">
              {messages.length === 0 && (
                <Text style={{ fontSize: 12, color: "var(--nsw-grey-04)", padding: "16px 0" }}>
                  Ask questions about {pps.join(", ")}. The agent will compare across all selected proposals.
                </Text>
              )}
              {messages.map((msg, i) => (
                <div key={i}>
                  {msg.role === "user" ? (
                    <div style={{ background: "var(--nsw-text)", color: "var(--nsw-white)", padding: "8px 12px", fontSize: 12, marginLeft: 30 }}>
                      {msg.content}
                    </div>
                  ) : (
                    <div style={{ background: "var(--nsw-grey-01)", border: "1px solid var(--nsw-grey-02)", padding: "10px 12px", fontSize: 12, lineHeight: 1.7 }}>
                      <div className="chat-markdown">
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                      </div>
                      {msg.streaming && (
                        <span style={{ display: "inline-block", width: 6, height: 14, background: "var(--nsw-text)", marginLeft: 2, animation: "blink 1s step-end infinite" }} />
                      )}
                    </div>
                  )}
                </div>
              ))}
            </Stack>
          </div>

          <div style={{ padding: "10px 14px", borderTop: "1px solid var(--nsw-grey-02)" }}>
            <div style={{ display: "flex", gap: 0, border: "2px solid var(--nsw-grey-03)", padding: "4px 4px 4px 10px" }}
              onFocus={(e) => (e.currentTarget.style.borderColor = "var(--nsw-brand-dark)")}
              onBlur={(e) => (e.currentTarget.style.borderColor = "var(--nsw-grey-03)")}
            >
              <Textarea
                placeholder={`Compare ${pps.length} proposals...`}
                value={input}
                onChange={(e) => setInput(e.currentTarget.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                disabled={isStreaming}
                autosize minRows={1} maxRows={3} variant="unstyled"
                style={{ flex: 1 }}
                styles={{ input: { fontSize: 12, padding: 0, minHeight: "unset" } }}
              />
              <ActionIcon onClick={handleSend} disabled={!input.trim() || isStreaming} variant="filled" color="dark" size="md">
                <span style={{ fontSize: 14 }}>&uarr;</span>
              </ActionIcon>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes blink { 50% { opacity: 0; } }
        @keyframes skeletonPulse { 0%,100% { opacity:1 } 50% { opacity:0.4 } }
        .chat-markdown p { margin: 0 0 6px 0; }
        .chat-markdown p:last-child { margin-bottom: 0; }
        .chat-markdown ul { margin: 4px 0; padding-left: 16px; }
        @media (max-width: 768px) {
          .compare-main { margin-right: 0 !important; }
          .compare-chat { width: 100% !important; left: 0; border-left: none !important; }
          .compare-grid { font-size: 10px !important; }
          .compare-summaries { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={<Center py="xl"><Loader color="dark" /></Center>}>
      <CompareContent />
    </Suspense>
  );
}
