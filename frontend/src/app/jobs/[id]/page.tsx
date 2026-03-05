"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { apiFetch, Job, SearchResult } from "@/lib/api";

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadJob();
    const interval = setInterval(loadJob, 5_000);
    return () => clearInterval(interval);
  }, [id]);

  async function loadJob() {
    try {
      const [jobRes, resultsRes] = await Promise.all([
        apiFetch(`/jobs/${id}`),
        apiFetch(`/jobs/${id}/results`),
      ]);
      if (jobRes.ok) {
        const j = await jobRes.json();
        setJob(j);
        // Stop polling when terminal
        if (j.status === "completed" || j.status === "failed") {
          // effect cleanup handles interval
        }
      }
      if (resultsRes.ok) setResults(await resultsRes.json());
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <p>Loading...</p>;
  if (!job) return <p>Job not found.</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Job: {job.query_code}</h1>
        <p className="text-sm text-gray-500">
          {job.library.name} | Status: {job.status}
          {job.slurm_job_id && ` | SLURM: ${job.slurm_job_id}`}
        </p>
        {job.error_message && (
          <p className="text-red-600 text-sm mt-2">{job.error_message}</p>
        )}
      </div>

      {results.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-3">
            Results ({results.length} hits)
          </h2>
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="py-2 pr-3">Hit</th>
                <th className="py-2 pr-3">Z-score</th>
                <th className="py-2 pr-3">RMSD</th>
                <th className="py-2 pr-3">Blocks</th>
                <th className="py-2 pr-3">Round</th>
                <th className="py-2"></th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr key={r.id} className="border-b hover:bg-gray-50">
                  <td className="py-2 pr-3 font-mono">{r.hit_cd2}</td>
                  <td className="py-2 pr-3">{r.zscore.toFixed(1)}</td>
                  <td className="py-2 pr-3">
                    {r.rmsd != null ? r.rmsd.toFixed(1) : "-"}
                  </td>
                  <td className="py-2 pr-3">{r.nblock ?? "-"}</td>
                  <td className="py-2 pr-3">{r.round}</td>
                  <td className="py-2">
                    <a
                      href={`/jobs/${id}/results/${r.id}`}
                      className="text-blue-600 hover:underline"
                    >
                      Details
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {job.status === "completed" && results.length === 0 && (
        <p className="text-gray-500">No structural hits found.</p>
      )}
    </div>
  );
}
