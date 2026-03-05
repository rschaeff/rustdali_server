"use client";

import { useState, useEffect } from "react";
import { apiFetch, Job } from "@/lib/api";

const STATUS_COLORS: Record<string, string> = {
  queued: "bg-gray-100 text-gray-700",
  submitted: "bg-yellow-100 text-yellow-700",
  running: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadJobs();
    const interval = setInterval(loadJobs, 10_000);
    return () => clearInterval(interval);
  }, []);

  async function loadJobs() {
    try {
      const res = await apiFetch("/jobs");
      if (res.ok) setJobs(await res.json());
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <p>Loading...</p>;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Jobs</h1>

      {jobs.length === 0 ? (
        <p className="text-gray-500">
          No jobs yet.{" "}
          <a href="/submit" className="text-blue-600 hover:underline">
            Submit one
          </a>
          .
        </p>
      ) : (
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b text-left text-sm text-gray-500">
              <th className="py-2 pr-4">Query</th>
              <th className="py-2 pr-4">Library</th>
              <th className="py-2 pr-4">Status</th>
              <th className="py-2 pr-4">Submitted</th>
              <th className="py-2"></th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id} className="border-b hover:bg-gray-50">
                <td className="py-2 pr-4 font-mono text-sm">
                  {job.query_code}
                </td>
                <td className="py-2 pr-4 text-sm">{job.library.name}</td>
                <td className="py-2 pr-4">
                  <span
                    className={`text-xs px-2 py-0.5 rounded ${STATUS_COLORS[job.status] || ""}`}
                  >
                    {job.status}
                  </span>
                </td>
                <td className="py-2 pr-4 text-sm text-gray-500">
                  {new Date(job.submitted_at).toLocaleString()}
                </td>
                <td className="py-2 text-sm">
                  <a
                    href={`/jobs/${job.id}`}
                    className="text-blue-600 hover:underline"
                  >
                    View
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
