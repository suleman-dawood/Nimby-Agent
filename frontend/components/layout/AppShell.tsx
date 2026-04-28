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
      header={{ height: 56 }}
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
              color="white"
            />
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div
                style={{
                  width: 32,
                  height: 32,
                  background: "var(--nsw-white)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Text
                  style={{
                    fontFamily: "'Public Sans', sans-serif",
                    fontWeight: 700,
                    fontSize: 14,
                    color: "var(--nsw-brand-dark)",
                    lineHeight: 1,
                  }}
                >
                  NSW
                </Text>
              </div>
              <Text
                style={{
                  fontFamily: "'Public Sans', sans-serif",
                  fontSize: 18,
                  fontWeight: 700,
                  color: "var(--nsw-white)",
                }}
              >
                Planning Proposals
              </Text>
            </div>
          </Group>
          <Text
            style={{
              fontFamily: "'Public Sans', sans-serif",
              fontSize: 12,
              color: "rgba(255,255,255,0.7)",
            }}
          >
            Nimby Agent
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
