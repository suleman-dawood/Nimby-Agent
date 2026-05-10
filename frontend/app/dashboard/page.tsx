"use client";

import {
  Container,
  Title,
  Text,
  Stack,
  Card,
  Alert,
  Badge,
  Group,
} from "@mantine/core";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { isAuthenticated, getStoredUser, type AuthUser } from "@/lib/auth";
import {
  getWatchers,
  getTokenBalance,
  getTokenHistory,
  type WatcherResponse,
  type NotificationResponse,
  getWatcherNotifications,
} from "@/lib/api";
import WatchForm from "@/components/dashboard/WatchForm";
import WatchedAddresses from "@/components/dashboard/WatchedAddresses";
import NotificationList from "@/components/dashboard/NotificationList";

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [watchers, setWatchers] = useState<WatcherResponse[]>([]);
  const [notifications, setNotifications] = useState<NotificationResponse[]>([]);
  const [tokenBalance, setTokenBalance] = useState<{ tokens_remaining: number; tokens_used: number } | null>(null);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/");
      return;
    }
    setUser(getStoredUser());
  }, [router]);

  const loadData = useCallback(async () => {
    try {
      const [w, tb] = await Promise.all([getWatchers(), getTokenBalance()]);
      setWatchers(w);
      setTokenBalance(tb);

      // Load notifications for all watchers
      const allNotifs: NotificationResponse[] = [];
      for (const watcher of w) {
        try {
          const notifs = await getWatcherNotifications(watcher.id);
          allNotifs.push(...notifs);
        } catch {}
      }
      allNotifs.sort((a, b) => new Date(b.sent_at).getTime() - new Date(a.sent_at).getTime());
      setNotifications(allNotifs);
    } catch {}
  }, []);

  useEffect(() => {
    if (user) loadData();
  }, [user, loadData]);

  if (!user) return null;

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
            Dashboard
          </Text>
          <Title order={2}>
            Welcome, {user.name || user.email}
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
            <Group justify="space-between">
              <div>
                <Text style={{ fontSize: 11, color: "var(--nsw-grey-04)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                  Token Balance
                </Text>
                <Group gap={8} mt={4}>
                  <Text style={{ fontSize: 28, fontWeight: 700 }}>
                    {tokenBalance.tokens_remaining}
                  </Text>
                  <Text style={{ fontSize: 13, color: "var(--nsw-grey-04)" }}>
                    remaining
                  </Text>
                </Group>
              </div>
              <Badge size="lg" variant="light" color="blue">
                {tokenBalance.tokens_used} used
              </Badge>
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

        {/* Notifications */}
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
            Recent Notifications
          </Text>
          <NotificationList notifications={notifications} />
        </Card>
      </Stack>
    </Container>
  );
}
