"use client";

import { useEffect, useRef, useState } from "react";

interface StructureViewerProps {
  queryUrl: string;
  hitUrl: string;
  queryChain: string;
  hitCode: string;
  rotation: number[][] | null;
  translation: number[] | null;
}

export default function StructureViewer({
  queryUrl,
  hitUrl,
}: StructureViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const pluginRef = useRef<any>(null);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      if (!containerRef.current) return;

      try {
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

        // Load hit structure first (template)
        const hitData = await plugin.builders.data.download(
          { url: hitUrl },
          { state: { isGhost: true } }
        );
        const hitParsed = await plugin.builders.structure.parseTrajectory(hitData, "pdb");
        await plugin.builders.structure.hierarchy.applyPreset(hitParsed, "default");

        // Load query structure
        const queryData = await plugin.builders.data.download(
          { url: queryUrl },
          { state: { isGhost: true } }
        );
        const queryParsed = await plugin.builders.structure.parseTrajectory(queryData, "pdb");
        await plugin.builders.structure.hierarchy.applyPreset(queryParsed, "default");

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
