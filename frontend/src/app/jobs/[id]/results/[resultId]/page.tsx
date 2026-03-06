"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import dynamic from "next/dynamic";
import { apiFetch, Alignment, Job, SearchResult } from "@/lib/api";

// Dynamic import to avoid SSR for Mol*
const StructureViewer = dynamic(
  () => import("@/components/StructureViewer"),
  { ssr: false, loading: () => <ViewerPlaceholder /> }
);

function ViewerPlaceholder() {
  return (
    <div className="border rounded-lg bg-gray-100 flex items-center justify-center text-gray-400 text-sm" style={{ height: 500 }}>
      Loading 3D viewer...
    </div>
  );
}

function AlignmentMap({ result }: { result: SearchResult }) {
  if (!result.alignments || result.alignments.length === 0) return null;

  // Find max residue numbers for scale
  const maxQuery = Math.max(...result.alignments.map((a) => a[0]));
  const maxHit = Math.max(...result.alignments.map((a) => a[1]));

  return (
    <div>
      <h2 className="text-lg font-semibold mb-3">Residue Alignment</h2>
      <div className="bg-white border border-gray-200 rounded-lg p-4 overflow-x-auto">
        <div className="min-w-[600px]">
          {/* Simple alignment visualization */}
          <div className="flex items-center gap-2 mb-2 text-xs text-gray-500">
            <span className="w-16 text-right">Query</span>
            <div className="flex-1 relative h-4 bg-gray-100 rounded">
              {result.blocks?.map((b, i) => {
                const left = ((b.l1 - 1) / maxQuery) * 100;
                const width = ((b.r1 - b.l1 + 1) / maxQuery) * 100;
                return (
                  <div
                    key={i}
                    className="absolute h-full bg-blue-400 rounded"
                    style={{ left: `${left}%`, width: `${Math.max(width, 0.5)}%` }}
                    title={`Block ${i + 1}: ${b.l1}-${b.r1}`}
                  />
                );
              })}
            </div>
            <span className="w-12 text-left">{maxQuery}</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <span className="w-16 text-right">Hit</span>
            <div className="flex-1 relative h-4 bg-gray-100 rounded">
              {result.blocks?.map((b, i) => {
                const left = ((b.l2 - 1) / maxHit) * 100;
                const width = ((b.r2 - b.l2 + 1) / maxHit) * 100;
                return (
                  <div
                    key={i}
                    className="absolute h-full bg-green-400 rounded"
                    style={{ left: `${left}%`, width: `${Math.max(width, 0.5)}%` }}
                    title={`Block ${i + 1}: ${b.l2}-${b.r2}`}
                  />
                );
              })}
            </div>
            <span className="w-12 text-left">{maxHit}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

const LINE_WIDTH = 60;

function SequenceAlignment({ alignment }: { alignment: Alignment }) {
  const { query_seq, match_line, hit_seq, query_resids, hit_resids } = alignment;
  const len = query_seq.length;
  const chunks: { qSeq: string; mLine: string; hSeq: string; qStart: string; qEnd: string; hStart: string; hEnd: string }[] = [];

  for (let i = 0; i < len; i += LINE_WIDTH) {
    const end = Math.min(i + LINE_WIDTH, len);
    const qSlice = query_seq.slice(i, end);
    const mSlice = match_line.slice(i, end);
    const hSlice = hit_seq.slice(i, end);

    // Find first and last non-gap residue numbers for labels
    let qStart = "", qEnd = "", hStart = "", hEnd = "";
    for (let j = i; j < end; j++) {
      if (query_resids[j] != null) { qStart = String(query_resids[j]); break; }
    }
    for (let j = end - 1; j >= i; j--) {
      if (query_resids[j] != null) { qEnd = String(query_resids[j]); break; }
    }
    for (let j = i; j < end; j++) {
      if (hit_resids[j] != null) { hStart = String(hit_resids[j]); break; }
    }
    for (let j = end - 1; j >= i; j--) {
      if (hit_resids[j] != null) { hEnd = String(hit_resids[j]); break; }
    }

    chunks.push({ qSeq: qSlice, mLine: mSlice, hSeq: hSlice, qStart, qEnd, hStart, hEnd });
  }

  return (
    <div>
      <h2 className="text-lg font-semibold mb-3">Sequence Alignment</h2>
      <div className="bg-white border border-gray-200 rounded-lg p-4 overflow-x-auto">
        <pre className="text-xs leading-5 font-mono">
          {chunks.map((c, i) => (
            <span key={i}>
              <span className="text-gray-400">{`Query ${c.qStart.padStart(5)} `}</span>
              <span className="text-blue-700">{c.qSeq}</span>
              <span className="text-gray-400">{` ${c.qEnd}`}</span>
              {"\n"}
              <span className="text-gray-400">{"             "}</span>
              <span className="text-gray-500">{c.mLine}</span>
              {"\n"}
              <span className="text-gray-400">{`Hit   ${c.hStart.padStart(5)} `}</span>
              <span className="text-green-700">{c.hSeq}</span>
              <span className="text-gray-400">{` ${c.hEnd}`}</span>
              {"\n\n"}
            </span>
          ))}
        </pre>
      </div>
    </div>
  );
}

export default function ResultDetailPage() {
  const { id, resultId } = useParams<{ id: string; resultId: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [alignment, setAlignment] = useState<Alignment | null>(null);

  useEffect(() => {
    Promise.all([
      apiFetch(`/jobs/${id}`).then((r) => r.json()),
      apiFetch(`/jobs/${id}/results/${resultId}`).then((r) => r.json()),
      apiFetch(`/jobs/${id}/results/${resultId}/alignment`).then((r) => r.ok ? r.json() : null),
    ]).then(([j, r, a]) => {
      setJob(j);
      setResult(r);
      setAlignment(a);
    });
  }, [id, resultId]);

  if (!result || !job) return <p className="text-gray-500">Loading...</p>;

  const queryChain = (job.parameters?.query_chain as string) || "A";

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="text-sm text-gray-500">
        <Link href="/jobs" className="hover:underline">
          Jobs
        </Link>
        {" / "}
        <Link href={`/jobs/${id}`} className="hover:underline">
          {job.query_code}
        </Link>
        {" / "}
        <span className="text-gray-900 font-medium">{result.hit_cd2}</span>
      </div>

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">{result.hit_cd2}</h1>
        <div className="flex items-center gap-4 mt-1 text-sm text-gray-500">
          <span>
            Z-score:{" "}
            <span className="font-medium text-gray-900">
              {result.zscore.toFixed(1)}
            </span>
          </span>
          <span>RMSD: {result.rmsd?.toFixed(1) ?? "-"}</span>
          <span>
            Lali: {result.alignments?.length ?? 0}
          </span>
          <span>Blocks: {result.nblock ?? "-"}</span>
          <span>Round: {result.round}</span>
        </div>
      </div>

      {/* 3D Structure Viewer */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Structure Superposition</h2>
        <StructureViewer
          queryUrl={`/api/jobs/${id}/structures/query`}
          hitUrl={`/api/jobs/${id}/structures/hit/${result.hit_cd2}`}
          queryChain={queryChain}
          hitCode={result.hit_cd2}
          rotation={result.rotation}
          translation={result.translation}
        />
        <p className="text-xs text-gray-400 mt-1">
          Query (blue) superimposed onto hit (green) using DALI alignment transform.
        </p>
      </div>

      {/* Alignment visualization */}
      <AlignmentMap result={result} />

      {/* Sequence alignment */}
      {alignment && <SequenceAlignment alignment={alignment} />}

      {/* Alignment blocks table */}
      {result.blocks && result.blocks.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-3">Alignment Blocks</h2>
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <table className="text-sm w-full">
              <thead>
                <tr className="border-b bg-gray-50 text-left text-xs text-gray-500 uppercase tracking-wider">
                  <th className="py-2 px-4">Block</th>
                  <th className="py-2 px-4">Query range</th>
                  <th className="py-2 px-4">Hit range</th>
                  <th className="py-2 px-4">Length</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {result.blocks.map((b, i) => (
                  <tr key={i}>
                    <td className="py-2 px-4">{i + 1}</td>
                    <td className="py-2 px-4 font-mono">
                      {b.l1}-{b.r1}
                    </td>
                    <td className="py-2 px-4 font-mono">
                      {b.l2}-{b.r2}
                    </td>
                    <td className="py-2 px-4">{b.r1 - b.l1 + 1}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
