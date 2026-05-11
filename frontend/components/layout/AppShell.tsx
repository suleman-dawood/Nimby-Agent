"use client";

import {
  AppShell as MantineAppShell,
  Group,
  Text,
  NavLink,
  Burger,
  Badge,
  Avatar,
  Menu,
  UnstyledButton,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { usePathname, useRouter } from "next/navigation";
import { useGoogleLogin } from "@react-oauth/google";
import { useEffect, useState, useCallback } from "react";
import {
  exchangeGoogleToken,
  getStoredUser,
  signOut,
  fetchMe,
  type AuthUser,
} from "@/lib/auth";
import NotificationBell from "@/components/common/NotificationBell";

const NAV_ITEMS = [
  { label: "Search", href: "/", auth: false },
  { label: "Results", href: "/results", auth: false },
  { label: "Dashboard", href: "/dashboard", auth: true },
  { label: "About", href: "/about", auth: false },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [opened, { toggle, close }] = useDisclosure(false);
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    const stored = getStoredUser();
    if (stored) {
      setUser(stored);
      fetchMe().then((u) => { if (u) setUser(u); });
    }
  }, []);

  const login = useGoogleLogin({
    onSuccess: async (response) => {
      try {
        const authRes = await exchangeGoogleToken(response.access_token);
        setUser(authRes.user);
      } catch (err) {
        console.error("Auth failed:", err);
      }
    },
    onError: () => console.error("Google login failed"),
  });

  const handleSignOut = useCallback(() => {
    signOut();
    setUser(null);
  }, []);

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

          <Group gap={8} wrap="nowrap">
            {user ? (
              <>
              <NotificationBell />
              <Menu shadow="md" width={200}>
                <Menu.Target>
                  <UnstyledButton>
                    <Group gap={6} wrap="nowrap">
                      <Badge
                        size="sm"
                        variant="light"
                        color="green"
                        style={{ fontFamily: "'Public Sans', sans-serif" }}
                      >
                        {user.tokens_remaining} tokens
                      </Badge>
                      <Avatar
                        src={user.avatar_url}
                        alt={user.name || "User"}
                        size={28}
                        radius="xl"
                      />
                    </Group>
                  </UnstyledButton>
                </Menu.Target>
                <Menu.Dropdown>
                  <Menu.Label>{user.name || user.email}</Menu.Label>
                  <Menu.Item onClick={handleSignOut}>Sign out</Menu.Item>
                </Menu.Dropdown>
              </Menu>
              </>
            ) : (
              <UnstyledButton onClick={() => login()}>
                <Text
                  style={{
                    fontFamily: "'Public Sans', sans-serif",
                    fontSize: 13,
                    fontWeight: 600,
                    color: "var(--nsw-white)",
                    whiteSpace: "nowrap",
                  }}
                >
                  Sign in
                </Text>
              </UnstyledButton>
            )}
          </Group>
        </Group>
      </MantineAppShell.Header>

      <MantineAppShell.Navbar p="xs" pt="md">
        {NAV_ITEMS.filter((item) => !item.auth || !!user).map((item) => (
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
