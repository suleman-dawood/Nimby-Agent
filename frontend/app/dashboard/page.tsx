"use client";

import {
  Container,
  Title,
  Text,
  Stack,
  Card,
  Group,
} from "@mantine/core";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { isAuthenticated, getStoredUser, type AuthUser } from "@/lib/auth";
import {
  getWatchers,
  getTokenBalance,
  getTokenHistory,
  getSubscriptions,
  getInAppNotifications,
  unsubscribe,
  type WatcherResponse,
  type NotificationResponse,
  type SubscriptionResponse,
  type InAppNotificationResponse,
  getWatcherNotifications,
} from "@/lib/api";
import WatchForm from "@/components/dashboard/WatchForm";
import WatchedAddresses from "@/components/dashboard/WatchedAddresses";
import NotificationList from "@/components/dashboard/NotificationList";

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [watchers, setWatchers] = useState<WatcherResponse[]>([]);
  const [subscriptions, setSubscriptions] = useState<SubscriptionResponse[]>([]);
  const [notifications, setNotifications] = useState<NotificationResponse[]>([]);
  const [inAppNotifs, setInAppNotifs] = useState<InAppNotificationResponse[]>([]);
  const [tokenBalance, setTokenBalance] = useState<{ tokens_remaining: number; tokens_used: number } | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/");
      return;
    }
    setUser(getStoredUser());
  }, [router]);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [w, tb, subs, appNotifs] = await Promise.all([
        getWatchers(), getTokenBalance(), getSubscriptions(), getInAppNotifications(),
      ]);
      setWatchers(w);
      setTokenBalance(tb);
      setSubscriptions(subs);
      setInAppNotifs(appNotifs);

      // Load watcher notifications
      const allNotifs: NotificationResponse[] = [];
      for (const watcher of w) {
        try {
          const notifs = await getWatcherNotifications(watcher.id);
          allNotifs.push(...notifs);
        } catch {}
      }
      allNotifs.sort((a, b) => new Date(b.sent_at).getTime() - new Date(a.sent_at).getTime());
      setNotifications(allNotifs);
    } catch {} finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) loadData();
  }, [user, loadData]);

  if (!user) return null;

  if (isLoading) {
    return (
      <Container size="md" py="md">
        <Stack gap="lg">
          {[1, 2, 3].map((i) => (
            <div key={i} style={{ height: 60, background: "var(--nsw-grey-01)", animation: "skeletonPulse 1.5s ease-in-out infinite", animationDelay: `${i * 0.2}s` }} />
          ))}
        </Stack>
        <style>{`@keyframes skeletonPulse { 0%,100% { opacity:1 } 50% { opacity:0.4 } }`}</style>
      </Container>
    );
  }

  return (
    <Container size="md" py="md">
      <Stack gap="lg">
        <div>
          <Text
            style={{
              fontFamily: "'Public Sans', Arial, sans-serif",
              fontSize: 11,
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              color: "var(--nsw-grey-04)",
              marginBottom: 4,
            }}
          >
            Settings
          </Text>
          <Title order={2}>
            {user.name || user.email}
          </Title>
          <div
            style={{
              width: 60,
              height: 3,
              background: "var(--nsw-brand-dark)",
              margin: "8px 0",
            }}
          />
        </div>

        {/* Token Balance */}
        {tokenBalance && (
          <Card withBorder padding="md">
            <Group justify="space-between" align="flex-end">
              <div>
                <Text
                  style={{
                    fontFamily: "'Public Sans', sans-serif",
                    fontSize: 11,
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                    color: "var(--nsw-grey-04)",
                    marginBottom: 4,
                  }}
                >
                  Token Balance
                </Text>
                <Group gap={8} mt={4}>
                  <Text style={{ fontSize: 28, fontWeight: 700, color: "var(--nsw-brand-dark)" }}>
                    {tokenBalance.tokens_remaining}
                  </Text>
                  <Text style={{ fontSize: 13, color: "var(--nsw-grey-04)" }}>
                    remaining
                  </Text>
                </Group>
              </div>
              <span
                style={{
                  fontFamily: "'Public Sans', sans-serif",
                  fontSize: 11,
                  fontWeight: 600,
                  color: "var(--nsw-grey-04)",
                  background: "var(--nsw-grey-01)",
                  padding: "4px 10px",
                  letterSpacing: "0.04em",
                }}
              >
                {tokenBalance.tokens_used} used
              </span>
            </Group>
          </Card>
        )}

        {/* Watch an Address */}
        <Card withBorder padding="md">
          <Text
            style={{
              fontFamily: "'Public Sans', sans-serif",
              fontSize: 11,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "var(--nsw-grey-04)",
              marginBottom: 12,
            }}
          >
            Watch an Address
          </Text>
          <WatchForm onCreated={loadData} />
        </Card>

        {/* Watched Addresses */}
        <Card withBorder padding="md">
          <Text
            style={{
              fontFamily: "'Public Sans', sans-serif",
              fontSize: 11,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "var(--nsw-grey-04)",
              marginBottom: 12,
            }}
          >
            Watched Addresses ({watchers.length})
          </Text>
          <WatchedAddresses watchers={watchers} onDeleted={loadData} />
        </Card>

        {/* Proposal Subscriptions */}
        <Card withBorder padding="md">
          <Text
            style={{
              fontFamily: "'Public Sans', sans-serif",
              fontSize: 11,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "var(--nsw-grey-04)",
              marginBottom: 12,
            }}
          >
            Proposal Subscriptions ({subscriptions.length})
          </Text>
          {subscriptions.length === 0 ? (
            <Text style={{ fontSize: 13, color: "var(--nsw-grey-04)" }}>
              No subscriptions yet. Visit a proposal and click "Subscribe to updates" to get notified about changes.
            </Text>
          ) : (
            <Stack gap="sm">
              {subscriptions.map((sub) => (
                <Card key={sub.id} withBorder padding="sm">
                  <Group justify="space-between">
                    <div>
                      <Text
                        style={{ fontSize: 14, fontWeight: 600, cursor: "pointer", color: "var(--nsw-brand-dark)" }}
                        onClick={() => router.push(`/brief/${sub.pp_number}`)}
                      >
                        {sub.pp_number}
                      </Text>
                      <Group gap={6} mt={4}>
                        {sub.notify_docs && (
                          <span style={{ fontFamily: "'Public Sans', sans-serif", fontSize: 10, fontWeight: 600, color: "var(--nsw-brand-dark)", background: "var(--nsw-grey-01)", padding: "2px 6px", textTransform: "uppercase", letterSpacing: "0.04em" }}>Docs</span>
                        )}
                        {sub.notify_stage && (
                          <span style={{ fontFamily: "'Public Sans', sans-serif", fontSize: 10, fontWeight: 600, color: "var(--nsw-brand-dark)", background: "var(--nsw-grey-01)", padding: "2px 6px", textTransform: "uppercase", letterSpacing: "0.04em" }}>Stage</span>
                        )}
                        {sub.notify_expiry && (
                          <span style={{ fontFamily: "'Public Sans', sans-serif", fontSize: 10, fontWeight: 600, color: "var(--nsw-brand-dark)", background: "var(--nsw-grey-01)", padding: "2px 6px", textTransform: "uppercase", letterSpacing: "0.04em" }}>Expiry</span>
                        )}
                      </Group>
                    </div>
                    <Text
                      size="xs"
                      c="red"
                      style={{ cursor: "pointer" }}
                      onClick={async () => {
                        if (!window.confirm(`Unsubscribe from ${sub.pp_number}?`)) return;
                        try {
                          await unsubscribe(sub.pp_number);
                          loadData();
                        } catch {}
                      }}
                    >
                      Unsubscribe
                    </Text>
                  </Group>
                </Card>
              ))}
            </Stack>
          )}
        </Card>

        {/* In-App Notifications (from subscriptions) */}
        <Card withBorder padding="md">
          <Text
            style={{
              fontFamily: "'Public Sans', sans-serif",
              fontSize: 11,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "var(--nsw-grey-04)",
              marginBottom: 12,
            }}
          >
            Subscription Notifications ({inAppNotifs.length})
          </Text>
          {inAppNotifs.length === 0 ? (
            <Text style={{ fontSize: 13, color: "var(--nsw-grey-04)" }}>
              No notifications yet. Subscribe to proposals to get notified about changes, new documents, and expiry warnings.
            </Text>
          ) : (
            <Stack gap="sm">
              {inAppNotifs.map((n) => (
                <Card
                  key={n.id}
                  withBorder
                  padding="sm"
                  style={{ cursor: "pointer", opacity: n.read ? 0.6 : 1 }}
                  onClick={() => router.push(`/brief/${n.pp_number}`)}
                >
                  <Group justify="space-between">
                    <div>
                      <Group gap={6}>
                        <span style={{
                          fontFamily: "'Public Sans', sans-serif",
                          fontSize: 10,
                          fontWeight: 600,
                          color: "var(--nsw-white)",
                          background: "var(--nsw-brand-dark)",
                          padding: "2px 6px",
                          textTransform: "uppercase",
                          letterSpacing: "0.04em",
                        }}>
                          {n.event_type.replace("_", " ")}
                        </span>
                        <Text style={{ fontSize: 11, color: "var(--nsw-grey-04)" }}>
                          {new Date(n.created_at).toLocaleDateString()}
                        </Text>
                      </Group>
                      <Text size="sm" fw={n.read ? 400 : 600} mt={4}>{n.title}</Text>
                      <Text size="xs" c="dimmed" lineClamp={1}>{n.message}</Text>
                    </div>
                  </Group>
                </Card>
              ))}
            </Stack>
          )}
        </Card>

        {/* Watcher Notifications */}
        {notifications.length > 0 && (
          <Card withBorder padding="md">
            <Text
              style={{
                fontFamily: "'Public Sans', sans-serif",
                fontSize: 11,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                color: "var(--nsw-grey-04)",
                marginBottom: 12,
              }}
            >
              Watcher Notifications ({notifications.length})
            </Text>
            <NotificationList notifications={notifications} />
          </Card>
        )}
      </Stack>
    </Container>
  );
}
