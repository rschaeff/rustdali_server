"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { apiFetch, SearchResult } from "@/lib/api";

export default function ResultDetailPage() {
  const { id, resultId } = useParams<{ id: string; resultId: string }>();
  const [result, setResult] = useState<SearchResult | null>(null);

  useEffect(() => {
    apiFetch(`/jobs/${id}/results/${resultId}`)
      .then((r) => r.json())
      .then(setResult);
  }, [id, resultId]);

  if (!result) return <p>Loading...</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{result.hit_cd2}</h1>
        <p className="text-sm text-gray-500">
          Z-score: {result.zscore.toFixed(1)} | RMSD:{" "}
          {result.rmsd?.toFixed(1) ?? "-"} | Blocks: {result.nblock ?? "-"} |
          Round: {result.round}
        </p>
      </div>

      {/* Structure viewer placeholder -- Phase 4 will add Mol* here */}
      <div className="border rounded bg-gray-100 h-96 flex items-center justify-center text-gray-400">
        3D structure superposition viewer (Mol* — coming soon)
      </div>

      {/* Alignment blocks */}
      {result.blocks && result.blocks.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-2">Alignment Blocks</h2>
          <table className="text-sm border-collapse">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="py-1 pr-4">Block</th>
                <th className="py-1 pr-4">Query</th>
                <th className="py-1 pr-4">Hit</th>
                <th className="py-1 pr-4">Length</th>
              </tr>
            </thead>
            <tbody>
              {result.blocks.map((b, i) => (
                <tr key={i} className="border-b">
                  <td className="py-1 pr-4">{i + 1}</td>
                  <td className="py-1 pr-4 font-mono">
                    {b.l1}-{b.r1}
                  </td>
                  <td className="py-1 pr-4 font-mono">
                    {b.l2}-{b.r2}
                  </td>
                  <td className="py-1 pr-4">{b.r1 - b.l1 + 1}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Rotation/translation */}
      {result.rotation && (
        <div>
          <h2 className="text-lg font-semibold mb-2">Transform</h2>
          <pre className="text-xs bg-gray-100 p-3 rounded overflow-x-auto">
            {JSON.stringify(
              { rotation: result.rotation, translation: result.translation },
              null,
              2
            )}
          </pre>
        </div>
      )}
    </div>
  );
}
