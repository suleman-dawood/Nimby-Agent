import { getAuthHeaders } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...getAuthHeaders(), ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `API error: ${res.status}`);
  }
  return res.json();
}

// --- Types ---

export interface GeocodeResponse {
  lat: number;
  lng: number;
  lga: string | null;
  formatted_address: string;
}

export interface NearbyPP {
  pp_number: string;
  title: string | null;
  council: string | null;
  distance_km: number;
  exhibition_start: string | null;
  exhibition_end: string | null;
  stage: string | null;
  geo_source: string | null;
  description: string | null;
  latitude: number | null;
  longitude: number | null;
}

export interface NearbyResponse {
  results: NearbyPP[];
  lga: string | null;
  policy_results: NearbyPP[];
}

export interface BriefResponse {
  pp_number: string;
  title: string | null;
  council: string | null;
  exhibition_start: string | null;
  exhibition_end: string | null;
  description: string | null;
  markdown: string;
  addresses: string | null;
  portal_url: string | null;
}

export interface CitationResponse {
  text: string;
  document_title: string;
  page: number;
  pdf_url: string | null;
}

export interface AskResponse {
  answer: string;
  citations: { document_title: string; page: number }[];
  verification_stats: { verified: number; unsupported: number; total: number };
}

export interface SubmissionResponse {
  markdown: string;
  dropped_concerns: { concern: string; reason: string }[];
  citations: { document_title: string; page: number }[];
}

// --- API calls ---

export function geocode(address: string) {
  return request<GeocodeResponse>("/api/search/geocode", {
    method: "POST",
    body: JSON.stringify({ address }),
  });
}

export function searchNearby(lat: number, lng: number, radiusKm = 10) {
  return request<NearbyResponse>(
    `/api/search/nearby?lat=${lat}&lng=${lng}&radius_km=${radiusKm}`
  );
}

export function getBrief(ppNumber: string) {
  return request<BriefResponse>(`/api/briefs/${ppNumber}`);
}

export function getCitation(ppNumber: string, documentTitle: string, page: number) {
  return request<CitationResponse>(`/api/briefs/${ppNumber}/citation`, {
    method: "POST",
    body: JSON.stringify({ document_title: documentTitle, page }),
  });
}

export function getSuggestions(ppNumber: string) {
  return request<{ questions: string[] }>(`/api/qa/${ppNumber}/suggestions`);
}

export function askQuestion(ppNumber: string, question: string) {
  return request<AskResponse>("/api/qa/ask", {
    method: "POST",
    body: JSON.stringify({ pp_number: ppNumber, question }),
  });
}

export function getImpact(ppNumber: string, address: string, distanceKm: number) {
  return request<AskResponse>("/api/qa/impact", {
    method: "POST",
    body: JSON.stringify({ pp_number: ppNumber, address, distance_km: distanceKm }),
  });
}

export interface StreamCallbacks {
  onToken: (token: string) => void;
  onCitations: (citations: { document_title: string; page: number }[]) => void;
  onToolCall?: (tool: string, status: "calling" | "done") => void;
  onError: (error: string) => void;
  onDone: () => void;
}

async function streamRequest(path: string, body: object, callbacks: StreamCallbacks) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(body),
  });

  if (!res.ok || !res.body) {
    callbacks.onError("Stream request failed");
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const data = line.slice(6);
      if (data === "[DONE]") {
        callbacks.onDone();
        return;
      }
      try {
        const parsed = JSON.parse(data);
        if (parsed.type === "token") callbacks.onToken(parsed.content);
        else if (parsed.type === "citations") callbacks.onCitations(parsed.citations);
        else if (parsed.type === "tool_call" && callbacks.onToolCall) callbacks.onToolCall(parsed.tool, parsed.status);
        else if (parsed.type === "error") callbacks.onError(parsed.content);
      } catch {}
    }
  }
  callbacks.onDone();
}

export function streamAsk(ppNumber: string, question: string, callbacks: StreamCallbacks) {
  return streamRequest("/api/qa/ask/stream", { pp_number: ppNumber, question }, callbacks);
}

export function streamImpact(ppNumber: string, address: string, distanceKm: number, callbacks: StreamCallbacks) {
  return streamRequest("/api/qa/impact/stream", { pp_number: ppNumber, address, distance_km: distanceKm }, callbacks);
}

export function streamImpactFast(ppNumber: string, address: string, distanceKm: number, callbacks: StreamCallbacks) {
  return streamRequest("/api/qa/impact-fast/stream", { pp_number: ppNumber, address, distance_km: distanceKm }, callbacks);
}

export function getConcerns() {
  return request<{ concerns: string[] }>("/api/submissions/concerns");
}

export function generateSubmission(params: {
  pp_number: string;
  concerns: string[];
  free_text?: string;
  user_name?: string;
  user_address?: string;
}) {
  return request<SubmissionResponse>("/api/submissions/generate", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

// --- Site Context ---

export interface SiteContextResponse {
  pp_number: string;
  zoning: string | null;
  max_height_m: number | null;
  max_fsr: number | null;
  min_lot_size_sqm: number | null;
  heritage_item: string | null;
  heritage_state: boolean;
  bushfire_prone: boolean;
  bushfire_category: string | null;
  flood_planning: boolean;
  landslide_risk: string | null;
  acid_sulfate_class: number | null;
  biodiversity_sensitive: boolean;
  drinking_water_catchment: boolean;
  wetlands_nearby: boolean;
  environmentally_sensitive: string | null;
  queried_at: string | null;
}

export function getSiteContext(ppNumber: string) {
  return request<SiteContextResponse>(`/api/site-context/${ppNumber}`);
}

// --- Agent Chat ---

export function streamAgentAsk(ppNumber: string, question: string, callbacks: StreamCallbacks) {
  return streamRequest("/api/qa/agent/stream", { pp_number: ppNumber, question }, callbacks);
}

// --- Watchers ---

export interface WatcherResponse {
  id: number;
  email: string;
  address: string;
  lat: number;
  lng: number;
  radius_km: number;
  webhook_url: string | null;
  active: boolean;
  created_at: string;
}

export interface NotificationResponse {
  id: number;
  pp_number: string;
  channel: string;
  status: string;
  sent_at: string;
}

export function createWatcher(data: { address: string; lat: number; lng: number; radius_km: number; webhook_url?: string }) {
  return request<WatcherResponse>("/api/watchers", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getWatchers() {
  return request<WatcherResponse[]>("/api/watchers");
}

export function deleteWatcher(id: number) {
  return request<{ status: string }>(`/api/watchers/${id}`, { method: "DELETE" });
}

export function getWatcherNotifications(id: number) {
  return request<NotificationResponse[]>(`/api/watchers/${id}/notifications`);
}

// --- Tokens ---

export function getTokenBalance() {
  return request<{ tokens_remaining: number; tokens_used: number }>("/api/tokens/balance");
}

export function getTokenHistory() {
  return request<{ usage: { id: number; action: string; tokens_spent: number; pp_number: string | null; created_at: string }[] }>("/api/tokens/history");
}
