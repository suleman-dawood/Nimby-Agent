const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface AuthUser {
  id: number;
  email: string;
  name: string | null;
  avatar_url: string | null;
  tokens_remaining: number;
  tokens_used: number;
}

interface AuthResponse {
  token: string;
  user: AuthUser;
}

const TOKEN_KEY = "nimby_jwt";
const USER_KEY = "nimby_user";

export async function exchangeGoogleToken(idToken: string): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/api/auth/google`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || "Auth failed");
  }
  const data: AuthResponse = await res.json();
  localStorage.setItem(TOKEN_KEY, data.token);
  localStorage.setItem(USER_KEY, JSON.stringify(data.user));
  return data;
}

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function updateStoredUser(user: AuthUser): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getAuthHeaders(): Record<string, string> {
  const token = getStoredToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function isAuthenticated(): boolean {
  return !!getStoredToken();
}

export function signOut(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export async function fetchMe(): Promise<AuthUser | null> {
  const token = getStoredToken();
  if (!token) return null;
  try {
    const res = await fetch(`${API_BASE}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      signOut();
      return null;
    }
    const user: AuthUser = await res.json();
    updateStoredUser(user);
    return user;
  } catch {
    return null;
  }
}
