"use client";

import {
  Text,
  Textarea,
  Button,
  Stack,
  Loader,
  Center,
  Chip,
  Group,
  ActionIcon,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useState, useRef, useEffect, useCallback } from "react";
import {
  getCitation,
  getSuggestions,
  streamAsk,
  streamImpact,
} from "@/lib/api";

interface Citation {
  document_title: string;
  page: number;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  streaming?: boolean;
}

interface Props {
  ppNumber: string;
  address: string | null;
  distanceKm: number;
  opened: boolean;
  onToggle: () => void;
}

const CITE_RE = /\[doc:\s*.+?\s*\|\s*p\.?\s*\d+\]/g;

function renderMarkdown(text: string) {
  // Strip citation markers
  let clean = text.replace(CITE_RE, "");

  // Bold
  clean = clean.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  // Italic
  clean = clean.replace(/\*(.+?)\*/g, "<em>$1</em>");
  // Bullet lists
  clean = clean.replace(/^[-•]\s+(.+)$/gm, "<li>$1</li>");
  clean = clean.replace(new RegExp("(<li>.*</li>\\n?)+", "gs"), (match) => `<ul>${match}</ul>`);
  // Paragraphs (double newline)
  clean = clean
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean)
    .map((p) => (p.startsWith("<ul>") || p.startsWith("<li>") ? p : `<p>${p}</p>`))
    .join("");
  // Single newlines within paragraphs
  clean = clean.replace(/(?<!<\/li>)\n(?!<)/g, "<br />");

  return clean;
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
  const [impactLoaded, setImpactLoaded] = useState(false);
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
        onError: (e: string) => void;
        onDone: () => void;
      }) => Promise<void>
    ) => {
      setIsStreaming(true);

      // Add empty assistant message
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "", streaming: true },
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
          setIsStreaming(false);
          scrollToBottom();
        },
      });
    },
    [scrollToBottom]
  );

  // Load impact on first open
  useEffect(() => {
    if (opened && !impactLoaded && address) {
      setImpactLoaded(true);
      startStream((cb) =>
        streamImpact(ppNumber, address, distanceKm, cb)
      );
    }
  }, [opened, impactLoaded, address, ppNumber, distanceKm, startStream]);

  const handleSend = (q?: string) => {
    const question = q || input;
    if (!question.trim() || isStreaming) return;

    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setInput("");

    startStream((cb) => streamAsk(ppNumber, question, cb));
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
          background: "var(--ink)",
          color: "var(--paper)",
          padding: "16px 8px",
          cursor: "pointer",
          writingMode: "vertical-rl",
          textOrientation: "mixed",
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 11,
          textTransform: "uppercase",
          letterSpacing: "0.1em",
          zIndex: 100,
        }}
      >
        Chat
      </div>
    );
  }

  return (
    <div
      style={{
        position: "fixed",
        right: 0,
        top: 52,
        bottom: 0,
        width: 380,
        background: "var(--paper-bright)",
        borderLeft: "2px solid var(--rule-heavy)",
        display: "flex",
        flexDirection: "column",
        zIndex: 100,
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "12px 16px",
          borderBottom: "2px solid var(--rule-heavy)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <Text
          style={{
            fontFamily: "'DM Serif Display', serif",
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
          {messages.length === 0 && isStreaming && (
            <Center py="xl">
              <Loader size="sm" color="dark" />
              <Text
                ml="sm"
                style={{ fontSize: 12, color: "var(--ink-faint)" }}
              >
                Analysing impact on your address...
              </Text>
            </Center>
          )}

          {messages.map((msg, i) => (
            <div key={i}>
              {msg.role === "user" ? (
                <div
                  style={{
                    background: "var(--ink)",
                    color: "var(--paper)",
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
                    background: "var(--paper-warm)",
                    border: "1px solid var(--rule)",
                    padding: "12px 14px",
                    fontSize: 13,
                    lineHeight: 1.7,
                  }}
                >
                  <div
                    className="chat-markdown"
                    dangerouslySetInnerHTML={{
                      __html: renderMarkdown(msg.content),
                    }}
                  />

                  {msg.streaming && (
                    <span
                      style={{
                        display: "inline-block",
                        width: 6,
                        height: 14,
                        background: "var(--ink)",
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
                        borderTop: "1px solid var(--rule)",
                      }}
                    >
                      <Text
                        style={{
                          fontFamily: "'IBM Plex Mono', monospace",
                          fontSize: 9,
                          textTransform: "uppercase",
                          letterSpacing: "0.08em",
                          color: "var(--ink-faint)",
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
                            color: "var(--accent)",
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
                          {c.document_title}, p.{c.page}
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
              borderTop: "1px solid var(--rule)",
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

      {/* Input */}
      <div
        style={{
          padding: "12px 16px",
          borderTop: "2px solid var(--rule-heavy)",
          display: "flex",
          gap: 8,
          alignItems: "flex-end",
        }}
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
        />
        <Button
          onClick={() => handleSend()}
          disabled={!input.trim() || isStreaming}
          style={{ alignSelf: "flex-end" }}
        >
          Send
        </Button>
      </div>

      <style>{`
        @keyframes blink {
          50% { opacity: 0; }
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
