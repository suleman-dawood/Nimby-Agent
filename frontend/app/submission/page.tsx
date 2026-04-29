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
import { Autocomplete } from "@react-google-maps/api";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import { getConcerns, generateSubmission, getBrief, getCitation } from "@/lib/api";
import MapProvider from "@/components/map/MapProvider";

const CITE_RE = /\[doc:\s*.+?\s*\|\s*p\.?\s*\d+\]/g;

/** Strip markdown formatting and citations for plain-text clipboard copy. */
function toPlainText(md: string): string {
  return md
    .replace(CITE_RE, "")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/\*(.+?)\*/g, "$1")
    .replace(/^[-*]\s+/gm, "- ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function SubmissionForm() {
  const [ppNumber, setPpNumber] = useState<string>("");
  const [portalUrl, setPortalUrl] = useState<string | null>(null);
  const [selectedConcerns, setSelectedConcerns] = useState<string[]>([]);
  const [freeText, setFreeText] = useState("");
  const [userName, setUserName] = useState("");
  const [userAddress, setUserAddress] = useState("");
  const autocompleteRef = useRef<google.maps.places.Autocomplete | null>(null);

  useEffect(() => {
    const stored = sessionStorage.getItem("nimby_submission_pp");
    if (stored) setPpNumber(stored);

    const searchData = sessionStorage.getItem("nimby_search");
    if (searchData) {
      const data = JSON.parse(searchData);
      if (data.address) setUserAddress(data.address);
    }
  }, []);

  // Fetch portal URL from brief data
  const { data: briefData } = useQuery({
    queryKey: ["brief", ppNumber],
    queryFn: () => getBrief(ppNumber),
    enabled: !!ppNumber,
  });

  useEffect(() => {
    if (briefData?.portal_url) setPortalUrl(briefData.portal_url);
  }, [briefData]);

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
    const blob = new Blob([toPlainText(submitMutation.data.markdown)], {
      type: "text/plain",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `submission_${ppNumber}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleCopyAndOpen = () => {
    if (!submitMutation.data) return;
    navigator.clipboard.writeText(toPlainText(submitMutation.data.markdown));
    if (portalUrl) window.open(portalUrl, "_blank");
  };

  const onAutocompleteLoad = (ac: google.maps.places.Autocomplete) => {
    autocompleteRef.current = ac;
    ac.setBounds({ north: -28.15, south: -37.51, east: 153.64, west: 140.99 });
    ac.setOptions({ strictBounds: true });
  };

  const onPlaceChanged = () => {
    const place = autocompleteRef.current?.getPlace();
    if (place?.formatted_address) {
      setUserAddress(place.formatted_address);
    }
  };

  return (
    <Container size="md" py="xl">
      <Stack gap="lg">
        <div>
          <Text
            style={{
              fontFamily: "'Public Sans', Arial, sans-serif",
              fontSize: 11,
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              color: "var(--nsw-grey-04)",
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
              background: "var(--nsw-brand-dark)",
              margin: "8px 0 4px",
            }}
          />
          <Text style={{ color: "var(--nsw-text-light)", fontSize: 14 }}>
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
                background: "var(--nsw-white)",
                border: "1px solid var(--nsw-grey-02)",
              }}
            >
              <Text
                style={{
                  fontFamily: "'Public Sans', Arial, sans-serif",
                  fontSize: 10,
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  color: "var(--nsw-grey-04)",
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

            <div className="form-row">
              <TextInput
                label="Your name"
                placeholder="A Concerned Resident"
                value={userName}
                onChange={(e) => setUserName(e.currentTarget.value)}
                style={{ flex: 1 }}
              />
              <div style={{ flex: 1 }}>
                <Autocomplete
                  onLoad={onAutocompleteLoad}
                  onPlaceChanged={onPlaceChanged}
                  options={{
                    componentRestrictions: { country: "au" },
                    types: ["address"],
                  }}
                >
                  <TextInput
                    label="Your address"
                    placeholder="Start typing your address..."
                    value={userAddress}
                    onChange={(e) => setUserAddress(e.currentTarget.value)}
                  />
                </Autocomplete>
              </div>
            </div>

            <Button
              onClick={() => submitMutation.mutate()}
              loading={submitMutation.isPending}
              disabled={selectedConcerns.length === 0}
              style={{ alignSelf: "flex-start" }}
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
                    color: "var(--nsw-grey-04)",
                  }}
                >
                  Generating evidence-based submission...
                </Text>
              </Center>
            )}

            {submitMutation.data && (
              <>
                <div style={{ borderTop: "2px solid var(--nsw-brand-dark)" }} />

                <div
                  className="brief-content"
                  style={{
                    padding: 24,
                    background: "var(--nsw-white)",
                    border: "1px solid var(--nsw-grey-02)",
                    borderLeft: "4px solid var(--nsw-text)",
                  }}
                >
                  <ReactMarkdown>
                    {submitMutation.data.markdown.replace(CITE_RE, "")}
                  </ReactMarkdown>
                </div>

                {submitMutation.data.citations.length > 0 && (
                  <div
                    style={{
                      padding: 16,
                      background: "var(--nsw-grey-01)",
                      border: "1px solid var(--nsw-grey-02)",
                    }}
                  >
                    <Text
                      style={{
                        fontFamily: "'Public Sans', Arial, sans-serif",
                        fontSize: 10,
                        textTransform: "uppercase",
                        letterSpacing: "0.08em",
                        color: "var(--nsw-grey-04)",
                        marginBottom: 8,
                      }}
                    >
                      Sources ({submitMutation.data.citations.length})
                    </Text>
                    {submitMutation.data.citations.map((c) => (
                      <Text
                        key={`${c.document_title}|${c.page}`}
                        style={{
                          fontSize: 11,
                          color: "var(--nsw-brand-dark)",
                          cursor: "pointer",
                          textDecoration: "underline",
                          marginBottom: 2,
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

                <Group gap="sm">
                  <Button onClick={handleDownload} variant="outline">
                    Download
                  </Button>
                  <Button onClick={handleCopyAndOpen}>
                    Copy &amp; open NSW Portal
                  </Button>
                </Group>

                {portalUrl && (
                  <Text
                    style={{
                      fontSize: 12,
                      color: "var(--nsw-grey-04)",
                      lineHeight: 1.5,
                    }}
                  >
                    Clicking &ldquo;Copy &amp; open NSW Portal&rdquo; copies
                    your submission to the clipboard and opens the proposal
                    page. Paste it into the submission form on the portal.
                  </Text>
                )}
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

export default function SubmissionPage() {
  return (
    <MapProvider>
      <SubmissionForm />
    </MapProvider>
  );
}
