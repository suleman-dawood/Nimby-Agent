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
        <Group h="100%" px="sm" justify="space-between" wrap="nowrap">
          <Group gap={8} wrap="nowrap">
            <Burger
              opened={opened}
              onClick={toggle}
              hiddenFrom="sm"
              size="sm"
              color="white"
            />
            <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
              <div
                style={{
                  width: 28,
                  height: 28,
                  minWidth: 28,
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
                    fontSize: 12,
                    color: "var(--nsw-brand-dark)",
                    lineHeight: 1,
                  }}
                >
                  NSW
                </Text>
              </div>
              <Text
                className="header-title"
                style={{
                  fontFamily: "'Public Sans', sans-serif",
                  fontWeight: 700,
                  color: "var(--nsw-white)",
                  whiteSpace: "nowrap",
                }}
              >
                Planning Proposals
              </Text>
            </div>
          </Group>
          <Text
            className="header-subtitle"
            style={{
              fontFamily: "'Public Sans', sans-serif",
              fontSize: 12,
              color: "rgba(255,255,255,0.7)",
              whiteSpace: "nowrap",
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
