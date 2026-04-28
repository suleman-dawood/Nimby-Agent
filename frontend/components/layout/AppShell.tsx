"use client";

import {
  AppShell as MantineAppShell,
  Group,
  Text,
  NavLink,
  Burger,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { usePathname, useRouter } from "next/navigation";

const NAV_ITEMS = [
  { label: "Search", href: "/" },
  { label: "Results", href: "/results" },
  { label: "About", href: "/about" },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [opened, { toggle, close }] = useDisclosure(false);
  const pathname = usePathname();
  const router = useRouter();

  return (
    <MantineAppShell
      header={{ height: 52 }}
      navbar={{
        width: 200,
        breakpoint: "sm",
        collapsed: { mobile: !opened },
      }}
      padding="md"
    >
      <MantineAppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group gap="sm">
            <Burger
              opened={opened}
              onClick={toggle}
              hiddenFrom="sm"
              size="sm"
              color="var(--paper)"
            />
            <Text
              style={{
                fontFamily: "'DM Serif Display', serif",
                fontSize: 20,
                color: "var(--paper)",
                letterSpacing: "-0.01em",
              }}
            >
              Nimby Agent
            </Text>
          </Group>
          <Text
            style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: 10,
              color: "var(--ink-faint)",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
            }}
          >
            NSW Planning Proposals
          </Text>
        </Group>
      </MantineAppShell.Header>

      <MantineAppShell.Navbar p="xs" pt="md">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.href}
            label={item.label}
            active={pathname === item.href}
            onClick={() => {
              router.push(item.href);
              close();
            }}
          />
        ))}
      </MantineAppShell.Navbar>

      <MantineAppShell.Main>{children}</MantineAppShell.Main>
    </MantineAppShell>
  );
}
