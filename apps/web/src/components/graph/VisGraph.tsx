"use client";

import React, { useEffect, useRef, useState, useMemo, useCallback } from "react";
import { Network } from "vis-network/standalone";
import { DataSet } from "vis-data";
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  Search,
  Filter,
  X,
  FileCode,
  Box,
  Layers,
  Code2,
  ArrowRight,
  ExternalLink,
  ChevronRight,
  Sparkles,
  Pause,
  Play,
  RotateCcw,
  Share2,
  Palette,
  SlidersHorizontal,
} from "lucide-react";
import { GraphData, GraphNode, GraphEdge } from "../../lib/types";

interface VisGraphProps {
  data: GraphData;
  onSelectNode?: (node: GraphNode | null) => void;
  selectedNodeId?: string | null;
}

// 10 curated community color schemes for dark mode
const COMMUNITY_PALETTE = [
  { name: "Indigo", bg: "#6366f1", border: "#818cf8", glow: "rgba(99, 102, 241, 0.25)" },
  { name: "Teal", bg: "#14b8a6", border: "#2dd4bf", glow: "rgba(20, 184, 166, 0.25)" },
  { name: "Amber", bg: "#f59e0b", border: "#fbbf24", glow: "rgba(245, 158, 11, 0.25)" },
  { name: "Cyan", bg: "#06b6d4", border: "#22d3ee", glow: "rgba(6, 182, 212, 0.25)" },
  { name: "Rose", bg: "#f43f5e", border: "#fb7185", glow: "rgba(244, 63, 94, 0.25)" },
  { name: "Emerald", bg: "#10b981", border: "#34d399", glow: "rgba(16, 185, 129, 0.25)" },
  { name: "Violet", bg: "#8b5cf6", border: "#a78bfa", glow: "rgba(139, 92, 246, 0.25)" },
  { name: "Orange", bg: "#f97316", border: "#fb923c", glow: "rgba(249, 115, 22, 0.25)" },
  { name: "Sky", bg: "#0ea5e9", border: "#38bdf8", glow: "rgba(14, 165, 233, 0.25)" },
  { name: "Fuchsia", bg: "#d946ef", border: "#e879f9", glow: "rgba(217, 70, 239, 0.25)" },
];

export function getCommunityName(n: GraphNode): string {
  if (n.communityLabel) return n.communityLabel;
  if ((n.props as any)?.communityLabel) return (n.props as any).communityLabel;
  const filePath = n.props?.file_path || n.props?.path || (n.type === "File" ? n.id : "");
  if (filePath) {
    const parts = filePath.split("/").filter(Boolean);
    if (parts.length > 1) {
      return parts.slice(0, Math.min(2, parts.length - 1)).join("/");
    }
    return "Root Files";
  }
  if (n.props?.module) return n.props.module;
  if (n.type) return n.type;
  return "Core System";
}

export const CANVAS_THEMES = {
  slate: {
    name: "Dark Slate",
    bgColor: "#0c0d12",
    style: {
      backgroundColor: "#0c0d12",
      backgroundImage: "radial-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px)",
      backgroundSize: "22px 22px",
    },
  },
  dots: {
    name: "Indigo Dots",
    bgColor: "#0c0d12",
    style: {
      backgroundColor: "#0c0d12",
      backgroundImage: "radial-gradient(rgba(99, 102, 241, 0.12) 1px, transparent 1px)",
      backgroundSize: "22px 22px",
    },
  },
  grid: {
    name: "Slate Grid",
    bgColor: "#0c0d12",
    style: {
      backgroundColor: "#0c0d12",
      backgroundImage:
        "linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px)",
      backgroundSize: "28px 28px",
    },
  },
  obsidian: {
    name: "Pure Slate",
    bgColor: "#0c0d12",
    style: {
      backgroundColor: "#0c0d12",
    },
  },
  light: {
    name: "Clean Light",
    bgColor: "#f8fafc",
    style: {
      backgroundColor: "#f8fafc",
      backgroundImage: "radial-gradient(rgba(15, 23, 42, 0.06) 1px, transparent 1px)",
      backgroundSize: "20px 20px",
    },
  },
};

export type CanvasThemeKey = keyof typeof CANVAS_THEMES;

export const VisGraph: React.FC<VisGraphProps> = ({
  data,
  onSelectNode,
  selectedNodeId: externalSelectedNodeId,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<any>(null);
  const nodesDataSetRef = useRef<any>(null);
  const edgesDataSetRef = useRef<any>(null);

  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState<string>("ALL");
  const [filterRel, setFilterRel] = useState<string>("ALL");
  const [isPhysicsActive, setIsPhysicsActive] = useState(true);
  const [isSearching, setIsSearching] = useState(false);
  const [canvasTheme, setCanvasTheme] = useState<CanvasThemeKey>("slate");
  const [isThemeMenuOpen, setIsThemeMenuOpen] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(true);

  // 1. Community detection & Degree calculation
  const { nodeDegrees, communities, communityMap, nodeDetailsMap } = useMemo(() => {
    const degrees = new Map<string, number>();
    const nodeMap = new Map<string, GraphNode>();
    const details = new Map<
      string,
      {
        node: GraphNode;
        defines: GraphNode[];
        definedIn: GraphNode | null;
        calls: GraphNode[];
        callers: GraphNode[];
        imports: GraphNode[];
        importedBy: GraphNode[];
      }
    >();

    // Index all nodes
    data.nodes.forEach((n) => {
      nodeMap.set(n.id, n);
      degrees.set(n.id, 0);
      details.set(n.id, {
        node: n,
        defines: [],
        definedIn: null,
        calls: [],
        callers: [],
        imports: [],
        importedBy: [],
      });
    });

    // Compute degrees & relationship links
    data.edges.forEach((e) => {
      degrees.set(e.source, (degrees.get(e.source) || 0) + 1);
      degrees.set(e.target, (degrees.get(e.target) || 0) + 1);

      const srcDetail = details.get(e.source);
      const tgtDetail = details.get(e.target);
      const srcNode = nodeMap.get(e.source);
      const tgtNode = nodeMap.get(e.target);

      if (srcDetail && tgtDetail && srcNode && tgtNode) {
        const rel = (e.relation || "").toUpperCase();
        if (rel === "CALLS") {
          srcDetail.calls.push(tgtNode);
          tgtDetail.callers.push(srcNode);
        } else if (rel === "IMPORTS" || rel === "DEPENDS_ON") {
          srcDetail.imports.push(tgtNode);
          tgtDetail.importedBy.push(srcNode);
        } else if (rel === "DEFINES" || rel === "CONTAINS") {
          srcDetail.defines.push(tgtNode);
          tgtDetail.definedIn = srcNode;
        }
      }
    });

    // Cluster into communities based on topological community or directory
    const commSet = new Set<string>();
    const cMap = new Map<string, number>();

    data.nodes.forEach((n) => {
      commSet.add(getCommunityName(n));
    });

    const uniqueComms = Array.from(commSet).sort();
    data.nodes.forEach((n) => {
      const commName = getCommunityName(n);
      const idx = uniqueComms.indexOf(commName);
      cMap.set(n.id, idx >= 0 ? idx % COMMUNITY_PALETTE.length : 0);
    });

    return {
      nodeDegrees: degrees,
      communities: uniqueComms,
      communityMap: cMap,
      nodeDetailsMap: details,
    };
  }, [data.nodes, data.edges]);

  // Graphify top stats computation
  const stats = useMemo(() => {
    const rawStats = data.stats;
    const nodeCount = data.nodes.length;
    const edgeCount = data.edges.length;
    const inferredCount =
      rawStats?.inferredCount ??
      data.nodes.filter(
        (n) => n.props?.provenance === "INFERRED" || n.type === "Inferred"
      ).length;
    const extractedCount =
      rawStats?.extractedCount ?? Math.max(0, nodeCount - inferredCount);
    const synthesizedCount = rawStats?.synthesizedCount ?? 0;
    const observedCount = rawStats?.observedCount ?? 0;

    return {
      nodes: nodeCount,
      edges: edgeCount,
      extracted: extractedCount,
      inferred: inferredCount,
      synthesized: synthesizedCount,
      observed: observedCount,
    };
  }, [data]);

  // Top 15 most connected hubs for sidebar
  const mostConnectedNodes = useMemo(() => {
    return [...data.nodes]
      .sort((a, b) => (nodeDegrees.get(b.id) || 0) - (nodeDegrees.get(a.id) || 0))
      .slice(0, 15);
  }, [data.nodes, nodeDegrees]);

  // Community member counts
  const communityCounts = useMemo(() => {
    const counts = new Map<string, number>();
    data.nodes.forEach((n) => {
      const comm = getCommunityName(n);
      counts.set(comm, (counts.get(comm) || 0) + 1);
    });
    return counts;
  }, [data.nodes]);

  // Unique node types available in this graph
  const availableTypes = useMemo(() => {
    const set = new Set<string>();
    data.nodes.forEach((n) => set.add(n.type || "Symbol"));
    return Array.from(set);
  }, [data.nodes]);

  // Build Vis Network DataSets
  useEffect(() => {
    if (!containerRef.current) return;

    // Filter nodes by type
    const visNodes = data.nodes
      .filter((n) => {
        if (filterType === "ALL") return true;
        if (filterType === "Inferred") {
          return n.props?.provenance === "INFERRED" || n.type === "Inferred";
        }
        if (filterType === "Function") {
          return (n.type || "").toLowerCase().includes("func") || n.type === "Method";
        }
        return (n.type || "Symbol").toUpperCase() === filterType.toUpperCase();
      })
      .map((node) => {
        const degree = nodeDegrees.get(node.id) || 0;
        const commIndex = communityMap.get(node.id) ?? 0;
        const palette = COMMUNITY_PALETTE[commIndex];
        const isInferred = node.props?.provenance === "INFERRED" || node.type === "Inferred";

        // Sizing based on degree
        let size = Math.max(9, Math.min(28, 8 + Math.sqrt(degree) * 2.8));
        if (node.type === "File") size = Math.max(13, size * 1.1);
        if (isInferred) size = Math.max(12, size);

        const shortLabel = node.label || node.id.split("/").pop() || node.id;
        const cleanLabel = shortLabel.length > 24 ? shortLabel.slice(0, 22) + "…" : shortLabel;

        return {
          id: node.id,
          label: cleanLabel,
          title: `${node.type}: ${node.id} (${degree} connections${isInferred ? " • Inferred" : ""})`,
          value: degree,
          size: size,
          shape: isInferred ? "diamond" : node.type === "File" ? "box" : "dot",
          color: {
            background: palette.bg,
            border: isInferred ? "#fbbf24" : palette.border,
            highlight: {
              background: "#ffffff",
              border: palette.border,
            },
            hover: {
              background: "#e4e4e7",
              border: palette.border,
            },
          },
          font: {
            color: canvasTheme === "light" ? "#0f172a" : "#f1f5f9",
            size: 11,
            face: "monospace",
            strokeWidth: 3,
            strokeColor: canvasTheme === "light" ? "#ffffff" : CANVAS_THEMES[canvasTheme].bgColor,
          },
          borderWidth: isInferred ? 2 : 1.5,
          borderWidthSelected: 3,
          shadow: {
            enabled: true,
            color: palette.glow,
            size: 8,
            x: 0,
            y: 0,
          },
        };
      });

    const activeNodeIds = new Set(visNodes.map((n) => n.id));

    // Filter edges by node visibility and edge relation filter
    const isLight = canvasTheme === "light";
    const visEdges = data.edges
      .filter((e) => {
        if (!activeNodeIds.has(e.source) || !activeNodeIds.has(e.target)) return false;
        if (filterRel === "ALL") return true;
        return (e.relation || "").toUpperCase() === filterRel.toUpperCase();
      })
      .map((edge, index) => {
        const rel = (edge.relation || "").toUpperCase();
        let color = isLight ? "rgba(100, 116, 139, 0.45)" : "rgba(148, 163, 184, 0.35)";
        let width = 1;
        let dashes: boolean | number[] = false;

        if (rel === "CALLS") {
          color = isLight ? "rgba(79, 70, 229, 0.65)" : "rgba(129, 140, 248, 0.6)";
          width = 1.3;
        } else if (rel === "IMPORTS") {
          color = isLight ? "rgba(13, 148, 136, 0.65)" : "rgba(45, 212, 191, 0.6)";
          dashes = [4, 4];
        } else if (rel === "DEFINES") {
          color = isLight ? "rgba(217, 119, 6, 0.6)" : "rgba(251, 191, 36, 0.5)";
        }

        return {
          id: `edge-${index}-${edge.source}-${edge.target}`,
          from: edge.source,
          to: edge.target,
          arrows: {
            to: { enabled: true, scaleFactor: 0.6 },
          },
          color: {
            color,
            highlight: "#ffffff",
            hover: "#a5b4fc",
          },
          width,
          dashes,
          smooth: {
            enabled: true,
            type: "continuous",
            roundness: 0.2,
          },
        };
      });

    const nodesDataSet = new DataSet(visNodes);
    const edgesDataSet = new DataSet(visEdges);

    nodesDataSetRef.current = nodesDataSet;
    edgesDataSetRef.current = edgesDataSet;

    const options = {
      nodes: {
        scaling: {
          min: 10,
          max: 36,
        },
      },
      edges: {
        selectionWidth: 2,
      },
      physics: {
        enabled: isPhysicsActive,
        solver: "forceAtlas2Based",
        forceAtlas2Based: {
          gravitationalConstant: -75,
          centralGravity: 0.009,
          springLength: 95,
          springConstant: 0.06,
          damping: 0.45,
          avoidOverlap: 0.65,
        },
        stabilization: {
          enabled: true,
          iterations: 160,
          updateInterval: 25,
          fit: true,
        },
      },
      interaction: {
        hover: true,
        tooltipDelay: 150,
        selectable: true,
        selectConnectedEdges: true,
        zoomView: true,
        dragView: true,
        keyboard: true,
      },
    };

    const network = new Network(containerRef.current, { nodes: nodesDataSet, edges: edgesDataSet }, options);
    networkRef.current = network;

    // Node selection event
    network.on("selectNode", (params: any) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0];
        const foundNode = data.nodes.find((n) => n.id === nodeId) || null;
        setSelectedNode(foundNode);
        if (onSelectNode) onSelectNode(foundNode);
      }
    });

    // Deselect event
    network.on("deselectNode", () => {
      setSelectedNode(null);
      if (onSelectNode) onSelectNode(null);
    });

    // After stabilization, stop physics if desired for calm reading
    network.once("stabilizationIterationsDone", () => {
      network.fit({ animation: { duration: 500, easingFunction: "easeInOutQuad" } });
    });

    return () => {
      network.destroy();
      networkRef.current = null;
    };
  }, [data.nodes, data.edges, filterType, filterRel, nodeDegrees, communityMap, onSelectNode]);

  // Sync physics state
  useEffect(() => {
    if (networkRef.current) {
      networkRef.current.setOptions({ physics: { enabled: isPhysicsActive } });
    }
  }, [isPhysicsActive]);

  // External selection or internal node focusing
  const focusOnNode = useCallback((nodeId: string) => {
    if (!networkRef.current) return;
    networkRef.current.selectNodes([nodeId]);
    networkRef.current.focus(nodeId, {
      scale: 1.25,
      animation: {
        duration: 500,
        easingFunction: "easeInOutQuad",
      },
    });
    const found = data.nodes.find((n) => n.id === nodeId) || null;
    setSelectedNode(found);
    if (onSelectNode) onSelectNode(found);
  }, [data.nodes, onSelectNode]);

  // Sync external selection
  useEffect(() => {
    if (externalSelectedNodeId && externalSelectedNodeId !== selectedNode?.id) {
      focusOnNode(externalSelectedNodeId);
    }
  }, [externalSelectedNodeId, focusOnNode, selectedNode?.id]);

  // Search matches
  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return [];
    const q = searchQuery.toLowerCase();
    return data.nodes
      .filter((n) => n.id.toLowerCase().includes(q) || (n.label && n.label.toLowerCase().includes(q)))
      .slice(0, 8);
  }, [data.nodes, searchQuery]);

  const selectedDetails = selectedNode ? nodeDetailsMap.get(selectedNode.id) : null;
  const selectedCommIdx = selectedNode ? (communityMap.get(selectedNode.id) ?? 0) : 0;
  const selectedPalette = COMMUNITY_PALETTE[selectedCommIdx];

  return (
    <div className="w-full h-full flex flex-col relative overflow-hidden select-none bg-[#0c0d12]">
      {/* 1. Top Controls Bar */}
      <div className="h-12 border-b border-white/[0.06] bg-[#0c0d12]/90 backdrop-blur-md px-4 flex items-center justify-between shrink-0 z-20 gap-3">
        {/* Left: Search & Filter Type */}
        <div className="flex items-center gap-2.5 flex-1 min-w-0">
          {/* Node Search Bar */}
          <div className="relative w-56 sm:w-64">
            <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 top-2.5 pointer-events-none" />
            <input
              type="text"
              placeholder="Search symbols or files..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onFocus={() => setIsSearching(true)}
              className="w-full pl-8 pr-7 py-1 bg-white/[0.03] border border-white/[0.08] rounded-md text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-white/20 font-mono transition-colors"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-2 top-2 text-zinc-500 hover:text-zinc-300"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}

            {/* Search Dropdown */}
            {isSearching && searchResults.length > 0 && (
              <div className="absolute left-0 right-0 top-full mt-1 bg-[#11131a] border border-white/[0.08] rounded-lg shadow-2xl py-1 z-50 animate-fade-in divide-y divide-white/[0.04]">
                {searchResults.map((n) => (
                  <button
                    key={n.id}
                    onClick={() => {
                      focusOnNode(n.id);
                      setIsSearching(false);
                      setSearchQuery("");
                    }}
                    className="w-full px-3 py-2 text-left hover:bg-white/[0.04] flex items-center justify-between text-xs transition-colors"
                  >
                    <div className="min-w-0 pr-2">
                      <span className="font-mono text-zinc-200 block truncate">{n.label || n.id}</span>
                      <span className="text-[10px] text-zinc-500 block font-mono truncate">
                        {n.props?.file_path || n.id}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono uppercase px-1 py-0.5 rounded bg-white/[0.04] text-zinc-400 border border-white/[0.06] shrink-0">
                      {n.type}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Node Type Filter Buttons */}
          <div className="hidden md:flex items-center gap-1 bg-white/[0.03] p-0.5 rounded-md border border-white/[0.06] text-xs">
            <button
              onClick={() => setFilterType("ALL")}
              className={`px-2.5 py-0.5 rounded font-mono text-[11px] transition-colors cursor-pointer ${
                filterType === "ALL"
                  ? "bg-white/[0.1] text-white font-semibold"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              All
            </button>
            {availableTypes.slice(0, 4).map((t) => (
              <button
                key={t}
                onClick={() => setFilterType(t)}
                className={`px-2 py-0.5 rounded font-mono text-[11px] transition-colors cursor-pointer ${
                  filterType.toUpperCase() === t.toUpperCase()
                    ? "bg-white/[0.1] text-white font-semibold"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Middle: Graphify Statistic Pill Badges */}
        <div className="hidden lg:flex items-center gap-1.5 overflow-x-auto py-1">
          <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.08] text-xs font-mono">
            <span className="font-bold text-white">{stats.nodes}</span>
            <span className="text-zinc-400 text-[10px]">Nodes</span>
          </div>
          <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.08] text-xs font-mono">
            <span className="font-bold text-white">{stats.edges}</span>
            <span className="text-zinc-400 text-[10px]">Edges</span>
          </div>
          <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-xs font-mono">
            <span className="font-bold text-emerald-400">{stats.extracted}</span>
            <span className="text-emerald-400/80 text-[10px]">Extracted</span>
          </div>
          {stats.inferred > 0 && (
            <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-xs font-mono">
              <span className="font-bold text-amber-400">{stats.inferred}</span>
              <span className="text-amber-400/80 text-[10px]">Inferred</span>
            </div>
          )}
          <div className="hidden xl:flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-white/[0.02] border border-white/[0.05] text-xs font-mono text-zinc-500">
            <span className="font-bold text-zinc-400">{stats.synthesized}</span>
            <span className="text-[10px]">Synthesized</span>
          </div>
          <div className="hidden xl:flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-white/[0.02] border border-white/[0.05] text-xs font-mono text-zinc-500">
            <span className="font-bold text-zinc-400">{stats.observed}</span>
            <span className="text-[10px]">Observed</span>
          </div>
        </div>

        {/* Right: Canvas Controls & Sidebar Toggle */}
        <div className="flex items-center gap-1.5 shrink-0">
          {/* Fit to View */}
          <button
            onClick={() => networkRef.current?.fit({ animation: { duration: 400 } })}
            className="p-1.5 rounded-md bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.06] text-zinc-400 hover:text-white text-xs transition-colors cursor-pointer"
            title="Fit to View"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>

          {/* Zoom In */}
          <button
            onClick={() => {
              if (networkRef.current) {
                const currentScale = networkRef.current.getScale();
                networkRef.current.moveTo({ scale: currentScale * 1.3, animation: { duration: 250 } });
              }
            }}
            className="p-1.5 rounded-md bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.06] text-zinc-400 hover:text-white text-xs transition-colors cursor-pointer"
            title="Zoom In"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>

          {/* Zoom Out */}
          <button
            onClick={() => {
              if (networkRef.current) {
                const currentScale = networkRef.current.getScale();
                networkRef.current.moveTo({ scale: currentScale / 1.3, animation: { duration: 250 } });
              }
            }}
            className="p-1.5 rounded-md bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.06] text-zinc-400 hover:text-white text-xs transition-colors cursor-pointer"
            title="Zoom Out"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>

          {/* Physics Play/Pause Toggle */}
          <button
            onClick={() => setIsPhysicsActive(!isPhysicsActive)}
            className={`p-1.5 rounded-md border text-xs transition-colors cursor-pointer flex items-center gap-1 ${
              isPhysicsActive
                ? "bg-white/[0.03] border-white/[0.06] text-zinc-300 hover:text-white"
                : "bg-amber-500/10 border-amber-500/30 text-amber-300"
            }`}
            title={isPhysicsActive ? "Pause Layout Physics" : "Resume Layout Physics"}
          >
            {isPhysicsActive ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
          </button>

          {/* Canvas Background Theme Selector */}
          <div className="relative">
            <button
              onClick={() => setIsThemeMenuOpen(!isThemeMenuOpen)}
              className="p-1.5 rounded-md bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.06] text-zinc-400 hover:text-white text-xs transition-colors cursor-pointer flex items-center gap-1.5"
              title="Change Canvas Background"
            >
              <Palette className="w-3.5 h-3.5 text-indigo-400" />
              <span className="hidden xl:inline text-[11px] font-mono text-zinc-300">
                {CANVAS_THEMES[canvasTheme].name}
              </span>
            </button>

            {isThemeMenuOpen && (
              <div className="absolute right-0 top-full mt-1.5 w-48 bg-[#11131a] border border-white/[0.08] rounded-lg shadow-2xl py-1 z-50 animate-fade-in text-xs">
                <div className="px-2.5 py-1 text-[10px] uppercase font-mono text-zinc-500 font-semibold tracking-wider">
                  Canvas Background
                </div>
                {(Object.keys(CANVAS_THEMES) as CanvasThemeKey[]).map((key) => {
                  const t = CANVAS_THEMES[key];
                  const isSelected = canvasTheme === key;
                  return (
                    <button
                      key={key}
                      onClick={() => {
                        setCanvasTheme(key);
                        setIsThemeMenuOpen(false);
                      }}
                      className={`w-full flex items-center justify-between px-2.5 py-1.5 hover:bg-white/[0.04] text-left transition-colors cursor-pointer ${
                        isSelected ? "text-white font-medium bg-white/[0.06]" : "text-zinc-400"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className="w-3 h-3 rounded-full border border-white/[0.1] shrink-0"
                          style={{ backgroundColor: t.bgColor }}
                        />
                        <span className="text-xs font-mono">{t.name}</span>
                      </div>
                      {isSelected && <span className="text-indigo-400 text-xs font-bold">✓</span>}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="h-4 w-px bg-white/[0.08]" />

          {/* Sidebar Toggle Button */}
          <button
            onClick={() => setIsDrawerOpen(!isDrawerOpen)}
            className={`p-1.5 rounded-md border text-xs transition-colors cursor-pointer flex items-center gap-1 ${
              isDrawerOpen
                ? "bg-white/[0.08] border-white/[0.12] text-white"
                : "bg-white/[0.03] border-white/[0.06] text-zinc-400 hover:text-white"
            }`}
            title={isDrawerOpen ? "Collapse Sidebar" : "Expand Sidebar"}
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* 2. Main Canvas Area with Overlay Inspector */}
      <div className="flex-1 relative overflow-hidden flex">
        {/* Network Canvas with architectural background */}
        <div
          ref={containerRef}
          style={CANVAS_THEMES[canvasTheme].style}
          className="flex-1 h-full w-full cursor-grab active:cursor-grabbing transition-all duration-200"
        />

        {/* 3. Docked Right Panel: Inspector or Overview Drawer */}
        {isDrawerOpen && (
          <aside className="w-80 md:w-88 border-l border-white/[0.06] bg-[#0e1017]/95 backdrop-blur-md h-full flex flex-col z-30 shadow-2xl transition-all duration-200">
            {selectedNode ? (
              /* Selected Node Inspector */
              <div className="h-full flex flex-col animate-fade-in">
                <div className="p-4 border-b border-white/[0.06] flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <button
                      onClick={() => {
                        setSelectedNode(null);
                        networkRef.current?.unselectAll();
                        if (onSelectNode) onSelectNode(null);
                      }}
                      className="text-[10px] font-mono text-zinc-400 hover:text-white flex items-center gap-1 mb-1.5 transition-colors cursor-pointer"
                    >
                      <span>← Back to Overview</span>
                    </button>
                    <div className="flex items-center gap-2">
                      <span
                        className="w-2.5 h-2.5 rounded-full shrink-0"
                        style={{ backgroundColor: selectedPalette.bg }}
                      />
                      <span className="text-xs font-mono font-bold text-white uppercase tracking-wider truncate">
                        {selectedNode.type}
                      </span>
                      {selectedNode.props?.provenance === "INFERRED" && (
                        <span className="text-[9px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 font-mono font-semibold">
                          INFERRED
                        </span>
                      )}
                    </div>
                    <h3 className="text-sm font-bold text-white font-mono truncate mt-1">
                      {selectedNode.label || selectedNode.id}
                    </h3>
                  </div>
                  <button
                    onClick={() => {
                      setSelectedNode(null);
                      networkRef.current?.unselectAll();
                      if (onSelectNode) onSelectNode(null);
                    }}
                    className="text-zinc-500 hover:text-zinc-300 p-1 rounded hover:bg-white/[0.06] transition-colors cursor-pointer"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                {/* Inspector Content */}
                <div className="flex-1 overflow-y-auto p-4 space-y-5 text-xs font-mono">
                  {/* File / Location */}
                  {(selectedNode.props?.file_path || selectedNode.props?.path) && (
                    <div className="space-y-1">
                      <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">
                        File Location
                      </span>
                      <div className="flex items-center gap-1.5 text-zinc-300 bg-[#11131a] p-2 rounded-md border border-white/[0.06] break-all text-[11px]">
                        <FileCode className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                        <span>{selectedNode.props.file_path || selectedNode.props.path}</span>
                      </div>
                    </div>
                  )}

                  {/* Source Range */}
                  {selectedNode.props?.start_line !== undefined && (
                    <div className="space-y-1">
                      <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">
                        Source Lines
                      </span>
                      <div className="text-zinc-300 bg-[#11131a] px-2.5 py-1.5 rounded border border-white/[0.06] text-[11px]">
                        Lines {selectedNode.props.start_line} – {selectedNode.props.end_line || selectedNode.props.start_line}
                      </div>
                    </div>
                  )}

                  {/* Connections Metric */}
                  <div className="grid grid-cols-2 gap-2 text-center">
                    <div className="bg-[#11131a] border border-white/[0.06] rounded p-2">
                      <span className="text-[10px] text-zinc-500 block uppercase">Degree</span>
                      <span className="text-sm font-bold text-white mt-0.5 block">
                        {nodeDegrees.get(selectedNode.id) || 0}
                      </span>
                    </div>
                    <div className="bg-[#11131a] border border-white/[0.06] rounded p-2">
                      <span className="text-[10px] text-zinc-500 block uppercase">Community</span>
                      <span className="text-[11px] font-semibold text-zinc-300 mt-1 block truncate">
                        {getCommunityName(selectedNode)}
                      </span>
                    </div>
                  </div>

                  {/* Relationships: Defines */}
                  {selectedDetails && selectedDetails.defines.length > 0 && (
                    <div className="space-y-2">
                      <span className="text-[10px] text-zinc-500 uppercase tracking-wider block font-semibold">
                        Defines ({selectedDetails.defines.length})
                      </span>
                      <div className="space-y-1 max-h-36 overflow-y-auto pr-1">
                        {selectedDetails.defines.map((child) => (
                          <button
                            key={child.id}
                            onClick={() => focusOnNode(child.id)}
                            className="w-full text-left p-1.5 rounded bg-[#11131a] hover:bg-white/[0.04] border border-white/[0.06] hover:border-white/[0.12] flex items-center justify-between text-[11px] text-zinc-300 transition-colors"
                          >
                            <span className="truncate">{child.label || child.id}</span>
                            <ChevronRight className="w-3 h-3 text-zinc-500 shrink-0" />
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Relationships: Calls */}
                  {selectedDetails && selectedDetails.calls.length > 0 && (
                    <div className="space-y-2">
                      <span className="text-[10px] text-zinc-500 uppercase tracking-wider block font-semibold text-indigo-400">
                        Calls ({selectedDetails.calls.length})
                      </span>
                      <div className="space-y-1 max-h-36 overflow-y-auto pr-1">
                        {selectedDetails.calls.map((callee) => (
                          <button
                            key={callee.id}
                            onClick={() => focusOnNode(callee.id)}
                            className="w-full text-left p-1.5 rounded bg-[#11131a] hover:bg-white/[0.04] border border-white/[0.06] hover:border-white/[0.12] flex items-center justify-between text-[11px] text-zinc-300 transition-colors"
                          >
                            <span className="truncate">{callee.label || callee.id}</span>
                            <ChevronRight className="w-3 h-3 text-zinc-500 shrink-0" />
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Relationships: Callers */}
                  {selectedDetails && selectedDetails.callers.length > 0 && (
                    <div className="space-y-2">
                      <span className="text-[10px] text-zinc-500 uppercase tracking-wider block font-semibold text-cyan-400">
                        Called By ({selectedDetails.callers.length})
                      </span>
                      <div className="space-y-1 max-h-36 overflow-y-auto pr-1">
                        {selectedDetails.callers.map((caller) => (
                          <button
                            key={caller.id}
                            onClick={() => focusOnNode(caller.id)}
                            className="w-full text-left p-1.5 rounded bg-[#11131a] hover:bg-white/[0.04] border border-white/[0.06] hover:border-white/[0.12] flex items-center justify-between text-[11px] text-zinc-300 transition-colors"
                          >
                            <span className="truncate">{caller.label || caller.id}</span>
                            <ChevronRight className="w-3 h-3 text-zinc-500 shrink-0" />
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Relationships: Imports */}
                  {selectedDetails && selectedDetails.imports.length > 0 && (
                    <div className="space-y-2">
                      <span className="text-[10px] text-zinc-500 uppercase tracking-wider block font-semibold text-teal-400">
                        Imports ({selectedDetails.imports.length})
                      </span>
                      <div className="space-y-1 max-h-36 overflow-y-auto pr-1">
                        {selectedDetails.imports.map((imp) => (
                          <button
                            key={imp.id}
                            onClick={() => focusOnNode(imp.id)}
                            className="w-full text-left p-1.5 rounded bg-[#11131a] hover:bg-white/[0.04] border border-white/[0.06] hover:border-white/[0.12] flex items-center justify-between text-[11px] text-zinc-300 transition-colors"
                          >
                            <span className="truncate">{imp.label || imp.id}</span>
                            <ChevronRight className="w-3 h-3 text-zinc-500 shrink-0" />
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              /* Graphify Overview: Filter Presets, Most Connected, and Legend */
              <div className="h-full flex flex-col divide-y divide-white/[0.06] text-xs font-mono animate-fade-in">
                {/* Filter Presets */}
                <div className="p-3.5 space-y-2">
                  <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider block">
                    Filter Presets
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    <button
                      onClick={() => setFilterType(filterType === "Function" ? "ALL" : "Function")}
                      className={`px-2 py-0.5 rounded text-[11px] border transition-colors cursor-pointer ${
                        filterType === "Function"
                          ? "bg-indigo-500/20 text-indigo-300 border-indigo-500/40"
                          : "bg-white/[0.03] text-zinc-400 border-white/[0.06] hover:text-white"
                      }`}
                    >
                      kind: function
                    </button>
                    <button
                      onClick={() => setFilterType(filterType === "File" ? "ALL" : "File")}
                      className={`px-2 py-0.5 rounded text-[11px] border transition-colors cursor-pointer ${
                        filterType === "File"
                          ? "bg-indigo-500/20 text-indigo-300 border-indigo-500/40"
                          : "bg-white/[0.03] text-zinc-400 border-white/[0.06] hover:text-white"
                      }`}
                    >
                      kind: file
                    </button>
                    <button
                      onClick={() => setFilterType(filterType === "Inferred" ? "ALL" : "Inferred")}
                      className={`px-2 py-0.5 rounded text-[11px] border transition-colors cursor-pointer ${
                        filterType === "Inferred"
                          ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
                          : "bg-white/[0.03] text-zinc-400 border-white/[0.06] hover:text-white"
                      }`}
                    >
                      prov: inferred
                    </button>
                  </div>
                </div>

                {/* Most Connected Panel */}
                <div className="p-3.5 flex-1 min-h-0 flex flex-col">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">
                      Most connected
                    </span>
                    <span className="text-[10px] text-zinc-600">Top 15</span>
                  </div>
                  <div className="flex-1 overflow-y-auto space-y-1 pr-1">
                    {mostConnectedNodes.map((n) => {
                      const deg = nodeDegrees.get(n.id) || 0;
                      const cIdx = communityMap.get(n.id) ?? 0;
                      const pal = COMMUNITY_PALETTE[cIdx];
                      const isInferred = n.props?.provenance === "INFERRED" || n.type === "Inferred";

                      return (
                        <button
                          key={n.id}
                          onClick={() => focusOnNode(n.id)}
                          className="w-full text-left px-2.5 py-1.5 rounded bg-[#11131a] hover:bg-white/[0.05] border border-white/[0.05] hover:border-white/[0.12] flex items-center justify-between text-[11px] transition-colors cursor-pointer group"
                        >
                          <div className="flex items-center gap-2 min-w-0 pr-2">
                            <span
                              className="w-2 h-2 rounded-full shrink-0"
                              style={{ backgroundColor: pal.bg }}
                            />
                            <span className="text-zinc-300 group-hover:text-white truncate font-medium">
                              {n.label || n.id}
                            </span>
                          </div>
                          <div className="flex items-center gap-1.5 shrink-0">
                            {isInferred && (
                              <span className="text-[9px] px-1 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                                inf
                              </span>
                            )}
                            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-white/[0.04] text-zinc-400 group-hover:text-zinc-200">
                              {deg}
                            </span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Legend Panel */}
                <div className="p-3.5 max-h-56 overflow-y-auto">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">
                      Legend ({communities.length})
                    </span>
                  </div>
                  <div className="space-y-1.5">
                    {communities.map((comm, idx) => {
                      const pal = COMMUNITY_PALETTE[idx % COMMUNITY_PALETTE.length];
                      const count = communityCounts.get(comm) || 0;
                      return (
                        <div
                          key={comm}
                          className="flex items-center justify-between px-2 py-1 rounded bg-white/[0.02] border border-white/[0.04] text-[11px]"
                        >
                          <div className="flex items-center gap-2 min-w-0 pr-2">
                            <span
                              className="w-2.5 h-2.5 rounded-full shrink-0"
                              style={{ backgroundColor: pal.bg }}
                            />
                            <span className="text-zinc-300 truncate">{comm}</span>
                          </div>
                          <span className="text-[10px] text-zinc-500 font-mono shrink-0 font-semibold">
                            {count}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
          </aside>
        )}
      </div>
    </div>
  );
};
