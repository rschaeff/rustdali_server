const API_BASE = "/api";

function getApiKey(): string {
  if (typeof window !== "undefined") {
    return localStorage.getItem("rustdali_api_key") || "";
  }
  return "";
}

export async function apiFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const headers = new Headers(options.headers);
  headers.set("X-API-Key", getApiKey());

  return fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });
}

export interface Library {
  id: string;
  name: string;
  lib_type: string;
  entry_count: number;
  updated_at: string;
}

export interface Job {
  id: string;
  status: string;
  query_code: string;
  query_filename: string | null;
  parameters: Record<string, unknown>;
  slurm_job_id: string | null;
  submitted_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  library: Library;
}

export interface AlignmentBlock {
  l1: number;
  r1: number;
  l2: number;
  r2: number;
}

export interface SearchResult {
  id: string;
  hit_cd2: string;
  zscore: number;
  score: number | null;
  rmsd: number | null;
  nblock: number | null;
  blocks: AlignmentBlock[] | null;
  rotation: number[][] | null;
  translation: number[] | null;
  alignments: number[][] | null;
  round: number;
}
