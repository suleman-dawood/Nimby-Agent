"use client";

import { Container, Title, Text, Button, Stack } from "@mantine/core";
import { useRouter } from "next/navigation";

export default function NotFound() {
  const router = useRouter();

  return (
    <Container size="sm" py="xl">
      <Stack align="center" gap="md" py={60}>
        <Text style={{ fontSize: 64, fontWeight: 700, color: "var(--nsw-grey-03)" }}>
          404
        </Text>
        <Title order={2}>Page not found</Title>
        <Text style={{ color: "var(--nsw-text-light)", textAlign: "center" }}>
          The page you are looking for does not exist or the proposal has not been loaded yet.
        </Text>
        <Button onClick={() => router.push("/")} variant="filled">
          Back to search
        </Button>
      </Stack>
    </Container>
  );
}
