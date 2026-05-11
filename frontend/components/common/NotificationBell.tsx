"use client";

import { ActionIcon, Badge, Menu, Text, Stack, Group, Indicator } from "@mantine/core";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  getInAppNotifications,
  getUnreadCount,
  markNotificationRead,
  markAllNotificationsRead,
  type InAppNotificationResponse,
} from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";

const EVENT_COLORS: Record<string, string> = {
  new_docs: "blue",
  stage_change: "violet",
  expiry_warning: "orange",
  new_proposal: "green",
};

export default function NotificationBell() {
  const router = useRouter();
  const [unread, setUnread] = useState(0);
  const [notifications, setNotifications] = useState<InAppNotificationResponse[]>([]);
  const [loaded, setLoaded] = useState(false);

  const refresh = useCallback(async () => {
    if (!isAuthenticated()) return;
    try {
      const { count } = await getUnreadCount();
      setUnread(count);
    } catch {}
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 30000); // poll every 30s
    return () => clearInterval(interval);
  }, [refresh]);

  const loadNotifications = async () => {
    if (loaded) return;
    try {
      const notifs = await getInAppNotifications();
      setNotifications(notifs);
      setLoaded(true);
    } catch {}
  };

  const handleClick = async (notif: InAppNotificationResponse) => {
    if (!notif.read) {
      await markNotificationRead(notif.id);
      setUnread((n) => Math.max(0, n - 1));
      setNotifications((prev) =>
        prev.map((n) => (n.id === notif.id ? { ...n, read: true } : n))
      );
    }
    router.push(`/brief/${notif.pp_number}`);
  };

  const handleMarkAllRead = async () => {
    await markAllNotificationsRead();
    setUnread(0);
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  };

  if (!isAuthenticated()) return null;

  return (
    <Menu
      shadow="md"
      width={320}
      position="bottom-end"
      onOpen={loadNotifications}
    >
      <Menu.Target>
        <Indicator
          color="red"
          size={16}
          label={unread > 0 ? String(unread) : undefined}
          disabled={unread === 0}
        >
          <ActionIcon variant="subtle" size={28}>
            <span style={{ fontSize: 18, color: "var(--nsw-white)" }}>&#128276;</span>
          </ActionIcon>
        </Indicator>
      </Menu.Target>

      <Menu.Dropdown>
        <Group justify="space-between" px="sm" py={4}>
          <Text size="xs" fw={600}>Notifications</Text>
          {unread > 0 && (
            <Text
              size="xs"
              c="blue"
              style={{ cursor: "pointer" }}
              onClick={handleMarkAllRead}
            >
              Mark all read
            </Text>
          )}
        </Group>
        <Menu.Divider />

        {notifications.length === 0 && (
          <Text size="xs" c="dimmed" ta="center" py="md">
            No notifications yet
          </Text>
        )}

        {notifications.slice(0, 10).map((notif) => (
          <Menu.Item
            key={notif.id}
            onClick={() => handleClick(notif)}
            style={{ opacity: notif.read ? 0.6 : 1 }}
          >
            <Stack gap={2}>
              <Group gap={6}>
                <Badge size="xs" color={EVENT_COLORS[notif.event_type] || "gray"} variant="filled">
                  {notif.event_type.replace("_", " ")}
                </Badge>
                <Text size="xs" c="dimmed">
                  {new Date(notif.created_at).toLocaleDateString()}
                </Text>
              </Group>
              <Text size="sm" fw={notif.read ? 400 : 600} lineClamp={1}>
                {notif.title}
              </Text>
            </Stack>
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  );
}
