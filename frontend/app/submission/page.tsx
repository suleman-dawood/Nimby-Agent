"use client";

import {
  Container,
  Title,
  Text,
  Stack,
  Chip,
  Group,
  TextInput,
  Textarea,
  Button,
  Alert,
  Loader,
  Center,
  List,
} from "@mantine/core";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import { getConcerns, generateSubmission } from "@/lib/api";

export default function SubmissionPage() {
  const [ppNumber, setPpNumber] = useState<string>("");
  const [selectedConcerns, setSelectedConcerns] = useState<string[]>([]);
  const [freeText, setFreeText] = useState("");
  const [userName, setUserName] = useState("");
  const [userAddress, setUserAddress] = useState("");

  useEffect(() => {
    const stored = sessionStorage.getItem("nimby_submission_pp");
    if (stored) setPpNumber(stored);
  }, []);

  const { data: concernsData } = useQuery({
    queryKey: ["concerns"],
    queryFn: getConcerns,
  });

  const submitMutation = useMutation({
    mutationFn: () =>
      generateSubmission({
        pp_number: ppNumber,
        concerns: selectedConcerns,
        free_text: freeText,
        user_name: userName || undefined,
        user_address: userAddress || undefined,
      }),
  });

  const handleDownload = () => {
    if (!submitMutation.data) return;
    const blob = new Blob([submitMutation.data.markdown], {
      type: "text/markdown",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `submission_${ppNumber}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Container size="md" py="xl">
      <Stack gap="lg">
        <div>
          <Text
            style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: 11,
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              color: "var(--ink-faint)",
              marginBottom: 8,
            }}
          >
            Draft Submission
          </Text>
          <Title order={2} style={{ fontSize: 28 }}>
            Have your say
          </Title>
          <div
            style={{
              width: 60,
              height: 3,
              background: "var(--accent)",
              margin: "8px 0 4px",
            }}
          />
          <Text style={{ color: "var(--ink-light)", fontSize: 14 }}>
            Select your concerns and we&apos;ll draft an evidence-based
            submission for{" "}
            <strong>{ppNumber || "the proposal"}</strong>, citing the
            proposal&apos;s own documents.
          </Text>
        </div>

        {!ppNumber && (
          <Alert color="yellow" title="No proposal selected">
            Go to a proposal brief first, then click &ldquo;Draft a
            submission&rdquo;.
          </Alert>
        )}

        {ppNumber && (
          <>
            <div
              style={{
                padding: 20,
                background: "var(--paper-bright)",
                border: "1px solid var(--rule)",
              }}
            >
              <Text
                style={{
                  fontFamily: "'IBM Plex Mono', monospace",
                  fontSize: 10,
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  color: "var(--ink-faint)",
                  marginBottom: 12,
                }}
              >
                Select Concerns
              </Text>
              <Chip.Group
                multiple
                value={selectedConcerns}
                onChange={setSelectedConcerns}
              >
                <Group gap="xs" wrap="wrap">
                  {(concernsData?.concerns || []).map((c) => (
                    <Chip key={c} value={c}>
                      {c}
                    </Chip>
                  ))}
                </Group>
              </Chip.Group>
            </div>

            <Textarea
              label="Additional concerns"
              placeholder="Describe any specific concerns not listed above..."
              value={freeText}
              onChange={(e) => setFreeText(e.currentTarget.value)}
              minRows={3}
            />

            <Group grow>
              <TextInput
                label="Your name"
                placeholder="A Concerned Resident"
                value={userName}
                onChange={(e) => setUserName(e.currentTarget.value)}
              />
              <TextInput
                label="Your address"
                placeholder="Street address"
                value={userAddress}
                onChange={(e) => setUserAddress(e.currentTarget.value)}
              />
            </Group>

            <Button
              onClick={() => submitMutation.mutate()}
              loading={submitMutation.isPending}
              disabled={selectedConcerns.length === 0}
              size="lg"
            >
              Generate Submission
            </Button>

            {submitMutation.isPending && (
              <Center py="md">
                <Loader size="sm" color="dark" />
                <Text
                  ml="sm"
                  style={{
                    fontSize: 12,
                    color: "var(--ink-faint)",
                  }}
                >
                  Generating evidence-based submission...
                </Text>
              </Center>
            )}

            {submitMutation.data && (
              <>
                <div style={{ borderTop: "2px solid var(--rule-heavy)" }} />

                <div
                  style={{
                    padding: 24,
                    background: "var(--paper-bright)",
                    border: "1px solid var(--rule)",
                    borderLeft: "4px solid var(--ink)",
                  }}
                >
                  <Text
                    size="sm"
                    style={{
                      whiteSpace: "pre-wrap",
                      lineHeight: 1.75,
                      color: "var(--ink)",
                    }}
                  >
                    {submitMutation.data.markdown}
                  </Text>
                </div>

                {submitMutation.data.dropped_concerns.length > 0 && (
                  <Alert color="yellow" title="Insufficient evidence">
                    <List size="sm">
                      {submitMutation.data.dropped_concerns.map((d) => (
                        <List.Item key={d.concern}>
                          <strong>{d.concern}:</strong> {d.reason}
                        </List.Item>
                      ))}
                    </List>
                  </Alert>
                )}

                <Group justify="space-between" align="center">
                  <Button onClick={handleDownload}>Download</Button>
                  <Text
                    style={{
                      fontFamily: "'IBM Plex Mono', monospace",
                      fontSize: 10,
                      color: "var(--ink-faint)",
                      textTransform: "uppercase",
                      letterSpacing: "0.06em",
                    }}
                  >
                    Verified: {submitMutation.data.citation_stats.verified}/
                    {submitMutation.data.citation_stats.total} citations
                  </Text>
                </Group>
              </>
            )}

            {submitMutation.error && (
              <Alert color="red" title="Failed">
                {submitMutation.error instanceof Error
                  ? submitMutation.error.message
                  : "Failed to generate submission"}
              </Alert>
            )}
          </>
        )}
      </Stack>
    </Container>
  );
}
