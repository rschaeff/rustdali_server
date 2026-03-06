"use client";

import { useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";

interface StructureViewerProps {
  queryUrl: string;
  hitUrl: string;
  queryChain: string;
  hitCode: string;
  rotation: number[][] | null;
  translation: number[] | null;
}

async function fetchAsDataUrl(apiPath: string): Promise<string> {
  const resp = await apiFetch(apiPath.replace(/^\/api/, ""));
  if (!resp.ok) throw new Error(`Failed to fetch structure: ${resp.status}`);
  const blob = await resp.blob();
  return URL.createObjectURL(blob);
}

export default function StructureViewer({
  queryUrl,
  hitUrl,
  rotation,
  translation,
}: StructureViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const pluginRef = useRef<any>(null);

  useEffect(() => {
    let cancelled = false;
    const blobUrls: string[] = [];

    async function init() {
      if (!containerRef.current) return;

      try {
        // Fetch PDB data with auth headers, convert to blob URLs
        const [hitBlobUrl, queryBlobUrl] = await Promise.all([
          fetchAsDataUrl(hitUrl),
          fetchAsDataUrl(queryUrl),
        ]);
        blobUrls.push(hitBlobUrl, queryBlobUrl);

        if (cancelled) return;

        const { createPluginUI } = await import("molstar/lib/mol-plugin-ui");
        const { renderReact18 } = await import("molstar/lib/mol-plugin-ui/react18");
        const { DefaultPluginUISpec } = await import("molstar/lib/mol-plugin-ui/spec");
        const { PluginCommands } = await import("molstar/lib/mol-plugin/commands");

        if (cancelled) return;

        const plugin = await createPluginUI({
          target: containerRef.current,
          render: renderReact18,
          spec: {
            ...DefaultPluginUISpec(),
            layout: {
              initial: {
                isExpanded: false,
                showControls: false,
              },
            },
          },
        });

        if (cancelled) {
          plugin.dispose();
          return;
        }

        pluginRef.current = plugin;

        const { StateTransforms } = await import("molstar/lib/mol-plugin-state/transforms");
        const { Mat4 } = await import("molstar/lib/mol-math/linear-algebra/3d/mat4");

        // Load hit structure first (template)
        const hitData = await plugin.builders.data.download(
          { url: hitBlobUrl },
          { state: { isGhost: true } }
        );
        const hitParsed = await plugin.builders.structure.parseTrajectory(hitData, "pdb");
        await plugin.builders.structure.hierarchy.applyPreset(hitParsed, "default");

        // Load query structure
        const queryData = await plugin.builders.data.download(
          { url: queryBlobUrl },
          { state: { isGhost: true } }
        );
        const queryParsed = await plugin.builders.structure.parseTrajectory(queryData, "pdb");
        await plugin.builders.structure.hierarchy.applyPreset(queryParsed, "default");

        // Apply DALI rotation/translation to query structure
        if (rotation && translation) {
          // Build column-major 4x4 matrix from DALI's row-major 3x3 rotation + translation
          const m = Mat4.identity();
          // DALI: transformed = R @ coords + t
          // Mat4.setValue(m, row, col, val) stores column-major
          for (let i = 0; i < 3; i++) {
            for (let j = 0; j < 3; j++) {
              Mat4.setValue(m, i, j, rotation[i][j]);
            }
            Mat4.setValue(m, i, 3, translation[i]);
          }

          // Find all structure nodes from the query (second loaded structure)
          const structures = plugin.managers.structure.hierarchy.current.structures;
          if (structures.length >= 2) {
            const queryStructure = structures[1];
            const structRef = queryStructure.cell.transform.ref;
            const update = plugin.build();
            update.to(structRef).apply(
              StateTransforms.Model.TransformStructureConformation,
              { transform: { name: "matrix" as const, params: { data: m, transpose: false } } }
            );
            await update.commit();
          }
        }

        // Reset camera
        await PluginCommands.Camera.Reset(plugin, {});

        setLoading(false);
      } catch (e) {
        if (!cancelled) {
          console.error("Mol* init error:", e);
          setError(`Failed to initialize 3D viewer: ${e instanceof Error ? e.message : String(e)}`);
          setLoading(false);
        }
      }
    }

    init();

    return () => {
      cancelled = true;
      blobUrls.forEach((u) => URL.revokeObjectURL(u));
      if (pluginRef.current) {
        pluginRef.current.dispose();
        pluginRef.current = null;
      }
    };
  }, [queryUrl, hitUrl]);

  return (
    <div className="relative">
      {loading && !error && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100 rounded-lg z-10">
          <span className="text-gray-400 text-sm">Loading structures...</span>
        </div>
      )}
      {error && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-100 rounded-lg z-10 p-4">
          <span className="text-red-500 text-sm text-center">{error}</span>
          <p className="text-gray-400 text-xs mt-2">
            Try refreshing the page. The 3D viewer requires WebGL support.
          </p>
        </div>
      )}
      <div
        ref={containerRef}
        className="rounded-lg border border-gray-200 overflow-hidden"
        style={{ height: 500, position: "relative" }}
      />
    </div>
  );
}
