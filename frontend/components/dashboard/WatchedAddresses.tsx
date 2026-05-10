"use client";

import { Card, Text, Group, Badge, Button, Stack } from "@mantine/core";
import type { WatcherResponse } from "@/lib/api";
import { deleteWatcher } from "@/lib/api";

interface Props {
  watchers: WatcherResponse[];
  onDeleted: () => void;
}

export default function WatchedAddresses({ watchers, onDeleted }: Props) {
  if (watchers.length === 0) {
    return (
      <Text style={{ fontSize: 13, color: "var(--nsw-grey-04)" }}>
        No addresses watched yet. Add one above to get notified about nearby proposals.
      </Text>
    );
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteWatcher(id);
      onDeleted();
    } catch {}
  };

  return (
    <Stack gap="sm">
      {watchers.map((w) => (
        <Card key={w.id} withBorder padding="sm">
          <Group justify="space-between">
            <div>
              <Text style={{ fontSize: 14, fontWeight: 600 }}>{w.address}</Text>
              <Group gap={8} mt={4}>
                <Badge size="xs" variant="light" color="blue">
                  {w.radius_km}km radius
                </Badge>
                <Text style={{ fontSize: 11, color: "var(--nsw-grey-04)" }}>
                  Since {new Date(w.created_at).toLocaleDateString()}
                </Text>
              </Group>
            </div>
            <Button
              size="xs"
              variant="subtle"
              color="red"
              onClick={() => handleDelete(w.id)}
            >
              Unwatch
            </Button>
          </Group>
        </Card>
      ))}
    </Stack>
  );
}
