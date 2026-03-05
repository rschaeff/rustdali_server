"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, Library } from "@/lib/api";

export default function SubmitPage() {
  const router = useRouter();
  const [libraries, setLibraries] = useState<Library[]>([]);
  const [libraryId, setLibraryId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [chain, setChain] = useState("A");
  const [zCut, setZCut] = useState(2.0);
  const [skipWolf, setSkipWolf] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch("/libraries")
      .then((r) => r.json())
      .then((data) => {
        setLibraries(data);
        if (data.length > 0) setLibraryId(data[0].id);
      })
      .catch(() => setError("Failed to load libraries. Check your API key."));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file || !libraryId) return;

    setSubmitting(true);
    setError("");

    const form = new FormData();
    form.append("file", file);
    form.append("library_id", libraryId);
    form.append("query_chain", chain);
    form.append("z_cut", zCut.toString());
    form.append("skip_wolf", skipWolf.toString());

    try {
      const res = await apiFetch("/jobs", { method: "POST", body: form });
      if (!res.ok) {
        const detail = await res.json();
        throw new Error(detail.detail || res.statusText);
      }
      const job = await res.json();
      router.push(`/jobs/${job.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-lg">
      <h1 className="text-2xl font-bold mb-6">Submit Search</h1>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded mb-4">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">
            Structure file (PDB/CIF)
          </label>
          <input
            type="file"
            accept=".pdb,.cif,.ent,.gz"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="block w-full text-sm border rounded px-3 py-2"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Chain</label>
          <input
            type="text"
            value={chain}
            onChange={(e) => setChain(e.target.value)}
            className="border rounded px-3 py-2 w-20"
            maxLength={2}
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">
            Target library
          </label>
          <select
            value={libraryId}
            onChange={(e) => setLibraryId(e.target.value)}
            className="border rounded px-3 py-2 w-full"
          >
            {libraries.map((lib) => (
              <option key={lib.id} value={lib.id}>
                {lib.name} ({lib.entry_count} entries)
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">
            Z-score cutoff
          </label>
          <input
            type="number"
            step="0.5"
            value={zCut}
            onChange={(e) => setZCut(parseFloat(e.target.value))}
            className="border rounded px-3 py-2 w-24"
          />
        </div>

        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={skipWolf}
            onChange={(e) => setSkipWolf(e.target.checked)}
            id="skip-wolf"
          />
          <label htmlFor="skip-wolf" className="text-sm">
            Skip WOLF path (PARSI only)
          </label>
        </div>

        <button
          type="submit"
          disabled={submitting || !file}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {submitting ? "Submitting..." : "Submit"}
        </button>
      </form>
    </div>
  );
}
