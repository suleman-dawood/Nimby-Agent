"use client";

import { Card, Text, Badge, Group, Stack } from "@mantine/core";
import { useRouter } from "next/navigation";
import type { NotificationResponse } from "@/lib/api";

interface Props {
  notifications: NotificationResponse[];
}

export default function NotificationList({ notifications }: Props) {
  const router = useRouter();

  if (notifications.length === 0) {
    return (
      <Text style={{ fontSize: 13, color: "var(--nsw-grey-04)" }}>
        No notifications yet. You will be notified when new proposals appear near your watched addresses.
      </Text>
    );
  }

  return (
    <Stack gap="sm">
      {notifications.map((n) => (
        <Card
          key={n.id}
          withBorder
          padding="sm"
          style={{ cursor: "pointer" }}
          onClick={() => router.push(`/brief/${n.pp_number}`)}
        >
          <Group justify="space-between">
            <div>
              <Text style={{ fontSize: 13, fontWeight: 600 }}>{n.pp_number}</Text>
              <Text style={{ fontSize: 11, color: "var(--nsw-grey-04)" }}>
                {new Date(n.sent_at).toLocaleString()}
              </Text>
            </div>
            <Group gap={6}>
              <Badge size="xs" variant="light" color={n.channel === "email" ? "blue" : "violet"}>
                {n.channel}
              </Badge>
              <Badge size="xs" variant="light" color={n.status === "sent" ? "green" : "red"}>
                {n.status}
              </Badge>
            </Group>
          </Group>
        </Card>
      ))}
    </Stack>
  );
}
