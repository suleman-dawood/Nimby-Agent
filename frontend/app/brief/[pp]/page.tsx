"use client";

import {
  Container,
  Title,
  Text,
  Stack,
  Group,
  Badge,
  Button,
  Loader,
  Center,
  Alert,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { getBrief, getCitation } from "@/lib/api";
import BriefViewer from "@/components/brief/BriefViewer";
import ChatPanel from "@/components/brief/ChatPanel";

export default function BriefPage() {
  const params = useParams();
  const ppNumber = params.pp as string;
  const router = useRouter();

  const [chatOpened, setChatOpened] = useState(false);
  const [userAddress, setUserAddress] = useState<string | null>(null);
  const [distanceKm, setDistanceKm] = useState(0);

  useEffect(() => {
    const stored = sessionStorage.getItem("nimby_search");
    if (stored) {
      const data = JSON.parse(stored);
      setUserAddress(data.address || null);
      const pp = [...(data.results || []), ...(data.policy_results || [])].find(
        (r: { pp_number: string }) => r.pp_number === ppNumber
      );
      if (pp) setDistanceKm(pp.distance_km || 0);
    }
  }, [ppNumber]);

  const { data, isLoading, error } = useQuery({
    queryKey: ["brief", ppNumber],
    queryFn: () => getBrief(ppNumber),
    enabled: !!ppNumber,
  });

  const handleCitationClick = async (docTitle: string, page: number) => {
    try {
      const citation = await getCitation(ppNumber, docTitle, page);
      if (citation.pdf_url) {
        window.open(citation.pdf_url, "_blank");
      }
    } catch {
      // Silently fail if citation not found
    }
  };

  if (isLoading) {
    return (
      <Center py="xl">
        <Loader color="dark" />
      </Center>
    );
  }

  if (error) {
    return (
      <Container size="md" py="xl">
        <Alert color="red" title="Error">
          {error instanceof Error ? error.message : "Failed to load brief"}
        </Alert>
      </Container>
    );
  }

  if (!data) return null;

  const daysLeft = data.exhibition_end
    ? Math.ceil(
        (new Date(data.exhibition_end).getTime() - Date.now()) / 86400000
      )
    : null;

  return (
    <>
      <Container
        size="md"
        py="xl"
        className="brief-container"
        style={{
          transition: "margin-right 0.2s ease",
          ...(chatOpened ? { marginRight: 396 } : {}),
        }}
      >
        <Stack gap="lg">
          <div>
            <Group justify="space-between" align="flex-start" mb={8}>
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
                  Planning Brief
                </Text>
                <Title order={2} style={{ fontSize: 28 }}>
                  {data.pp_number}
                </Title>
              </div>
              {daysLeft !== null && (
                <Badge
                  color={
                    daysLeft <= 0 ? "red" : daysLeft <= 7 ? "orange" : "green"
                  }
                >
                  {daysLeft > 0 ? `${daysLeft}d left` : "Closed"}
                </Badge>
              )}
            </Group>
            <div
              style={{
                width: 60,
                height: 3,
                background: "var(--nsw-brand-dark)",
                marginBottom: 8,
              }}
            />
            <Text style={{ fontSize: 13, color: "var(--nsw-text-light)" }}>
              {data.council}
              {data.exhibition_end &&
                ` \u2014 Exhibition closes ${data.exhibition_end}`}
            </Text>
          </div>

          <BriefViewer
            markdown={data.markdown}
            onCitationClick={handleCitationClick}
          />

          <div
            style={{
              borderTop: "1px solid var(--nsw-grey-02)",
              paddingTop: 16,
              display: "flex",
              flexWrap: "wrap",
              gap: 12,
            }}
          >
            <Button
              onClick={() => {
                sessionStorage.setItem("nimby_submission_pp", ppNumber);
                router.push("/submission");
              }}
            >
              Draft a submission
            </Button>
            <Button variant="outline" onClick={() => router.push("/results")}>
              Back to results
            </Button>
            {!chatOpened && (
              <Button variant="outline" onClick={() => setChatOpened(true)}>
                Ask questions
              </Button>
            )}
          </div>
        </Stack>
      </Container>

      <ChatPanel
        ppNumber={ppNumber}
        address={userAddress}
        distanceKm={distanceKm}
        opened={chatOpened}
        onToggle={() => setChatOpened(!chatOpened)}
      />
    </>
  );
}
