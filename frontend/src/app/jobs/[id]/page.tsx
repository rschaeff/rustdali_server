"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiFetch, Job, SearchResult } from "@/lib/api";

const STATUS_COLORS: Record<string, string> = {
  queued: "bg-gray-100 text-gray-700",
  submitted: "bg-yellow-100 text-yellow-700",
  running: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

const TERMINAL = new Set(["completed", "failed"]);

function alignedLength(result: SearchResult): number {
  if (!result.alignments) return 0;
  return result.alignments.length;
}

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(true);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    loadJob();
    intervalRef.current = setInterval(loadJob, 5_000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [id]);

  async function loadJob() {
    try {
      const [jobRes, resultsRes] = await Promise.all([
        apiFetch(`/jobs/${id}`),
        apiFetch(`/jobs/${id}/results`),
      ]);
      if (jobRes.ok) {
        const j: Job = await jobRes.json();
        setJob(j);
        if (TERMINAL.has(j.status) && intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      }
      if (resultsRes.ok) setResults(await resultsRes.json());
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <p className="text-gray-500">Loading...</p>;
  if (!job) return <p className="text-gray-500">Job not found.</p>;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{job.query_code}</h1>
          <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
            <span>{job.library.name}</span>
            <span
              className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[job.status] || ""}`}
            >
              {job.status}
            </span>
            {job.slurm_job_id && <span>SLURM {job.slurm_job_id}</span>}
          </div>
          {job.error_message && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm mt-3">
              {job.error_message}
            </div>
          )}
        </div>
        <div className="text-sm text-gray-500 text-right">
          <div>Submitted {new Date(job.submitted_at).toLocaleString()}</div>
          {job.completed_at && (
            <div>
              Finished {new Date(job.completed_at).toLocaleString()}
            </div>
          )}
        </div>
      </div>

      {/* Running indicator */}
      {!TERMINAL.has(job.status) && (
        <div className="bg-blue-50 border border-blue-200 text-blue-700 px-4 py-3 rounded text-sm">
          Search is {job.status}. This page refreshes automatically.
        </div>
      )}

      {/* Results table */}
      {results.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-3">
            Results ({results.length} hit{results.length !== 1 ? "s" : ""})
          </h2>
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50 text-left text-xs text-gray-500 uppercase tracking-wider">
                  <th className="py-3 px-4">Hit</th>
                  <th className="py-3 px-4">Z-score</th>
                  <th className="py-3 px-4">RMSD</th>
                  <th className="py-3 px-4">Lali</th>
                  <th className="py-3 px-4">Blocks</th>
                  <th className="py-3 px-4">Round</th>
                  <th className="py-3 px-4"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {results.map((r) => (
                  <tr key={r.id} className="hover:bg-gray-50">
                    <td className="py-3 px-4 font-mono">{r.hit_cd2}</td>
                    <td className="py-3 px-4 font-medium">
                      {r.zscore.toFixed(1)}
                    </td>
                    <td className="py-3 px-4">
                      {r.rmsd != null ? r.rmsd.toFixed(1) : "-"}
                    </td>
                    <td className="py-3 px-4">{alignedLength(r)}</td>
                    <td className="py-3 px-4">{r.nblock ?? "-"}</td>
                    <td className="py-3 px-4">{r.round}</td>
                    <td className="py-3 px-4">
                      <Link
                        href={`/jobs/${id}/results/${r.id}`}
                        className="text-blue-600 hover:underline"
                      >
                        Details
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {job.status === "completed" && results.length === 0 && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 text-center text-gray-500">
          No structural hits found above the Z-score cutoff.
        </div>
      )}
    </div>
  );
}
