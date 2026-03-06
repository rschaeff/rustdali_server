"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { apiFetch, Job } from "@/lib/api";

const STATUS_COLORS: Record<string, string> = {
  queued: "bg-gray-100 text-gray-700",
  submitted: "bg-yellow-100 text-yellow-700",
  running: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

const TERMINAL = new Set(["completed", "failed"]);

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    loadJobs();
    intervalRef.current = setInterval(loadJobs, 10_000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  async function loadJobs() {
    try {
      const res = await apiFetch("/jobs");
      if (res.ok) {
        const data: Job[] = await res.json();
        setJobs(data);
        // Stop polling if all jobs are terminal
        if (data.length > 0 && data.every((j) => TERMINAL.has(j.status))) {
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
        }
      }
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <p className="text-gray-500">Loading...</p>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Jobs</h1>
        <Link
          href="/submit"
          className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
        >
          New search
        </Link>
      </div>

      {jobs.length === 0 ? (
        <p className="text-gray-500">
          No jobs yet.{" "}
          <Link href="/submit" className="text-blue-600 hover:underline">
            Submit one
          </Link>
          .
        </p>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b bg-gray-50 text-left text-xs text-gray-500 uppercase tracking-wider">
                <th className="py-3 px-4">Query</th>
                <th className="py-3 px-4">Library</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Submitted</th>
                <th className="py-3 px-4"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {jobs.map((job) => (
                <tr key={job.id} className="hover:bg-gray-50">
                  <td className="py-3 px-4 font-mono text-sm">
                    {job.query_code}
                  </td>
                  <td className="py-3 px-4 text-sm">{job.library.name}</td>
                  <td className="py-3 px-4">
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[job.status] || ""}`}
                    >
                      {job.status}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-sm text-gray-500">
                    {new Date(job.submitted_at).toLocaleString()}
                  </td>
                  <td className="py-3 px-4 text-sm">
                    <Link
                      href={`/jobs/${job.id}`}
                      className="text-blue-600 hover:underline"
                    >
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
