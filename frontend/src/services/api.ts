/**
 * API client. Authentication uses an httpOnly session cookie set by the backend,
 * so no token is ever stored in JavaScript. All requests go to /api (proxied to
 * FastAPI in development; same-origin rewrite in production).
 */
const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") || "";

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function parseError(res: Response): Promise<ApiError> {
  let message = `Request failed (${res.status})`;
  let code = "error";
  try {
    const data = await res.json();
    if (data?.error) {
      message = data.error.message || message;
      code = data.error.code || code;
    } else if (data?.detail) {
      message = typeof data.detail === "string" ? data.detail : message;
    }
  } catch {
    /* not JSON */
  }
  if (res.status === 502 || res.status === 503 || res.status === 504) {
    if (code === "error") message = "The server is unreachable. Is the backend running?";
  }
  return new ApiError(res.status, code, message);
}

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...rest } = init;
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      credentials: "include",
      ...rest,
      headers: { ...(json !== undefined ? { "Content-Type": "application/json" } : {}), ...(headers || {}) },
      body: json !== undefined ? JSON.stringify(json) : rest.body,
    });
  } catch {
    throw new ApiError(0, "network", "Can't reach the server. Check your connection and that the backend is running.");
  }
  if (!res.ok) {
    const err = await parseError(res);
    if (res.status === 401 && !path.startsWith("/api/auth/")) onUnauthorized?.();
    throw err;
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const get = <T,>(path: string) => api<T>(path);
export const post = <T,>(path: string, json?: unknown) => api<T>(path, { method: "POST", json: json ?? {} });
export const patch = <T,>(path: string, json: unknown) => api<T>(path, { method: "PATCH", json });
export const del = <T,>(path: string, json?: unknown) => api<T>(path, { method: "DELETE", json });

export function mediaUrl(lectureId: string) {
  return `${BASE}/api/lectures/${lectureId}/media`;
}

export function exportUrl(lectureId: string, kind: string, format?: string) {
  return `${BASE}/api/lectures/${lectureId}/export/${kind}${format ? `?format=${format}` : ""}`;
}

/** Download through fetch so errors surface as toasts instead of a blank tab. */
export async function download(url: string, fallbackName: string) {
  const res = await fetch(url, { credentials: "include" });
  if (!res.ok) throw await parseError(res);
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition") || "";
  const match = /filename="?([^";]+)"?/.exec(cd);
  const name = match?.[1] || fallbackName;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  return name;
}

/** Multipart upload with progress (fetch has no upload progress events). */
export function uploadWithProgress<T>(path: string, form: FormData, onProgress: (pct: number) => void,
                                      signal?: AbortSignal): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${BASE}${path}`);
    xhr.withCredentials = true;
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      let data: any = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        /* ignore */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data as T);
      else reject(new ApiError(xhr.status, data?.error?.code || "error", data?.error?.message || `Upload failed (${xhr.status})`));
    };
    xhr.onerror = () => reject(new ApiError(0, "network", "Upload failed: network error."));
    xhr.onabort = () => reject(new ApiError(0, "aborted", "Upload cancelled."));
    signal?.addEventListener("abort", () => xhr.abort());
    xhr.send(form);
  });
}
