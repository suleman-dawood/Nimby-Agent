"use client";

import {
  Text,
  Textarea,
  Stack,
  Chip,
  Group,
  ActionIcon,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import {
  getCitation,
  getSuggestions,
  streamAsk,
  streamAgentAsk,
  streamImpactFast,
} from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";
import ToolCallIndicator from "@/components/common/ToolCallIndicator";

interface Citation {
  document_title: string;
  page: number;
}

interface ToolCall {
  tool: string;
  status: "calling" | "done";
}

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  toolCalls?: ToolCall[];
  streaming?: boolean;
}

interface Props {
  ppNumber: string;
  address: string | null;
  distanceKm: number;
  opened: boolean;
  onToggle: () => void;
}

const CITE_RE = /\[doc:\s*.+?\s*(\|\s*p\.?\s*\d+)?\]/g;

function replaceCitesWithNumbers(text: string, citations?: Citation[]): string {
  if (!citations || citations.length === 0) {
    return text.replace(CITE_RE, "");
  }
  const emitted = new Set<number>();
  return text.replace(CITE_RE, (match) => {
    // Extract title and optional page from [doc: Title | p.N] or [doc: Title]
    const fullMatch = match.match(/\[doc:\s*(.+?)(?:\s*\|\s*p\.?\s*(\d+))?\s*\]/);
    if (!fullMatch) return "";
    const title = fullMatch[1].trim().toLowerCase();
    const page = fullMatch[2] ? parseInt(fullMatch[2]) : 0;

    // Try exact title+page match first
    let idx = citations.findIndex(
      (c) => c.document_title.toLowerCase() === title && (page === 0 || c.page === page)
    );
    // Fallback: substring match
    if (idx < 0) {
      idx = citations.findIndex(
        (c) => c.document_title.toLowerCase().includes(title.slice(0, 30))
          || title.includes(c.document_title.toLowerCase().slice(0, 30))
      );
    }
    if (idx >= 0) {
      emitted.add(idx);
      return ` **[${idx + 1}]**`;
    }
    return "";
  });
}

export default function ChatPanel({
  ppNumber,
  address,
  distanceKm,
  opened,
  onToggle,
}: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const impactFired = useRef(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: suggestions } = useQuery({
    queryKey: ["suggestions", ppNumber],
    queryFn: () => getSuggestions(ppNumber),
    enabled: opened,
  });

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
    });
  }, []);

  const startStream = useCallback(
    (
      streamFn: (callbacks: {
        onToken: (t: string) => void;
        onCitations: (c: Citation[]) => void;
        onToolCall?: (tool: string, status: "calling" | "done") => void;
        onError: (e: string) => void;
        onDone: () => void;
      }) => Promise<void>
    ) => {
      setIsStreaming(true);

      // Add empty assistant message
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "", streaming: true, toolCalls: [] },
      ]);

      let accumulated = "";

      streamFn({
        onToken: (token) => {
          accumulated += token;
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last.role === "assistant") {
              updated[updated.length - 1] = {
                ...last,
                content: accumulated,
                streaming: true,
              };
            }
            return updated;
          });
          scrollToBottom();
        },
        onToolCall: (tool, status) => {
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last.role === "assistant") {
              const calls = [...(last.toolCalls || [])];
              const existing = calls.findIndex((c) => c.tool === tool);
              if (existing >= 0) {
                calls[existing] = { tool, status };
              } else {
                calls.push({ tool, status });
              }
              updated[updated.length - 1] = { ...last, toolCalls: calls };
            }
            return updated;
          });
          scrollToBottom();
        },
        onCitations: (citations) => {
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last.role === "assistant") {
              updated[updated.length - 1] = {
                ...last,
                citations,
                streaming: false,
              };
            }
            return updated;
          });
        },
        onError: (error) => {
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last.role === "assistant") {
              updated[updated.length - 1] = {
                ...last,
                content: error || "Something went wrong.",
                streaming: false,
              };
            }
            return updated;
          });
          setIsStreaming(false);
        },
        onDone: () => {
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last?.role === "assistant" && last.streaming) {
              updated[updated.length - 1] = { ...last, streaming: false };
            }
            return updated;
          });
          setIsStreaming(false);
          scrollToBottom();
        },
      });
    },
    [scrollToBottom]
  );

  // Start loading impact immediately on mount (even when collapsed)
  useEffect(() => {
    if (impactFired.current) return;
    impactFired.current = true;
    if (address) {
      startStream((cb) =>
        streamImpactFast(ppNumber, address, distanceKm, cb)
      );
    } else {
      // No address — show welcome message
      setMessages([{
        role: "assistant",
        content: "Ask me anything about this planning proposal. I can search the proposal documents, check planning controls, and analyse compliance with the LEP.",
      }]);
    }
  }, [address, ppNumber, distanceKm, startStream]);

  const handleSend = (q?: string) => {
    const question = q || input;
    if (!question.trim() || isStreaming) return;

    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setInput("");

    // Use agent endpoint if authenticated, fallback to basic stream
    if (isAuthenticated()) {
      startStream((cb) => streamAgentAsk(ppNumber, question, cb));
    } else {
      startStream((cb) => streamAsk(ppNumber, question, cb));
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages.length, scrollToBottom]);

  if (!opened) {
    return (
      <div
        onClick={onToggle}
        style={{
          position: "fixed",
          right: 0,
          top: "50%",
          transform: "translateY(-50%)",
          background: "var(--nsw-text)",
          color: "var(--nsw-white)",
          padding: "16px 8px",
          cursor: "pointer",
          writingMode: "vertical-rl",
          textOrientation: "mixed",
          fontFamily: "'Public Sans', Arial, sans-serif",
          fontSize: 11,
          textTransform: "uppercase",
          letterSpacing: "0.1em",
          zIndex: 100,
        }}
      >
        {isStreaming ? "Loading..." : messages.length > 0 ? "Chat ready" : "Chat"}
      </div>
    );
  }

  return (
    <div
      className="chat-panel"
      style={{
        position: "fixed",
        right: 0,
        top: 52,
        bottom: 0,
        background: "var(--nsw-white)",
        borderLeft: "2px solid var(--nsw-brand-dark)",
        display: "flex",
        flexDirection: "column",
        zIndex: 100,
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "12px 16px",
          borderBottom: "2px solid var(--nsw-brand-dark)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <Text
          style={{
            fontFamily: "'Public Sans', Arial, sans-serif",
            fontSize: 16,
          }}
        >
          How this affects you
        </Text>
        <ActionIcon variant="subtle" onClick={onToggle} color="dark">
          <span style={{ fontSize: 18 }}>&times;</span>
        </ActionIcon>
      </div>

      {/* Messages */}
      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: "auto",
          padding: 16,
        }}
      >
        <Stack gap="md">
          {messages.length === 0 && (
            <div style={{ padding: "24px 0" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
                <div style={{ width: 8, height: 8, background: "var(--nsw-brand-dark)", animation: "chatPulse 1.2s ease-in-out infinite" }} />
                <Text style={{ fontSize: 12, color: "var(--nsw-grey-04)", fontFamily: "'Public Sans', sans-serif" }}>
                  {isStreaming ? "Analysing impact on your address..." : "Loading chat..."}
                </Text>
              </div>
              {[70, 90, 55].map((w, i) => (
                <div key={i} style={{ height: 10, width: `${w}%`, background: "var(--nsw-grey-02)", marginBottom: 6, animation: "chatPulse 1.5s ease-in-out infinite", animationDelay: `${i * 0.2}s` }} />
              ))}
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i}>
              {msg.role === "user" ? (
                <div
                  style={{
                    background: "var(--nsw-text)",
                    color: "var(--nsw-white)",
                    padding: "10px 14px",
                    fontSize: 13,
                    marginLeft: 40,
                  }}
                >
                  {msg.content}
                </div>
              ) : (
                <div
                  style={{
                    background: "var(--nsw-grey-01)",
                    border: "1px solid var(--nsw-grey-02)",
                    padding: "12px 14px",
                    fontSize: 13,
                    lineHeight: 1.7,
                  }}
                >
                  {msg.toolCalls && msg.toolCalls.length > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      {msg.toolCalls.map((tc) => (
                        <ToolCallIndicator key={tc.tool} tool={tc.tool} status={tc.status} />
                      ))}
                    </div>
                  )}
                  <div className="chat-markdown">
                    <ReactMarkdown>
                      {replaceCitesWithNumbers(msg.content, msg.citations)}
                    </ReactMarkdown>
                  </div>

                  {msg.streaming && (
                    <span
                      style={{
                        display: "inline-block",
                        width: 6,
                        height: 14,
                        background: "var(--nsw-text)",
                        marginLeft: 2,
                        animation: "blink 1s step-end infinite",
                      }}
                    />
                  )}

                  {msg.citations && msg.citations.length > 0 && (
                    <div
                      style={{
                        marginTop: 10,
                        paddingTop: 8,
                        borderTop: "1px solid var(--nsw-grey-02)",
                      }}
                    >
                      <Text
                        style={{
                          fontFamily: "'Public Sans', Arial, sans-serif",
                          fontSize: 9,
                          textTransform: "uppercase",
                          letterSpacing: "0.08em",
                          color: "var(--nsw-grey-04)",
                          marginBottom: 4,
                        }}
                      >
                        Sources
                      </Text>
                      {msg.citations.map((c) => (
                        <Text
                          key={`${c.document_title}|${c.page}`}
                          style={{
                            fontSize: 10,
                            color: "var(--nsw-brand-dark)",
                            cursor: "pointer",
                            textDecoration: "underline",
                          }}
                          onClick={async () => {
                            try {
                              const cit = await getCitation(
                                ppNumber,
                                c.document_title,
                                c.page
                              );
                              if (cit.pdf_url)
                                window.open(cit.pdf_url, "_blank");
                            } catch {}
                          }}
                        >
                          {c.document_title}{c.page > 0 ? `, p.${c.page}` : ""}
                        </Text>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </Stack>
      </div>

      {/* Suggestions */}
      {suggestions?.questions &&
        suggestions.questions.length > 0 &&
        messages.length <= 1 &&
        !isStreaming && (
          <div
            style={{
              padding: "8px 16px",
              borderTop: "1px solid var(--nsw-grey-02)",
            }}
          >
            <Group gap={4} wrap="wrap">
              {suggestions.questions.slice(0, 4).map((q, i) => (
                <Chip
                  key={i}
                  checked={false}
                  size="xs"
                  onClick={() => handleSend(q)}
                >
                  {q}
                </Chip>
              ))}
            </Group>
          </div>
        )}

      {/* Input — Claude-style integrated bar */}
      <div
        style={{
          padding: "12px 16px",
          borderTop: "1px solid var(--nsw-grey-02)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "flex-end",
            gap: 0,
            border: "2px solid var(--nsw-grey-03)",
            background: "var(--nsw-white)",
            padding: "6px 6px 6px 12px",
            transition: "border-color 0.15s",
          }}
          onFocus={(e) => (e.currentTarget.style.borderColor = "var(--nsw-brand-dark)")}
          onBlur={(e) => (e.currentTarget.style.borderColor = "var(--nsw-grey-03)")}
        >
          <Textarea
            placeholder="Ask about this proposal..."
            value={input}
            onChange={(e) => setInput(e.currentTarget.value)}
            onKeyDown={handleKeyDown}
            style={{ flex: 1 }}
            disabled={isStreaming}
            autosize
            minRows={1}
            maxRows={4}
            variant="unstyled"
            styles={{
              input: { fontSize: 13, padding: 0, minHeight: "unset" },
            }}
          />
          <ActionIcon
            onClick={() => handleSend()}
            disabled={!input.trim() || isStreaming}
            variant="filled"
            color="dark"
            size="md"
            style={{ flexShrink: 0 }}
          >
            <span style={{ fontSize: 16 }}>&uarr;</span>
          </ActionIcon>
        </div>
      </div>

      <style>{`
        @keyframes chatPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
        @keyframes blink {
          50% { opacity: 0; }
        }
        .chat-panel {
          width: 500px;
        }
        @media (max-width: 640px) {
          .chat-panel {
            width: 100% !important;
            left: 0;
            border-left: none !important;
          }
        }
        .chat-markdown p {
          margin: 0 0 8px 0;
        }
        .chat-markdown p:last-child {
          margin-bottom: 0;
        }
        .chat-markdown ul {
          margin: 4px 0 8px 0;
          padding-left: 18px;
        }
        .chat-markdown li {
          margin-bottom: 2px;
        }
        .chat-markdown strong {
          font-weight: 600;
        }
      `}</style>
    </div>
  );
}
