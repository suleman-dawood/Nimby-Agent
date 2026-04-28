"use client";

import {
  Text,
  TextInput,
  Button,
  Stack,
  Loader,
  Center,
  Chip,
  Group,
  ActionIcon,
} from "@mantine/core";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useState, useRef, useEffect } from "react";
import {
  askQuestion,
  getImpact,
  getSuggestions,
  type AskResponse,
} from "@/lib/api";

interface Message {
  role: "system" | "user" | "assistant";
  content: string;
  citations?: AskResponse["citations"];
  verification?: AskResponse["verification_stats"];
}

interface Props {
  ppNumber: string;
  address: string | null;
  distanceKm: number;
  opened: boolean;
  onToggle: () => void;
}

const CITE_RE = /\[doc:\s*.+?\s*\|\s*p\.?\s*\d+\]/g;

export default function ChatPanel({
  ppNumber,
  address,
  distanceKm,
  opened,
  onToggle,
}: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [impactLoaded, setImpactLoaded] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: suggestions } = useQuery({
    queryKey: ["suggestions", ppNumber],
    queryFn: () => getSuggestions(ppNumber),
    enabled: opened,
  });

  // Load personalized impact on first open
  const impactMutation = useMutation({
    mutationFn: () => getImpact(ppNumber, address || "", distanceKm),
    onSuccess: (data) => {
      setMessages([
        {
          role: "assistant",
          content: data.answer.replace(CITE_RE, ""),
          citations: data.citations,
          verification: data.verification_stats,
        },
      ]);
      setImpactLoaded(true);
    },
    onError: () => {
      setMessages([
        {
          role: "assistant",
          content:
            "I couldn't generate a personalized impact summary. Ask me anything about this proposal.",
        },
      ]);
      setImpactLoaded(true);
    },
  });

  useEffect(() => {
    if (opened && !impactLoaded && address) {
      impactMutation.mutate();
    }
  }, [opened]);

  const askMutation = useMutation({
    mutationFn: (q: string) => askQuestion(ppNumber, q),
    onSuccess: (data) => {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer.replace(CITE_RE, ""),
          citations: data.citations,
          verification: data.verification_stats,
        },
      ]);
    },
    onError: () => {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Sorry, I couldn't find an answer." },
      ]);
    },
  });

  const handleSend = (q?: string) => {
    const question = q || input;
    if (!question.trim()) return;

    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setInput("");
    askMutation.mutate(question);
  };

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [messages, askMutation.isPending]);

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
          {impactMutation.isPending && (
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
                  {msg.content}

                  {msg.citations && msg.citations.length > 0 && (
                    <div
                      style={{
                        marginTop: 8,
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
                        Sources ({msg.citations.length})
                      </Text>
                      {[
                        ...new Set(
                          msg.citations.map(
                            (c) => `${c.document_title}, p.${c.page}`
                          )
                        ),
                      ].map((label) => (
                        <Text
                          key={label}
                          style={{
                            fontSize: 10,
                            color: "var(--ink-faint)",
                          }}
                        >
                          {label}
                        </Text>
                      ))}
                    </div>
                  )}

                  {msg.verification && msg.verification.total > 0 && (
                    <Text
                      style={{
                        fontSize: 9,
                        color: "var(--ink-faint)",
                        fontFamily: "'IBM Plex Mono', monospace",
                        textTransform: "uppercase",
                        letterSpacing: "0.06em",
                        marginTop: 6,
                      }}
                    >
                      Verified: {msg.verification.verified}/
                      {msg.verification.total}
                    </Text>
                  )}
                </div>
              )}
            </div>
          ))}

          {askMutation.isPending && (
            <Center py="sm">
              <Loader size="xs" color="dark" />
              <Text
                ml="xs"
                style={{ fontSize: 11, color: "var(--ink-faint)" }}
              >
                Searching documents...
              </Text>
            </Center>
          )}
        </Stack>
      </div>

      {/* Suggestions */}
      {suggestions?.questions &&
        suggestions.questions.length > 0 &&
        messages.length <= 1 && (
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
        }}
      >
        <TextInput
          placeholder="Ask about this proposal..."
          value={input}
          onChange={(e) => setInput(e.currentTarget.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          style={{ flex: 1 }}
          disabled={askMutation.isPending}
        />
        <Button
          onClick={() => handleSend()}
          disabled={!input.trim() || askMutation.isPending}
          loading={askMutation.isPending}
        >
          Send
        </Button>
      </div>
    </div>
  );
}
