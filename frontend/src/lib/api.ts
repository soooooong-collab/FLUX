const API = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

function authHeaders(): HeadersInit {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("flux_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ── Auth ──

export async function register(email: string, password: string, displayName?: string) {
  const res = await fetch(`${API}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, display_name: displayName }),
  });
  if (!res.ok) throw new Error(`Register failed: ${res.status}`);
  const data = await res.json();
  localStorage.setItem("flux_token", data.access_token);
  return data;
}

export async function login(email: string, password: string) {
  const res = await fetch(`${API}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(`Login failed: ${res.status}`);
  const data = await res.json();
  localStorage.setItem("flux_token", data.access_token);
  return data;
}

/**
 * Ensure user is authenticated. If no token exists, auto-creates a guest account.
 * Call this before any API that requires authentication.
 */
export async function ensureAuth(): Promise<void> {
  if (typeof window === "undefined") return;
  const token = localStorage.getItem("flux_token");
  if (token) {
    // Validate existing token
    try {
      const res = await fetch(`${API}/api/auth/me`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) return; // token is valid
    } catch { /* token invalid, fall through to re-register */ }
    localStorage.removeItem("flux_token");
  }
  // Auto-register as guest
  const guestId = `guest_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  await register(`${guestId}@flux.local`, `flux-guest-${guestId}`, "Guest User");
}

export function isLoggedIn(): boolean {
  if (typeof window === "undefined") return false;
  return !!localStorage.getItem("flux_token");
}

export function logout(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem("flux_token");
}

export async function getCurrentUser(): Promise<{ id: string; email: string; display_name: string | null; plan_tier: string } | null> {
  const res = await fetch(`${API}/api/auth/me`, { headers: authHeaders() });
  if (!res.ok) return null;
  return res.json();
}

export async function deleteProject(id: string) {
  const res = await fetch(`${API}/api/projects/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Delete project failed: ${res.status}`);
  return res.json();
}

// ── Projects ──

export interface ProjectCreate {
  brand_name: string;
  product_service?: string;
  industry?: string;
  target_audience?: string;
  main_goal?: string;
  campaign_success?: string;
  current_problem?: string;
  constraints?: string;
  channels?: string[];
  budget?: string;
  brief_raw_text?: string;
  director_type?: string;
}

export async function createProject(data: ProjectCreate) {
  const res = await fetch(`${API}/api/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Create project failed: ${res.status}`);
  return res.json();
}

export async function listProjects() {
  const res = await fetch(`${API}/api/projects`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`List projects failed: ${res.status}`);
  return res.json();
}

export async function getProject(id: string) {
  const res = await fetch(`${API}/api/projects/${id}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`Get project failed: ${res.status}`);
  return res.json();
}

export async function parseBriefPdf(file: File): Promise<{ text: string; filename: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API}/api/projects/parse-pdf`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });
  if (!res.ok) throw new Error(`PDF 파싱 실패: ${res.status}`);
  return res.json();
}

export async function uploadBriefPdf(projectId: string, file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API}/api/projects/${projectId}/upload-brief`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });
  if (!res.ok) throw new Error(`브리프 업로드 실패: ${res.status}`);
  return res.json();
}

// ── Discussion Turn Types ──

export interface DiscussionTurn {
  step_key: string;
  speaker: string;
  speaker_label: string;
  speaker_label_kr: string;
  role: "moderator" | "lead" | "support";
  content: string;
  turn_number: number;
  type: "framing" | "analysis" | "reaction" | "synthesis";
  total_turns: number;
}

// ── Pipeline ──

export function runPipelineSSE(
  projectId: string,
  directorType?: string,
  onEvent?: (event: string, data: any) => void,
  onError?: (err: any) => void,
  onComplete?: () => void,
) {
  const token = localStorage.getItem("flux_token");

  fetch(`${API}/api/pipeline/${projectId}/run`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ director_type: directorType }),
  }).then(async (res) => {
    if (!res.ok) {
      onError?.(new Error(`Pipeline failed: ${res.status}`));
      return;
    }
    const reader = res.body?.getReader();
    if (!reader) {
      onError?.(new Error("Pipeline stream is unavailable."));
      return;
    }

    const decoder = new TextDecoder();
    let buffer = "";
    let currentEvent = "message";
    let currentDataLines: string[] = [];
    let hasServerError = false;
    let didComplete = false;

    const dispatchEvent = () => {
      if (currentDataLines.length === 0) {
        currentEvent = "message";
        return;
      }

      const rawData = currentDataLines.join("\n");
      let payload: any = rawData;
      try {
        payload = JSON.parse(rawData);
      } catch {
        // Keep raw string payload for non-JSON SSE data.
      }

      onEvent?.(currentEvent, payload);
      if (currentEvent === "pipeline_complete") {
        didComplete = true;
      }
      if (currentEvent === "error") {
        hasServerError = true;
        const message = typeof payload?.error === "string" ? payload.error : "Pipeline execution failed.";
        onError?.(new Error(message));
      }

      currentEvent = "message";
      currentDataLines = [];
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const rawLine of lines) {
        const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
        if (line === "") {
          dispatchEvent();
          continue;
        }
        if (line.startsWith(":")) continue;
        if (line.startsWith("event:")) {
          currentEvent = line.slice(6).trim();
          continue;
        }
        if (line.startsWith("data:")) {
          currentDataLines.push(line.slice(5).trimStart());
          continue;
        }
      }
    }
    dispatchEvent();

    if (didComplete) {
      onComplete?.();
    } else if (!hasServerError) {
      onError?.(new Error("Pipeline stream disconnected before completion."));
    }
  }).catch(onError);
}

// ── Slides & Export ──

export async function getSlides(projectId: string) {
  const res = await fetch(`${API}/api/pipeline/${projectId}/slides`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`Get slides failed: ${res.status}`);
  return res.json();
}

export async function getDiscussionTranscript(projectId: string) {
  const res = await fetch(`${API}/api/pipeline/${projectId}/discussion-transcript`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Get transcript failed: ${res.status}`);
  return res.text();
}

export async function getDiscussionMinutes(projectId: string) {
  const res = await fetch(`${API}/api/pipeline/${projectId}/discussion-minutes`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Get minutes failed: ${res.status}`);
  return res.text();
}

export function getPptxUrl(projectId: string) {
  return `${API}/api/pipeline/${projectId}/export/pptx`;
}

export function getMeetingPptxUrl(projectId: string) {
  return `${API}/api/pipeline/${projectId}/export/meeting-pptx`;
}

// ── Directors ──

export async function listDirectors() {
  const res = await fetch(`${API}/api/directors`);
  if (!res.ok) throw new Error(`List directors failed: ${res.status}`);
  return res.json();
}

// ── Admin ──

export async function syncData() {
  const res = await fetch(`${API}/admin/sync`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Sync failed: ${res.status}`);
  return res.json();
}

export async function runFullPipeline() {
  const res = await fetch(`${API}/admin/pipeline/full`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Full pipeline failed: ${res.status}`);
  return res.json();
}

export async function uploadDataset(dataset: string, file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API}/admin/sync/upload?dataset=${dataset}`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
}

export async function buildGraph(clear = false) {
  const res = await fetch(`${API}/admin/graph/build?clear=${clear}`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Graph build failed: ${res.status}`);
  return res.json();
}

export async function getGraphStats() {
  const res = await fetch(`${API}/admin/graph/stats`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`Graph stats failed: ${res.status}`);
  return res.json();
}

export async function runEmbeddings(force = false) {
  const res = await fetch(`${API}/admin/embeddings/run?force=${force}`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Embeddings failed: ${res.status}`);
  return res.json();
}

export async function getEmbeddingStatus() {
  const res = await fetch(`${API}/admin/embeddings/status`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`Embedding status failed: ${res.status}`);
  return res.json();
}

export async function getSystemHealth() {
  const res = await fetch(`${API}/admin/health`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return res.json();
}

export async function listMethods(category?: string) {
  const params = category ? `?category=${encodeURIComponent(category)}` : "";
  const res = await fetch(`${API}/admin/methods${params}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`List methods failed: ${res.status}`);
  return res.json();
}

export async function getMethodCategories() {
  const res = await fetch(`${API}/admin/methods/categories`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`Categories failed: ${res.status}`);
  return res.json();
}

export async function updateMethod(id: number, data: Record<string, unknown>) {
  const res = await fetch(`${API}/admin/methods/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Update method failed: ${res.status}`);
  return res.json();
}

export async function listCases(industry?: string) {
  const params = industry ? `?industry=${encodeURIComponent(industry)}` : "";
  const res = await fetch(`${API}/admin/cases${params}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`List cases failed: ${res.status}`);
  return res.json();
}

export async function getCaseDetail(caseId: string) {
  const res = await fetch(`${API}/admin/cases/${caseId}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`Case detail failed: ${res.status}`);
  return res.json();
}

export async function adminListDirectors() {
  const res = await fetch(`${API}/admin/directors`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`List directors failed: ${res.status}`);
  return res.json();
}

export async function getGraphMethodSubgraph(methodName: string) {
  const res = await fetch(`${API}/admin/graph/method/${encodeURIComponent(methodName)}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`Method subgraph failed: ${res.status}`);
  return res.json();
}
