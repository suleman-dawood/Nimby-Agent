"use client";

import {
  AppShell as MantineAppShell,
  Group,
  Text,
  NavLink,
  Burger,
  Avatar,
  Menu,
  UnstyledButton,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { usePathname, useRouter } from "next/navigation";
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
  { label: "Settings", href: "/dashboard", auth: true },
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

  const handleLogin = useCallback(async () => {
    const g = (window as any).google;
    if (!g?.accounts?.oauth2) {
      // Script not loaded yet — try loading it
      await new Promise<void>((resolve) => {
        const script = document.createElement("script");
        script.src = "https://accounts.google.com/gsi/client";
        script.onload = () => resolve();
        script.onerror = () => resolve();
        document.head.appendChild(script);
      });
      // Wait a tick for google to init
      await new Promise((r) => setTimeout(r, 500));
    }

    const google = (window as any).google;
    if (!google?.accounts?.oauth2) {
      console.error("Google OAuth not available");
      return;
    }

    const client = google.accounts.oauth2.initTokenClient({
      client_id: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "",
      scope: "openid email profile",
      callback: async (response: any) => {
        if (response.access_token) {
          try {
            const authRes = await exchangeGoogleToken(response.access_token);
            setUser(authRes.user);
          } catch (err) {
            console.error("Auth failed:", err);
          }
        }
      },
    });
    client.requestAccessToken();
  }, []);

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
                Nimby Agent
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
                      <span
                        style={{
                          fontFamily: "'Public Sans', sans-serif",
                          fontSize: 11,
                          fontWeight: 600,
                          color: "var(--nsw-white)",
                          background: "rgba(255,255,255,0.15)",
                          padding: "3px 8px",
                          letterSpacing: "0.04em",
                        }}
                      >
                        {user.tokens_remaining} tokens
                      </span>
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
              <UnstyledButton onClick={handleLogin}>
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
