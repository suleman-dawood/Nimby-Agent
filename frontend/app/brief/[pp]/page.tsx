"use client";

import {
  Container,
  Title,
  Text,
  Stack,
  Group,
  Badge,
  Button,
  Alert,
  Tabs,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { getBrief, getCitation, subscribe, unsubscribe, getSubscriptions } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";
import BriefViewer from "@/components/brief/BriefViewer";
import ChatPanel from "@/components/brief/ChatPanel";
import SiteContextTab from "@/components/brief/SiteContextTab";
import TimelineTab from "@/components/brief/TimelineTab";

export default function BriefPage() {
  const params = useParams();
  const ppNumber = params.pp as string;
  const router = useRouter();

  const [chatOpened, setChatOpened] = useState(false);
  const [userAddress, setUserAddress] = useState<string | null>(null);
  const [distanceKm, setDistanceKm] = useState(0);
  const [subscribed, setSubscribed] = useState(false);
  const [subLoading, setSubLoading] = useState(false);

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
    // Check subscription status
    if (isAuthenticated()) {
      getSubscriptions().then((subs) => {
        setSubscribed(subs.some((s) => s.pp_number === ppNumber));
      }).catch(() => {});
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
      <Container size="md" py="xl">
        <Stack gap="md">
          <div style={{ height: 12, width: "30%", background: "var(--nsw-grey-02)", animation: "skeletonPulse 1.5s ease-in-out infinite" }} />
          <div style={{ height: 28, width: "50%", background: "var(--nsw-grey-02)", animation: "skeletonPulse 1.5s ease-in-out infinite", animationDelay: "0.1s" }} />
          <div style={{ width: 60, height: 3, background: "var(--nsw-grey-02)" }} />
          <div style={{ height: 14, width: "40%", background: "var(--nsw-grey-02)", animation: "skeletonPulse 1.5s ease-in-out infinite", animationDelay: "0.2s" }} />
          {[1, 2, 3, 4].map((i) => (
            <div key={i} style={{ height: 12, width: `${90 - i * 10}%`, background: "var(--nsw-grey-02)", animation: "skeletonPulse 1.5s ease-in-out infinite", animationDelay: `${i * 0.15}s` }} />
          ))}
        </Stack>
        <style>{`@keyframes skeletonPulse { 0%,100% { opacity:1 } 50% { opacity:0.4 } }`}</style>
      </Container>
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
          ...(chatOpened ? { marginRight: 516 } : {}),
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

          <Tabs defaultValue="brief" style={{ marginTop: 8 }}>
            <Tabs.List>
              <Tabs.Tab value="brief">Brief</Tabs.Tab>
              <Tabs.Tab value="site-context">Site Context</Tabs.Tab>
              <Tabs.Tab value="timeline">Timeline</Tabs.Tab>
            </Tabs.List>

            <Tabs.Panel value="brief" pt="md">
              <BriefViewer
                markdown={data.markdown}
                onCitationClick={handleCitationClick}
              />
            </Tabs.Panel>

            <Tabs.Panel value="site-context" pt="md">
              <SiteContextTab ppNumber={ppNumber} />
            </Tabs.Panel>

            <Tabs.Panel value="timeline" pt="md">
              <TimelineTab ppNumber={ppNumber} />
            </Tabs.Panel>
          </Tabs>

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
            <Button
              variant="outline"
              onClick={() => {
                window.open(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/briefs/${ppNumber}/export-pdf`, "_blank");
              }}
            >
              Download PDF
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                navigator.clipboard.writeText(window.location.href);
                alert("Link copied to clipboard");
              }}
            >
              Share link
            </Button>
            {isAuthenticated() && (
              <Button
                variant={subscribed ? "light" : "outline"}
                color={subscribed ? "green" : "blue"}
                loading={subLoading}
                onClick={async () => {
                  setSubLoading(true);
                  try {
                    if (subscribed) {
                      await unsubscribe(ppNumber);
                      setSubscribed(false);
                    } else {
                      await subscribe(ppNumber, { notify_docs: true, notify_stage: true, notify_expiry: true });
                      setSubscribed(true);
                    }
                  } catch {}
                  setSubLoading(false);
                }}
              >
                {subscribed ? "Subscribed \u2713" : "Subscribe to updates"}
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
      <style>{`
        @media (max-width: 640px) {
          .brief-container { margin-right: 0 !important; }
        }
      `}</style>
    </>
  );
}
