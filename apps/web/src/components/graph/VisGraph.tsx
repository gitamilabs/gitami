"use client";

import React, { useEffect, useRef, useState, useMemo, useCallback } from "react";
import { Network } from "vis-network/standalone";
import { DataSet } from "vis-data";
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  Search,
  X,
  FileCode,
  ChevronRight,
  Pause,
  Play,
  RotateCcw,
  SlidersHorizontal,
  Folder,
  FolderOpen,
  FolderPlus,
  FolderMinus,
  FolderTree,
  FileText,
  Network as NetworkIcon,
  Crosshair,
  Sparkles,
  Filter,
  Check,
  Eye,
  EyeOff,
  ChevronDown,
  Layers,
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
  if (n.communityLabel && n.communityLabel !== "Core System") {
    return n.communityLabel;
  }
  const fpath = n.props?.file_path || n.props?.path || (n.id.includes("/") ? n.id : "");
  if (fpath) {
    const parts = fpath.replace(/\\/g, "/").split("/").filter((p: string) => p && p !== "src");
    if (parts.length > 0) {
      const top = parts[0].replace(/[_-]/g, " ");
      return top.charAt(0).toUpperCase() + top.slice(1) + " Module";
    }
  }
  return n.type || "Symbol";
}

const CANVAS_THEMES = {
  slate: {
    name: "Deep Slate",
    bgColor: "#090a0f",
    style: {
      backgroundColor: "#090a0f",
      backgroundImage: "radial-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px)",
      backgroundSize: "24px 24px",
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

export type NodeCategory =
  | "Directory"
  | "File"
  | "Function"
  | "Class"
  | "Schema"
  | "Variable"
  | "Package"
  | "Inferred";

export type EdgeCategory = "CALLS" | "IMPORTS" | "DEPENDS_ON" | "EXTENDS" | "CONTAINS";

export const ALL_NODE_CATEGORIES: {
  id: NodeCategory;
  label: string;
  icon: string;
  color: string;
  badgeBg: string;
  desc: string;
}[] = [
  { id: "Directory", label: "Folders", icon: "📁", color: "text-amber-400", badgeBg: "bg-amber-500/10 border-amber-500/20", desc: "Directories & Repositories" },
  { id: "File", label: "Files", icon: "📄", color: "text-sky-400", badgeBg: "bg-sky-500/10 border-sky-500/20", desc: "Source files" },
  { id: "Function", label: "Functions", icon: "⚡", color: "text-emerald-400", badgeBg: "bg-emerald-500/10 border-emerald-500/20", desc: "Functions & Methods" },
  { id: "Class", label: "Classes", icon: "🔷", color: "text-indigo-400", badgeBg: "bg-indigo-500/10 border-indigo-500/20", desc: "Classes & Interfaces" },
  { id: "Schema", label: "Schemas", icon: "🗄️", color: "text-purple-400", badgeBg: "bg-purple-500/10 border-purple-500/20", desc: "Schemas, Routers, Enums & Types" },
  { id: "Variable", label: "Variables", icon: "🏷️", color: "text-teal-400", badgeBg: "bg-teal-500/10 border-teal-500/20", desc: "Constants & Variables" },
  { id: "Package", label: "Packages", icon: "📦", color: "text-slate-400", badgeBg: "bg-slate-500/10 border-slate-500/20", desc: "External npm / pip packages" },
  { id: "Inferred", label: "Inferred", icon: "✨", color: "text-amber-300", badgeBg: "bg-amber-500/10 border-amber-500/20", desc: "Auto-inferred symbols" },
];

export const ALL_EDGE_CATEGORIES: {
  id: EdgeCategory;
  label: string;
  symbol: string;
  color: string;
  badgeBg: string;
  desc: string;
}[] = [
  { id: "CALLS", label: "Function Calls", symbol: "──➔", color: "text-purple-400", badgeBg: "bg-purple-500/10 border-purple-500/20", desc: "Caller ➔ Callee" },
  { id: "IMPORTS", label: "File Imports", symbol: "- -➔", color: "text-emerald-400", badgeBg: "bg-emerald-500/10 border-emerald-500/20", desc: "Importer ➔ Target" },
  { id: "DEPENDS_ON", label: "Dependencies", symbol: "⋯➔", color: "text-sky-400", badgeBg: "bg-sky-500/10 border-sky-500/20", desc: "Package / File dependency" },
  { id: "EXTENDS", label: "Inheritance", symbol: "- -➔", color: "text-amber-300", badgeBg: "bg-amber-500/10 border-amber-500/20", desc: "Class ➔ Parent" },
  { id: "CONTAINS", label: "Hierarchy Lines", symbol: "──➔", color: "text-amber-500", badgeBg: "bg-amber-500/10 border-amber-500/20", desc: "Folder ➔ File containment" },
];

export const getNodeCategory = (node: GraphNode): NodeCategory => {
  const t = node.type || "Symbol";
  const isInferred = node.props?.provenance === "INFERRED" || t === "Inferred";
  if (isInferred) return "Inferred";
  if (t === "Directory" || t === "Repository") return "Directory";
  if (t === "File") return "File";
  if (t === "Function" || t === "Method") return "Function";
  if (t === "Class" || t === "Interface") return "Class";
  if (t === "Schema" || t === "Enum" || t === "Type" || t === "Relation" || t === "Router") return "Schema";
  if (t === "Package") return "Package";
  return "Variable";
};

export const getCanonicalEdgeCategory = (rel: string): EdgeCategory => {
  const r = rel.toUpperCase();
  if (r === "CALLS") return "CALLS";
  if (r === "IMPORTS") return "IMPORTS";
  if (r === "DEPENDS_ON" || r === "DEPENDS_ON_FILE") return "DEPENDS_ON";
  if (r === "EXTENDS" || r === "IMPLEMENTS") return "EXTENDS";
  return "CONTAINS";
};

export const VisGraph: React.FC<VisGraphProps> = ({
  data,
  onSelectNode,
  selectedNodeId: externalSelectedNodeId,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<any>(null);
  const nodesDataSetRef = useRef<any>(null);
  const edgesDataSetRef = useRef<any>(null);

  // Scope & Filter States
  const [scopeFilter, setScopeFilter] = useState<"all" | "containers" | "files" | "folders">("all");
  const [selectedNodeCategories, setSelectedNodeCategories] = useState<Set<NodeCategory>>(
    () => new Set(ALL_NODE_CATEGORIES.map((c) => c.id))
  );
  const [selectedEdgeTypes, setSelectedEdgeTypes] = useState<Set<EdgeCategory>>(
    () => new Set(ALL_EDGE_CATEGORIES.map((e) => e.id))
  );
  const [selectedCommunity, setSelectedCommunity] = useState<string | null>(null);
  const [isFilterMenuOpen, setIsFilterMenuOpen] = useState(false);
  const filterMenuRef = useRef<HTMLDivElement | null>(null);

  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState<string>("ALL");
  const [filterRel, setFilterRel] = useState<string>("ALL");
  const [isPhysicsActive, setIsPhysicsActive] = useState(true);
  const [isSearching, setIsSearching] = useState(false);
  const [canvasTheme, setCanvasTheme] = useState<CanvasThemeKey>("slate");
  const [isDrawerOpen, setIsDrawerOpen] = useState(true);
  const [highlightedChain, setHighlightedChain] = useState<Set<string> | null>(null);

  const zoomBadgeRef = useRef<HTMLButtonElement | null>(null);

  const updateZoomBadge = useCallback((scale: number) => {
    if (zoomBadgeRef.current) {
      zoomBadgeRef.current.textContent = `${Math.round(scale * 100)}%`;
    }
  }, []);

  const handleZoom = useCallback((direction: "in" | "out") => {
    if (!networkRef.current) return;
    const network = networkRef.current;
    const currentScale = network.getScale();
    const currentPosition = network.getViewPosition();
    const factor = direction === "in" ? 1.45 : 1 / 1.45;
    const targetScale = Math.min(Math.max(currentScale * factor, 0.06), 3.2);

    network.moveTo({
      position: currentPosition,
      scale: targetScale,
      animation: { duration: 180, easingFunction: "easeInOutQuad" },
    });
    updateZoomBadge(targetScale);
  }, [updateZoomBadge]);

  // Smooth, device-independent zoom listener for mouse wheel & trackpad
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const onWheel = (e: WheelEvent) => {
      const network = networkRef.current;
      if (!network) return;

      e.preventDefault();
      e.stopPropagation();

      const currentScale = network.getScale();
      const minScale = 0.06;
      const maxScale = 3.2;

      let delta = e.deltaY;
      if (e.deltaMode === 1) delta *= 30; // Line mode
      else if (e.deltaMode === 2) delta *= 400; // Page mode

      // Responsive zoom curve: trackpad gets higher multiplier for rapid pinching, notched mouse gets crisp punchy steps
      const speed = Math.abs(delta) > 50 ? 0.0035 : 0.008;
      const zoomFactor = Math.exp(-delta * speed);
      const targetScale = Math.min(Math.max(currentScale * zoomFactor, minScale), maxScale);

      if (Math.abs(targetScale - currentScale) < 0.00001) return;

      // Pointer location relative to container
      const rect = container.getBoundingClientRect();
      const pointerDOM = {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      };

      // Pointer in Canvas coordinates before zoom
      const pointerCanvas = network.DOMtoCanvas(pointerDOM);
      const offsetDOM = {
        x: pointerDOM.x - rect.width / 2,
        y: pointerDOM.y - rect.height / 2,
      };

      network.moveTo({
        position: pointerCanvas,
        offset: offsetDOM,
        scale: targetScale,
      });

      updateZoomBadge(targetScale);
    };

    container.addEventListener("wheel", onWheel, { capture: true, passive: false });
    return () => {
      container.removeEventListener("wheel", onWheel, { capture: true });
    };
  }, [updateZoomBadge]);

  // Close filter popover on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (filterMenuRef.current && !filterMenuRef.current.contains(e.target as Node)) {
        setIsFilterMenuOpen(false);
      }
    };
    if (isFilterMenuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [isFilterMenuOpen]);

  const toggleNodeCategory = useCallback((cat: NodeCategory) => {
    setSelectedNodeCategories((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) {
        if (next.size > 1) next.delete(cat);
      } else {
        next.add(cat);
      }
      return next;
    });
  }, []);

  const isolateNodeCategory = useCallback((cat: NodeCategory) => {
    setSelectedNodeCategories(new Set([cat]));
  }, []);

  const selectAllNodeCategories = useCallback(() => {
    setSelectedNodeCategories(new Set(ALL_NODE_CATEGORIES.map((c) => c.id)));
  }, []);

  const toggleEdgeType = useCallback((edgeType: EdgeCategory) => {
    setSelectedEdgeTypes((prev) => {
      const next = new Set(prev);
      if (next.has(edgeType)) {
        if (next.size > 1) next.delete(edgeType);
      } else {
        next.add(edgeType);
      }
      return next;
    });
  }, []);

  const isolateEdgeType = useCallback((edgeType: EdgeCategory) => {
    setSelectedEdgeTypes(new Set([edgeType]));
  }, []);

  const selectAllEdgeTypes = useCallback(() => {
    setSelectedEdgeTypes(new Set(ALL_EDGE_CATEGORIES.map((e) => e.id)));
  }, []);

  const resetAllFilters = useCallback(() => {
    setSelectedNodeCategories(new Set(ALL_NODE_CATEGORIES.map((c) => c.id)));
    setSelectedEdgeTypes(new Set(ALL_EDGE_CATEGORIES.map((e) => e.id)));
    setSelectedCommunity(null);
    setScopeFilter("all");
    setFilterType("ALL");
    setFilterRel("ALL");
  }, []);

  const applyPreset = useCallback(
    (preset: "all" | "callGraph" | "dependencies" | "architecture" | "pureSemantic") => {
      if (preset === "all") {
        resetAllFilters();
      } else if (preset === "callGraph") {
        setSelectedNodeCategories(new Set(["Function", "Class", "File", "Inferred"]));
        setSelectedEdgeTypes(new Set(["CALLS"]));
        setSelectedCommunity(null);
        setScopeFilter("all");
      } else if (preset === "dependencies") {
        setSelectedNodeCategories(new Set(["File", "Package", "Schema", "Class"]));
        setSelectedEdgeTypes(new Set(["IMPORTS", "DEPENDS_ON"]));
        setSelectedCommunity(null);
        setScopeFilter("files");
      } else if (preset === "architecture") {
        setSelectedNodeCategories(new Set(["Directory", "File"]));
        setSelectedEdgeTypes(new Set(["CONTAINS", "DEPENDS_ON"]));
        setSelectedCommunity(null);
        setScopeFilter("files");
      } else if (preset === "pureSemantic") {
        setSelectedNodeCategories(new Set(ALL_NODE_CATEGORIES.map((c) => c.id)));
        setSelectedEdgeTypes(new Set(["CALLS", "IMPORTS", "DEPENDS_ON", "EXTENDS"]));
        setSelectedCommunity(null);
      }
    },
    [resetAllFilters]
  );

  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (selectedNodeCategories.size < ALL_NODE_CATEGORIES.length) {
      count += ALL_NODE_CATEGORIES.length - selectedNodeCategories.size;
    }
    if (selectedEdgeTypes.size < ALL_EDGE_CATEGORIES.length) {
      count += ALL_EDGE_CATEGORIES.length - selectedEdgeTypes.size;
    }
    if (selectedCommunity !== null) count += 1;
    if (scopeFilter !== "all") count += 1;
    return count;
  }, [selectedNodeCategories, selectedEdgeTypes, selectedCommunity, scopeFilter]);

  const nodeCategoryCounts = useMemo(() => {
    const counts: Record<NodeCategory, number> = {
      Directory: 0,
      File: 0,
      Function: 0,
      Class: 0,
      Schema: 0,
      Variable: 0,
      Package: 0,
      Inferred: 0,
    };
    data.nodes.forEach((n) => {
      const cat = getNodeCategory(n);
      counts[cat] = (counts[cat] || 0) + 1;
    });
    return counts;
  }, [data.nodes]);

  const edgeCategoryCounts = useMemo(() => {
    const counts: Record<EdgeCategory, number> = {
      CALLS: 0,
      IMPORTS: 0,
      DEPENDS_ON: 0,
      EXTENDS: 0,
      CONTAINS: 0,
    };
    data.edges.forEach((e) => {
      const cat = getCanonicalEdgeCategory(e.relation || "");
      counts[cat] = (counts[cat] || 0) + 1;
    });
    return counts;
  }, [data.edges]);

  // Index all nodes by ID for fast lookup
  const nodeMap = useMemo(() => {
    const map = new Map<string, GraphNode>();
    data.nodes.forEach((n) => map.set(n.id, n));
    return map;
  }, [data.nodes]);

  // Root repository node
  const rootNode = useMemo(() => {
    return data.nodes.find((n) => n.type === "Repository" || n.isRoot) || null;
  }, [data.nodes]);
  const rootId = rootNode?.id || (data.nodes[0] ? data.nodes[0].id : "repo:root");

  // Strict hierarchical parent-child relationships
  const parentMap = useMemo(() => {
    const pMap = new Map<string, string>();

    // 1. First, populate from explicit hierarchy edges (CONTAINS, DEFINES, HAS_METHOD)
    data.edges.forEach((e) => {
      const rel = (e.relation || "").toUpperCase();
      if (rel === "CONTAINS" || rel === "DEFINES" || rel === "HAS_METHOD") {
        if (!pMap.has(e.target)) {
          pMap.set(e.target, e.source);
        }
      }
    });

    // 2. Explicit node.parentId
    data.nodes.forEach((n) => {
      if (n.id === rootId) return;
      if (pMap.has(n.id)) return;
      if (n.parentId && n.parentId !== n.id) {
        pMap.set(n.id, n.parentId);
      }
    });

    // 3. Fallback path-based and relational ancestry
    data.nodes.forEach((n) => {
      if (n.id === rootId || pMap.has(n.id)) return;
      const t = n.type || "Symbol";

      if (t === "Directory") {
        if (n.id.includes("/")) {
          pMap.set(n.id, n.id.slice(0, n.id.lastIndexOf("/")));
        } else if (rootId) {
          pMap.set(n.id, rootId);
        }
      } else if (t === "File") {
        const path = n.props?.file_path || n.path || n.id;
        if (path.includes("/")) {
          pMap.set(n.id, path.slice(0, path.lastIndexOf("/")));
        } else if (rootId) {
          pMap.set(n.id, rootId);
        }
      } else if (t === "Package") {
        if (nodeMap.has("package.json")) {
          pMap.set(n.id, "package.json");
        }
      } else if (t === "Inferred") {
        const inEdge = data.edges.find((e) => e.target === n.id);
        if (inEdge && nodeMap.has(inEdge.source)) {
          pMap.set(n.id, inEdge.source);
        }
      } else {
        // AST Symbol / Class / Method / Function / Variable / Schema / Enum / Router
        const fpath = n.props?.file_path || n.path;
        if (t === "Method" && n.props?.class_name && nodeMap.has(n.props.class_name)) {
          pMap.set(n.id, n.props.class_name);
        } else if (fpath && nodeMap.has(fpath)) {
          pMap.set(n.id, fpath);
        } else if (fpath && fpath.includes("/")) {
          pMap.set(n.id, fpath);
        } else if (rootId) {
          pMap.set(n.id, rootId);
        }
      }
    });

    return pMap;
  }, [data.nodes, data.edges, rootId, nodeMap]);

  const childrenMap = useMemo(() => {
    const cMap = new Map<string, string[]>();
    parentMap.forEach((parentId, childId) => {
      const list = cMap.get(parentId) || [];
      list.push(childId);
      cMap.set(parentId, list);
    });
    return cMap;
  }, [parentMap]);

  // Helper to collect all container node IDs (Repository, Directory, File, Class, Package, or any node with children)
  const getAllContainerIds = useCallback(() => {
    const containers = new Set<string>();
    if (rootId) containers.add(rootId);
    data.nodes.forEach((n) => {
      const t = n.type || "Symbol";
      const hasChildren = (childrenMap.get(n.id)?.length || 0) > 0;
      if (
        t === "Directory" ||
        t === "Repository" ||
        t === "File" ||
        t === "Class" ||
        t === "Package" ||
        hasChildren
      ) {
        containers.add(n.id);
      }
    });
    return containers;
  }, [rootId, data.nodes, childrenMap]);

  // Expansion State: stores IDs of currently expanded containers
  // Initial state: Completely open graph by default! All containers start expanded.
  const [expandedNodeIds, setExpandedNodeIds] = useState<Set<string>>(() => {
    const initial = new Set<string>();
    if (rootId) initial.add(rootId);
    data.nodes.forEach((n) => {
      const t = n.type || "Symbol";
      const hasChildren = (childrenMap.get(n.id)?.length || 0) > 0;
      if (
        t === "Directory" ||
        t === "Repository" ||
        t === "File" ||
        t === "Class" ||
        t === "Package" ||
        hasChildren
      ) {
        initial.add(n.id);
      }
    });
    return initial;
  });

  // Re-sync initial expanded state when repo/root or dataset changes
  const lastExpandedDataKeyRef = useRef<string>("");
  useEffect(() => {
    const currentKey = `${rootId}-${data.nodes.length}`;
    if (data.nodes.length > 0 && lastExpandedDataKeyRef.current !== currentKey) {
      lastExpandedDataKeyRef.current = currentKey;
      setExpandedNodeIds(getAllContainerIds());
    }
  }, [rootId, data.nodes.length, getAllContainerIds]);

  // Deterministic, non-overlapping hierarchical radial pre-layout
  // Distributes nodes across broad angular sectors by folder and file hierarchy so 200+ nodes start sparse without collision
  const initialPositionsMap = useMemo(() => {
    const positions = new Map<string, { x: number; y: number }>();
    if (!rootId || data.nodes.length === 0) return positions;

    // 1. Calculate subtree weights (number of descendant components) for angular partitioning
    const subtreeWeights = new Map<string, number>();
    const calcWeight = (id: string, visited: Set<string>): number => {
      if (visited.has(id)) return 1;
      visited.add(id);
      const children = childrenMap.get(id) || [];
      if (children.length === 0) {
        subtreeWeights.set(id, 1);
        return 1;
      }
      let sum = 0;
      for (const cid of children) {
        sum += calcWeight(cid, visited);
      }
      const w = Math.max(sum, 1);
      subtreeWeights.set(id, w);
      return w;
    };

    const visitedForWeight = new Set<string>();
    calcWeight(rootId, visitedForWeight);

    // Root node placed at origin
    positions.set(rootId, { x: 0, y: 0 });

    // 2. Recursively assign positions in non-overlapping radial sectors
    const visitedForLayout = new Set<string>([rootId]);

    const layoutSubtree = (
      parentId: string,
      parentPos: { x: number; y: number },
      startAngle: number,
      endAngle: number,
      parentDepth: number
    ) => {
      const children = childrenMap.get(parentId) || [];
      if (children.length === 0) return;

      const totalWeight = children.reduce(
        (acc, cid) => acc + Math.max(subtreeWeights.get(cid) || 1, 2),
        0
      );

      const totalAngleSpan = endAngle - startAngle;
      let currentAngle = startAngle;

      children.forEach((childId) => {
        if (visitedForLayout.has(childId)) return;
        visitedForLayout.add(childId);

        const childNode = nodeMap.get(childId);
        const childType = childNode?.type || "Symbol";
        const weight = Math.max(subtreeWeights.get(childId) || 1, 2);
        const angleShare =
          totalWeight > 0 ? (weight / totalWeight) * totalAngleSpan : totalAngleSpan / children.length;
        const childStartAngle = currentAngle;
        const childEndAngle = currentAngle + angleShare;
        const childMidAngle = childStartAngle + angleShare / 2;
        currentAngle += angleShare;

        // Radius from parent based on hierarchical tier
        let radius = 220;
        if (parentDepth === 0) {
          // Direct children of root repository
          radius = childType === "Directory" ? 780 : 420;
        } else if (childType === "Directory") {
          radius = 500;
        } else if (childType === "File") {
          radius = 320;
        } else if (childType === "Class" || childType === "Schema" || childType === "Router") {
          radius = 220;
        } else {
          // Method, Function, Variable, Enum, Type
          radius = 160;
        }

        const childPos = {
          x: Math.round(parentPos.x + Math.cos(childMidAngle) * radius),
          y: Math.round(parentPos.y + Math.sin(childMidAngle) * radius),
        };
        positions.set(childId, childPos);

        layoutSubtree(childId, childPos, childStartAngle, childEndAngle, parentDepth + 1);
      });
    };

    layoutSubtree(rootId, { x: 0, y: 0 }, 0, 2 * Math.PI, 0);

    // Fallback: any node not reached from root
    let unparentedIdx = 0;
    data.nodes.forEach((n) => {
      if (!positions.has(n.id)) {
        const angle = (unparentedIdx / 16) * 2 * Math.PI;
        const r = 1200 + Math.floor(unparentedIdx / 16) * 200;
        positions.set(n.id, {
          x: Math.round(Math.cos(angle) * r),
          y: Math.round(Math.sin(angle) * r),
        });
        unparentedIdx++;
      }
    });

    return positions;
  }, [rootId, data.nodes, childrenMap, nodeMap]);

  const toggleExpand = useCallback(
    (nodeId: string) => {
      setExpandedNodeIds((prev) => {
        const next = new Set(prev);
        if (next.has(nodeId)) {
          // Collapse: remove this node and all of its descendants
          const toRemove: string[] = [nodeId];
          let idx = 0;
          while (idx < toRemove.length) {
            const curr = toRemove[idx++];
            const children = childrenMap.get(curr) || [];
            for (const childId of children) {
              if (next.has(childId)) {
                toRemove.push(childId);
              }
            }
          }
          toRemove.forEach((id) => next.delete(id));
        } else {
          // Expand: add this node
          next.add(nodeId);
        }
        return next;
      });
    },
    [childrenMap]
  );

  const collapseAll = useCallback(() => {
    const next = new Set<string>();
    if (rootId) next.add(rootId);
    setExpandedNodeIds(next);
  }, [rootId]);

  const expandAll = useCallback(() => {
    setExpandedNodeIds(getAllContainerIds());
  }, [getAllContainerIds]);

  const isNodeVisible = useCallback(
    (nodeId: string): boolean => {
      if (!rootId || nodeId === rootId) return true;
      let currId: string | undefined = nodeId;
      const visited = new Set<string>();
      while (currId && currId !== rootId) {
        if (visited.has(currId)) return false;
        visited.add(currId);
        const parentId = parentMap.get(currId);
        if (!parentId) {
          return false;
        }
        if (!expandedNodeIds.has(parentId)) {
          return false;
        }
        currId = parentId;
      }
      return true;
    },
    [rootId, parentMap, expandedNodeIds]
  );

  // Checks scope LOD, node category filter, and community filter
  const isNodeAllowedByScope = useCallback(
    (node: GraphNode): boolean => {
      const t = node.type || "Symbol";

      // 1. Level of detail (LOD) check
      if (scopeFilter === "folders") {
        if (t !== "Directory" && t !== "Repository") return false;
      } else if (scopeFilter === "files") {
        if (t !== "Directory" && t !== "Repository" && t !== "File") return false;
      } else if (scopeFilter === "containers") {
        if (
          ![
            "Directory",
            "Repository",
            "File",
            "Class",
            "Schema",
            "Router",
            "Enum",
            "Interface",
            "Package",
          ].includes(t)
        ) {
          return false;
        }
      }

      // 2. Node category filter check
      const cat = getNodeCategory(node);
      if (!selectedNodeCategories.has(cat)) {
        return false;
      }

      // 3. Community / Code area isolation filter check
      if (selectedCommunity) {
        if (t === "Repository" || node.id === rootId) return true;
        const comm = getCommunityName(node);
        if (comm !== selectedCommunity) {
          // Keep directory ancestor if it contains nodes in selected community
          if (t === "Directory") {
            const hasDescInComm = (childrenMap.get(node.id) || []).some((cid) => {
              const cNode = nodeMap.get(cid);
              return cNode && getCommunityName(cNode) === selectedCommunity;
            });
            if (hasDescInComm) return true;
          }
          return false;
        }
      }

      return true;
    },
    [scopeFilter, selectedNodeCategories, selectedCommunity, rootId, childrenMap, nodeMap]
  );

  const isAllowedAndVisible = useCallback(
    (nodeId: string): boolean => {
      const n = nodeMap.get(nodeId);
      if (!n) return false;
      return isNodeAllowedByScope(n) && isNodeVisible(nodeId);
    },
    [nodeMap, isNodeAllowedByScope, isNodeVisible]
  );

  // Lowest visible ancestor proxy for boundary edge rollups
  const getVisibleProxy = useCallback(
    (nodeId: string): string | null => {
      if (isAllowedAndVisible(nodeId)) {
        return nodeId;
      }
      let currId: string | undefined = nodeId;
      const visited = new Set<string>();
      while (currId) {
        if (visited.has(currId)) break;
        visited.add(currId);
        const parentId = parentMap.get(currId);
        if (!parentId) break;
        if (isAllowedAndVisible(parentId)) {
          return parentId;
        }
        currId = parentId;
      }
      return null;
    },
    [isAllowedAndVisible, parentMap]
  );

  // Helper to find the most specific visible descendant of an expanded container towards a target
  const findVisibleDescendant = useCallback(
    (targetId: string, ancestorId: string): string | null => {
      if (targetId !== ancestorId && isAllowedAndVisible(targetId)) return targetId;
      let curr: string | undefined = targetId;
      const chain: string[] = [];
      const visited = new Set<string>();
      while (curr && curr !== ancestorId && !visited.has(curr)) {
        visited.add(curr);
        chain.unshift(curr);
        curr = parentMap.get(curr);
      }
      if (curr !== ancestorId) return null;
      // Look from deepest / most specific child up to immediate child of ancestor
      for (let i = chain.length - 1; i >= 0; i--) {
        if (isAllowedAndVisible(chain[i])) {
          return chain[i];
        }
      }
      return null;
    },
    [isAllowedAndVisible, parentMap]
  );

  // Compute degrees & relationships with strict deduplication
  const { nodeDegrees, communities, communityMap, nodeDetailsMap } = useMemo(() => {
    const degrees = new Map<string, number>();
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

    const seenDefines = new Map<string, Set<string>>();
    const seenCalls = new Map<string, Set<string>>();
    const seenCallers = new Map<string, Set<string>>();
    const seenImports = new Map<string, Set<string>>();
    const seenImportedBy = new Map<string, Set<string>>();

    data.nodes.forEach((n) => {
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
      seenDefines.set(n.id, new Set());
      seenCalls.set(n.id, new Set());
      seenCallers.set(n.id, new Set());
      seenImports.set(n.id, new Set());
      seenImportedBy.set(n.id, new Set());
    });

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
          if (!seenCalls.get(e.source)?.has(e.target)) {
            srcDetail.calls.push(tgtNode);
            seenCalls.get(e.source)?.add(e.target);
          }
          if (!seenCallers.get(e.target)?.has(e.source)) {
            tgtDetail.callers.push(srcNode);
            seenCallers.get(e.target)?.add(e.source);
          }
        } else if (rel === "IMPORTS" || rel === "DEPENDS_ON" || rel === "DEPENDS_ON_FILE") {
          if (!seenImports.get(e.source)?.has(e.target)) {
            srcDetail.imports.push(tgtNode);
            seenImports.get(e.source)?.add(e.target);
          }
          if (!seenImportedBy.get(e.target)?.has(e.source)) {
            tgtDetail.importedBy.push(srcNode);
            seenImportedBy.get(e.target)?.add(e.source);
          }
        } else if (rel === "DEFINES" || rel === "CONTAINS" || rel === "HAS_METHOD") {
          if (!seenDefines.get(e.source)?.has(e.target)) {
            srcDetail.defines.push(tgtNode);
            seenDefines.get(e.source)?.add(e.target);
          }
          tgtDetail.definedIn = srcNode;
        }
      }
    });

    // Communities based on label or directory
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
  }, [data.nodes, data.edges, nodeMap]);

  // Statistics
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
    const directoryCount =
      rawStats?.directoryCount ??
      data.nodes.filter((n) => n.type === "Directory").length;
    const fileCount =
      rawStats?.fileCount ??
      data.nodes.filter((n) => n.type === "File").length;
    const symbolCount =
      rawStats?.symbolCount ??
      data.nodes.filter(
        (n) =>
          !["Directory", "File", "Repository", "Package", "Inferred"].includes(
            n.type || ""
          )
      ).length;

    return {
      nodes: nodeCount,
      edges: edgeCount,
      directories: directoryCount,
      files: fileCount,
      symbols: symbolCount,
      extracted: extractedCount,
      inferred: inferredCount,
    };
  }, [data]);

  // Breadcrumb path calculation from child to root Repository
  const getBreadcrumbPath = useCallback(
    (node: GraphNode | null): GraphNode[] => {
      if (!node) return [];
      const path: GraphNode[] = [node];
      const visited = new Set<string>([node.id]);
      let currentId: string | undefined = node.id;

      while (currentId && currentId !== rootId) {
        const parentId = parentMap.get(currentId);
        if (parentId && !visited.has(parentId)) {
          visited.add(parentId);
          const parent = nodeMap.get(parentId);
          if (parent) {
            path.unshift(parent);
          }
          currentId = parentId;
        } else {
          break;
        }
      }
      return path;
    },
    [nodeMap, parentMap, rootId]
  );

  // Trace full call chain for selected node
  const traceCallChain = useCallback(
    (node: GraphNode) => {
      const chain = new Set<string>([node.id]);
      getBreadcrumbPath(node).forEach((n) => chain.add(n.id));

      const detail = nodeDetailsMap.get(node.id);
      if (detail) {
        detail.calls.forEach((c) => chain.add(c.id));
        detail.callers.forEach((c) => chain.add(c.id));
        detail.defines.forEach((d) => chain.add(d.id));
        detail.imports.forEach((i) => chain.add(i.id));
      }

      setHighlightedChain(chain);
    },
    [nodeDetailsMap, getBreadcrumbPath]
  );

  // A node is an expanded container if it is expanded and has at least one visible child on the canvas
  const isExpandedContainer = useCallback(
    (nodeId: string): boolean => {
      if (!expandedNodeIds.has(nodeId)) return false;
      const children = childrenMap.get(nodeId);
      if (!children || children.length === 0) return false;
      return children.some((cid) => isAllowedAndVisible(cid));
    },
    [expandedNodeIds, childrenMap, isAllowedAndVisible]
  );

  // Helper to find the containing File of a symbol or node
  const getContainingFile = useCallback(
    (nodeId: string): string | null => {
      let curr: string | undefined = nodeId;
      const visited = new Set<string>();
      while (curr) {
        if (visited.has(curr)) break;
        visited.add(curr);
        const n = nodeMap.get(curr);
        if (n?.type === "File") return curr;
        curr = parentMap.get(curr);
      }
      return null;
    },
    [nodeMap, parentMap]
  );

  // Helper to select the primary visible child symbol inside an expanded container
  const getPrimaryVisibleChild = useCallback(
    (containerId: string): string | null => {
      const children = childrenMap.get(containerId) || [];
      const visibleChildren = children.filter((cid) => isAllowedAndVisible(cid));
      if (visibleChildren.length === 0) return null;

      const typePriority: Record<string, number> = {
        Router: 10,
        Class: 9,
        Schema: 8,
        Function: 7,
        Method: 6,
        Interface: 5,
        Enum: 4,
        Variable: 3,
        File: 2,
        Directory: 1,
      };

      let bestChild = visibleChildren[0];
      let bestScore = -1;

      for (const cid of visibleChildren) {
        const node = nodeMap.get(cid);
        const t = node?.type || "Symbol";
        const deg = nodeDegrees.get(cid) || 0;
        const score = (typePriority[t] || 0) * 100 + deg;
        if (score > bestScore) {
          bestScore = score;
          bestChild = cid;
        }
      }

      return bestChild;
    },
    [childrenMap, isAllowedAndVisible, nodeMap, nodeDegrees]
  );

  // Top 15 most connected hubs for sidebar
  const mostConnectedNodes = useMemo(() => {
    return [...data.nodes]
      .filter((n) => n.type !== "Repository")
      .sort((a, b) => (nodeDegrees.get(b.id) || 0) - (nodeDegrees.get(a.id) || 0))
      .slice(0, 15);
  }, [data.nodes, nodeDegrees]);

  const toggleExpandRef = useRef(toggleExpand);
  toggleExpandRef.current = toggleExpand;
  const nodeMapRef = useRef(nodeMap);
  nodeMapRef.current = nodeMap;
  const childrenMapRef = useRef(childrenMap);
  childrenMapRef.current = childrenMap;
  const onSelectNodeRef = useRef(onSelectNode);
  onSelectNodeRef.current = onSelectNode;
  const prevDataRef = useRef(data);
  const isAllowedAndVisibleRef = useRef(isAllowedAndVisible);
  isAllowedAndVisibleRef.current = isAllowedAndVisible;

  const dragGroupRef = useRef<{
    parentId: string;
    offsets: { id: string; dx: number; dy: number }[];
  } | null>(null);

  // Collect all visible descendants of a node to move them collectively when parent is dragged
  const getVisibleDescendants = useCallback((parentId: string): string[] => {
    const descendants: string[] = [];
    const queue = [parentId];
    const seen = new Set<string>([parentId]);
    while (queue.length > 0) {
      const curr = queue.shift()!;
      const children = childrenMapRef.current.get(curr) || [];
      for (const childId of children) {
        if (!seen.has(childId) && isAllowedAndVisibleRef.current(childId)) {
          seen.add(childId);
          descendants.push(childId);
          queue.push(childId);
        }
      }
    }
    return descendants;
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (networkRef.current) {
        networkRef.current.destroy();
        networkRef.current = null;
      }
    };
  }, []);

  // Build Vis Network DataSets with Organic Graph Physics & Dynamic Boundary Edge Rollup
  useEffect(() => {
    if (!containerRef.current) return;

    if (prevDataRef.current !== data) {
      prevDataRef.current = data;
      if (networkRef.current) {
        networkRef.current.destroy();
        networkRef.current = null;
      }
    }

    // 1. Filter visible nodes based on active level-of-detail and hierarchy expansion
    const visNodes = data.nodes
      .filter((n) => {
        if (!isAllowedAndVisible(n.id)) return false;
        const rawLabel = n.label || n.id.split("/").pop() || n.id;
        // Filter out destructuring patterns and random internal AST variable noise
        if (
          rawLabel.startsWith("{") ||
          rawLabel.startsWith("[") ||
          rawLabel.includes(", ") ||
          n.id.includes("::{ ") ||
          n.id.includes("::[")
        ) {
          return false;
        }
        if (filterType === "ALL") return true;
        if (filterType === "Directory") {
          return n.type === "Directory" || n.type === "Repository";
        }
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
        const t = node.type || "Symbol";
        const isInferred = node.props?.provenance === "INFERRED" || t === "Inferred";
        const isExpanded = expandedNodeIds.has(node.id);
        const children = childrenMap.get(node.id) || [];
        const childCount = children.length || node.childCount || 0;
        const isHighlighted = highlightedChain ? highlightedChain.has(node.id) : true;

        let shape = "dot";
        let bgColor = palette.bg;
        let borderColor = palette.border;
        let borderWidth = 1.5;
        let size = 9;
        let labelPrefix = "";

        if (t === "Repository") {
          shape = "dot";
          bgColor = "#3b82f6";
          borderColor = "#93c5fd";
          borderWidth = 3.5;
          size = 24;
          labelPrefix = "📦 ";
        } else if (t === "Directory") {
          shape = "dot";
          if (isExpanded) {
            bgColor = "#b45309";
            borderColor = "#fef08a";
            borderWidth = 3;
            size = 20;
            labelPrefix = "📂 ";
          } else {
            bgColor = "#f59e0b";
            borderColor = "#fde047";
            borderWidth = 2.5;
            size = 18;
            labelPrefix = "📁 ";
          }
        } else if (t === "File") {
          shape = "dot";
          bgColor = "#0284c7";
          borderColor = "#38bdf8";
          borderWidth = 2;
          size = 14;
          labelPrefix = "📄 ";
        } else if (t === "Class" || t === "Schema" || t === "Router" || t === "Interface") {
          shape = "dot";
          bgColor = "#6366f1";
          borderColor = "#a5b4fc";
          borderWidth = 1.8;
          size = 12;
          labelPrefix = t === "Schema" ? "🗄️ " : t === "Router" ? "🔀 " : "🔷 ";
        } else if (isInferred) {
          shape = "diamond";
          bgColor = "#b45309";
          borderColor = "#f59e0b";
          borderWidth = 2;
          size = 11;
          labelPrefix = "✨ ";
        } else if (t === "Package") {
          shape = "dot";
          bgColor = "#475569";
          borderColor = "#cbd5e1";
          borderWidth = 1.5;
          size = 11;
          labelPrefix = "📦 ";
        } else {
          // Method / Function / Variable / Type
          shape = "dot";
          bgColor = "#10b981";
          borderColor = "#6ee7b7";
          borderWidth = 1.2;
          size = 9;
          labelPrefix = t === "Method" || t === "Function" ? "⚡ " : "";
        }

        const rawLabel = node.label || node.id.split("/").pop() || node.id;
        const cleanBaseLabel = rawLabel.length > 20 ? rawLabel.slice(0, 18) + "…" : rawLabel;
        const fullDisplayLabel =
          t === "Directory" && !isExpanded && childCount > 0
            ? `${labelPrefix}${cleanBaseLabel} (${childCount})`
            : `${labelPrefix}${cleanBaseLabel}`;

        const opacity = isHighlighted ? 1.0 : 0.15;

        const initialPos = initialPositionsMap.get(node.id);
        const isRoot = t === "Repository" || node.id === rootId;

        return {
          id: node.id,
          x: initialPos?.x,
          y: initialPos?.y,
          fixed: isRoot ? { x: true, y: true } : false,
          label: fullDisplayLabel,
          title: `${t}: ${node.id} (${degree} connections${childCount > 0 ? ` • ${childCount} items` : ""}${isInferred ? " • Inferred" : ""})`,
          size: size,
          shape: shape,
          opacity: opacity,
          color: {
            background: bgColor,
            border: borderColor,
            highlight: {
              background: "#ffffff",
              border: borderColor,
            },
            hover: {
              background: "#e4e4e7",
              border: borderColor,
            },
          },
          font: {
            color: isHighlighted ? (canvasTheme === "light" ? "#0f172a" : "#f8fafc") : "#64748b",
            size: t === "Repository" ? 14 : t === "Directory" ? 12 : t === "File" ? 10 : 9,
            face: "JetBrains Mono, ui-monospace, SFMono-Regular, monospace",
            strokeWidth: 4,
            strokeColor: canvasTheme === "light" ? "#ffffff" : CANVAS_THEMES[canvasTheme].bgColor,
            vadjust: 6,
            align: "center",
          },
          borderWidth: borderWidth,
          borderWidthSelected: 3.5,
          shadow: {
            enabled: isHighlighted && (t === "Repository" || t === "Directory" || t === "File"),
            color: t === "Directory"
              ? (isExpanded ? "rgba(180, 83, 9, 0.5)" : "rgba(245, 158, 11, 0.4)")
              : t === "File"
              ? "rgba(2, 132, 199, 0.4)"
              : t === "Repository"
              ? "rgba(59, 130, 246, 0.45)"
              : palette.glow,
            size: t === "Repository" || t === "Directory" ? 10 : 6,
            x: 0,
            y: 0,
          },
        };
      });

    // Deduplicate visNodes by ID
    const uniqueVisNodes: any[] = [];
    const seenNodeIds = new Set<string>();
    for (const node of visNodes) {
      if (!seenNodeIds.has(node.id)) {
        seenNodeIds.add(node.id);
        uniqueVisNodes.push(node);
      }
    }

    const isLight = canvasTheme === "light";

    // 2. Active containment edges (from each expanded container to each of its visible children)
    const containmentEdges: any[] = [];
    if (selectedEdgeTypes.has("CONTAINS")) {
      expandedNodeIds.forEach((expandedId) => {
        const children = childrenMap.get(expandedId) || [];
        const parentNode = nodeMap.get(expandedId);
        const parentType = parentNode?.type || "Symbol";

        children.forEach((childId) => {
          if (isAllowedAndVisible(childId) && isAllowedAndVisible(expandedId)) {
          const childNode = nodeMap.get(childId);
          const childType = childNode?.type || "Symbol";

          let edgeLength = 160;
          let edgeWidth = 1.6;
          let edgeColor = isLight ? "rgba(217, 119, 6, 0.75)" : "rgba(245, 158, 11, 0.7)";

          if (parentType === "Repository") {
            edgeLength = 320;
            edgeWidth = 2.4;
            edgeColor = isLight ? "rgba(59, 130, 246, 0.8)" : "rgba(96, 165, 250, 0.75)";
          } else if (parentType === "Directory") {
            if (childType === "Directory") {
              edgeLength = 260;
              edgeWidth = 2.0;
              edgeColor = isLight ? "rgba(217, 119, 6, 0.8)" : "rgba(245, 158, 11, 0.75)";
            } else {
              edgeLength = 200;
              edgeWidth = 1.6;
              edgeColor = isLight ? "rgba(2, 132, 199, 0.75)" : "rgba(56, 189, 248, 0.7)";
            }
          } else if (parentType === "File") {
            edgeLength = 130;
            edgeWidth = 1.2;
            edgeColor = isLight ? "rgba(99, 102, 241, 0.65)" : "rgba(165, 180, 252, 0.6)";
          } else if (parentType === "Class") {
            edgeLength = 85;
            edgeWidth = 1.0;
            edgeColor = isLight ? "rgba(16, 185, 129, 0.65)" : "rgba(110, 231, 183, 0.6)";
          }

          containmentEdges.push({
            id: `containment-${expandedId}->${childId}`,
            from: expandedId,
            to: childId,
            title: `📁 Hierarchy: ${expandedId} contains ${childNode?.label || childId}`,
            length: edgeLength,
            arrows: {
              to: { enabled: true, scaleFactor: 0.45 },
            },
            color: {
              color: edgeColor,
              highlight: "#ffffff",
              hover: "#fde047",
            },
            width: edgeWidth,
            dashes: false,
            smooth: {
              enabled: true,
              type: "continuous",
              roundness: 0.15,
            },
          });
        }
      });
    });
    }

    // 3. Consolidated Dynamic Boundary Rolled-Up Semantic Edges
    // Consolidate all parallel connections between two nodes into a single clean line
    const edgeGroups = new Map<
      string,
      {
        from: string;
        to: string;
        relations: Set<string>;
        count: number;
      }
    >();

    // Pre-scan: Identify which pairs of files/containers already have specific symbol-level edges
    // (CALLS, IMPORTS with symbol target, EXTENDS, etc.)
    const specificContainerPairs = new Set<string>();
    data.edges.forEach((e) => {
      const r = (e.relation || "").toUpperCase();
      if (r === "CONTAINS" || r === "DEPENDS_ON_FILE") return;

      const srcFile = getContainingFile(e.source);
      const tgtFile = getContainingFile(e.target);
      if (srcFile && tgtFile && srcFile !== tgtFile) {
        specificContainerPairs.add(`${srcFile}->${tgtFile}`);
      }
    });

    // Helper to resolve an endpoint down into its visible descendants if it's an expanded container
    const resolveEndpoint = (
      rawEndpoint: string,
      initialProxy: string,
      isTarget: boolean,
      otherRawEndpoint: string
    ): string | null => {
      let curr: string | null = initialProxy;
      const visited = new Set<string>();

      while (curr && isExpandedContainer(curr)) {
        if (visited.has(curr)) return null;
        visited.add(curr);

        // 1. If rawEndpoint is a descendant inside curr, find that visible descendant
        if (rawEndpoint !== curr) {
          const desc = findVisibleDescendant(rawEndpoint, curr);
          if (desc && desc !== curr) {
            curr = desc;
            continue;
          }
        }

        // 2. Coarse container-level edge:
        // If this is target and source file already has specific symbol connections to curr file:
        if (isTarget) {
          const srcFile = getContainingFile(otherRawEndpoint);
          const tgtFile = getContainingFile(curr);
          if (
            srcFile &&
            tgtFile &&
            srcFile !== tgtFile &&
            specificContainerPairs.has(`${srcFile}->${tgtFile}`)
          ) {
            return null; // Skip redundant parent connection; child relations are shown in detail
          }
        }

        // 3. Move down to the primary visible child
        const primaryChild = getPrimaryVisibleChild(curr);
        if (!primaryChild || primaryChild === curr) {
          return null;
        }
        curr = primaryChild;
      }

      // Final check: an expanded container must NEVER be an endpoint of a semantic edge!
      if (!curr || isExpandedContainer(curr)) {
        return null;
      }

      return curr;
    };

    data.edges.forEach((rawEdge) => {
      const rel = (rawEdge.relation || "").toUpperCase();
      if (rel === "CONTAINS") return;
      const edgeCat = getCanonicalEdgeCategory(rel);
      if (!selectedEdgeTypes.has(edgeCat)) return;

      const rawSp = getVisibleProxy(rawEdge.source);
      const rawTp = getVisibleProxy(rawEdge.target);

      if (!rawSp || !rawTp) return;

      // Resolve source and target endpoints:
      // If either endpoint is an expanded container, resolve down to its visible internal things
      const sp = resolveEndpoint(rawEdge.source, rawSp, false, rawEdge.target);
      const tp = resolveEndpoint(rawEdge.target, rawTp, true, rawEdge.source);

      // Both resolved endpoints must exist, be visible, and not form self-loops
      if (!sp || !tp || sp === tp) return;

      // An expanded container must NEVER receive an inward semantic edge or originate an outward semantic edge
      if (isExpandedContainer(tp) || isExpandedContainer(sp)) return;

      const key = `${sp}-->${tp}`;
      const existing = edgeGroups.get(key);
      if (existing) {
        existing.count += 1;
        existing.relations.add(rel);
      } else {
        edgeGroups.set(key, {
          from: sp,
          to: tp,
          relations: new Set([rel]),
          count: 1,
        });
      }
    });

    const rolledUpSemanticEdges: any[] = [];
    edgeGroups.forEach((group, key) => {
      // Pick primary relation for color and styling
      let primaryRel = "DEPENDS_ON_FILE";
      if (group.relations.has("CALLS")) primaryRel = "CALLS";
      else if (group.relations.has("IMPORTS")) primaryRel = "IMPORTS";
      else if (group.relations.has("DEPENDS_ON")) primaryRel = "DEPENDS_ON";
      else if (group.relations.has("EXTENDS")) primaryRel = "EXTENDS";
      else if (group.relations.has("DEFINES")) primaryRel = "DEFINES";

      if (!selectedEdgeTypes.has(getCanonicalEdgeCategory(primaryRel))) return;

      let color = isLight ? "rgba(100, 116, 139, 0.45)" : "rgba(148, 163, 184, 0.35)";
      let width = Math.min(1.2 + group.count * 0.25, 3.2);
      let dashes: boolean | number[] = false;
      let springLength = 360;

      if (primaryRel === "CALLS") {
        color = isLight ? "rgba(147, 51, 234, 0.9)" : "rgba(168, 85, 247, 0.85)";
        springLength = 360;
        dashes = false;
      } else if (primaryRel === "IMPORTS") {
        color = isLight ? "rgba(5, 150, 105, 0.9)" : "rgba(52, 211, 153, 0.8)";
        dashes = [6, 4];
        springLength = 380;
      } else if (primaryRel === "DEPENDS_ON_FILE") {
        color = isLight ? "rgba(5, 150, 105, 0.85)" : "rgba(52, 211, 153, 0.75)";
        dashes = [6, 4];
        springLength = 380;
      } else if (primaryRel === "DEPENDS_ON") {
        color = isLight ? "rgba(2, 132, 199, 0.85)" : "rgba(56, 189, 248, 0.75)";
        dashes = [3, 3];
        springLength = 320;
      } else if (primaryRel === "EXTENDS") {
        color = isLight ? "rgba(217, 119, 6, 0.85)" : "rgba(251, 191, 36, 0.8)";
        dashes = [4, 4];
        springLength = 340;
      }

      const isHighlighted = highlightedChain
        ? highlightedChain.has(group.from) && highlightedChain.has(group.to)
        : true;

      const fromNode = nodeMap.get(group.from);
      const toNode = nodeMap.get(group.to);
      const fromLabel = fromNode?.label || group.from.split("/").pop() || group.from;
      const toLabel = toNode?.label || group.to.split("/").pop() || group.to;

      let title = "";
      if (primaryRel === "CALLS") {
        title = group.count > 1
          ? `⚡ ${group.count} calls: ${fromLabel} → ${toLabel}`
          : `⚡ Call: ${fromLabel} calls ${toLabel}`;
      } else if (primaryRel === "IMPORTS" || primaryRel === "DEPENDS_ON_FILE") {
        title = group.count > 1
          ? `📦 ${group.count} dependencies: ${fromLabel} → ${toLabel}`
          : `📦 Import: ${fromLabel} imports ${toLabel}`;
      } else if (primaryRel === "EXTENDS") {
        title = `🔷 Inheritance: ${fromLabel} extends ${toLabel}`;
      } else {
        const relSummary = Array.from(group.relations).join(", ");
        title = `${relSummary}: ${fromLabel} → ${toLabel}`;
      }

      // Check if reciprocal edge exists to curve them separately
      const reciprocalKey = `${group.to}-->${group.from}`;
      const hasReciprocal = edgeGroups.has(reciprocalKey);

      rolledUpSemanticEdges.push({
        id: `semantic-${key}`,
        from: group.from,
        to: group.to,
        title,
        length: springLength,
        arrows: {
          to: { enabled: true, scaleFactor: 0.5 },
        },
        color: {
          color: isHighlighted ? color : "rgba(148, 163, 184, 0.08)",
          highlight: "#ffffff",
          hover: "#fde047",
        },
        width: isHighlighted ? width : 0.8,
        dashes,
        smooth: hasReciprocal
          ? {
              enabled: true,
              type: "curvedCW",
              roundness: 0.2,
            }
          : {
              enabled: true,
              type: "continuous",
              roundness: 0.15,
            },
      });
    });

    const uniqueVisEdges = [...containmentEdges, ...rolledUpSemanticEdges];

    const options: any = {
      nodes: {
        borderWidth: 2,
        shadow: true,
      },
      edges: {
        selectionWidth: 2,
        hoverWidth: 1.5,
      },
      physics: {
        enabled: isPhysicsActive,
        solver: "barnesHut",
        barnesHut: {
          gravitationalConstant: -26000,
          centralGravity: 0.02,
          springLength: 350,
          springConstant: 0.04,
          damping: 0.65,
          avoidOverlap: 1.0,
        },
        maxVelocity: 25,
        minVelocity: 0.75,
        stabilization: {
          enabled: true,
          iterations: 120,
          updateInterval: 25,
          fit: true,
        },
      },
      interaction: {
        hover: true,
        tooltipDelay: 120,
        selectable: true,
        selectConnectedEdges: true,
        zoomView: true,
        dragView: true,
        keyboard: true,
        zoomSpeed: 0.25,
      },
    };

    if (!networkRef.current) {
      // First initialization of Vis Network
      const nodesDataSet = new DataSet(uniqueVisNodes);
      const edgesDataSet = new DataSet(uniqueVisEdges);

      nodesDataSetRef.current = nodesDataSet;
      edgesDataSetRef.current = edgesDataSet;

      const network = new Network(containerRef.current, { nodes: nodesDataSet, edges: edgesDataSet }, options);
      networkRef.current = network;

      // Smoothly fit viewport once initial layout stabilizes, then freeze physics like Graphify / Obsidian
      network.on("stabilizationIterationsDone", () => {
        network.fit({
          animation: { duration: 500, easingFunction: "easeInOutQuad" },
        });
        network.setOptions({ physics: { enabled: false } });
        setIsPhysicsActive(false);
        setTimeout(() => {
          if (networkRef.current) {
            updateZoomBadge(networkRef.current.getScale());
          }
        }, 550);
      });

      // Synchronize zoom state and clamp zoom bounds
      network.on("zoom", (params: any) => {
        const minScale = 0.06;
        const maxScale = 3.2;
        if (params.scale < minScale) {
          network.moveTo({ scale: minScale });
          updateZoomBadge(minScale);
        } else if (params.scale > maxScale) {
          network.moveTo({ scale: maxScale });
          updateZoomBadge(maxScale);
        } else {
          updateZoomBadge(params.scale);
        }
      });

      // Dragging a parent node moves all of its child nodes with it!
      network.on("dragStart", (params: any) => {
        if (params.nodes && params.nodes.length > 0) {
          const draggedId = params.nodes[0];
          const descendants = getVisibleDescendants(draggedId);
          if (descendants.length > 0) {
            const allPositions = network.getPositions([draggedId, ...descendants]);
            const pPos = allPositions[draggedId];
            if (pPos) {
              dragGroupRef.current = {
                parentId: draggedId,
                offsets: descendants.map((cid) => ({
                  id: cid,
                  dx: (allPositions[cid]?.x ?? pPos.x) - pPos.x,
                  dy: (allPositions[cid]?.y ?? pPos.y) - pPos.y,
                })),
              };
            }
          }
        }
      });

      network.on("dragging", (params: any) => {
        if (dragGroupRef.current) {
          const { parentId, offsets } = dragGroupRef.current;
          const currentPositions = network.getPositions([parentId]);
          const curPPos = currentPositions[parentId];
          if (curPPos && nodesDataSetRef.current) {
            const childUpdates = offsets.map((item) => ({
              id: item.id,
              x: curPPos.x + item.dx,
              y: curPPos.y + item.dy,
            }));
            nodesDataSetRef.current.update(childUpdates);
          }
        }
      });

      network.on("dragEnd", (params: any) => {
        if (dragGroupRef.current) {
          const { parentId, offsets } = dragGroupRef.current;
          const currentPositions = network.getPositions([parentId]);
          const curPPos = currentPositions[parentId];
          if (curPPos && nodesDataSetRef.current) {
            const childUpdates = offsets.map((item) => ({
              id: item.id,
              x: curPPos.x + item.dx,
              y: curPPos.y + item.dy,
            }));
            nodesDataSetRef.current.update(childUpdates);
          }
          dragGroupRef.current = null;
        }
      });

      // Single-click: select node & open inspector drawer (DO NOT expand/collapse)
      network.on("click", (params: any) => {
        if (params.nodes && params.nodes.length > 0) {
          const id = params.nodes[0];
          const node = nodeMapRef.current.get(id) || null;
          setSelectedNode(node);
          setIsDrawerOpen(true);
          if (onSelectNodeRef.current) onSelectNodeRef.current(node);
        } else {
          setSelectedNode(null);
          if (onSelectNodeRef.current) onSelectNodeRef.current(null);
        }
      });

      // Double-click: toggle expand/collapse if node is container/folder, or smooth zoom in if on canvas background
      network.on("doubleClick", (params: any) => {
        if (params.nodes && params.nodes.length > 0) {
          const id = params.nodes[0];
          toggleExpandRef.current(id);
        } else if (params.pointer && params.pointer.canvas) {
          const curScale = network.getScale();
          const targetScale = Math.min(curScale * 1.4, 3.2);
          network.moveTo({
            position: params.pointer.canvas,
            scale: targetScale,
            animation: { duration: 300, easingFunction: "easeInOutQuad" },
          });
          updateZoomBadge(targetScale);
        }
      });
    } else {
      // Smooth update of existing canvas without resetting camera or view
      const existingPositions = networkRef.current.getPositions();

      // Group newly appearing child nodes by their parent so we can place them radially in a wide, non-overlapping circle
      const newNodesByParent = new Map<string, any[]>();
      uniqueVisNodes.forEach((node) => {
        if (!existingPositions[node.id]) {
          const parentId = parentMap.get(node.id);
          if (parentId && existingPositions[parentId]) {
            const list = newNodesByParent.get(parentId) || [];
            list.push(node);
            newNodesByParent.set(parentId, list);
          }
        }
      });

      const nodesWithPositions = uniqueVisNodes.map((node) => {
        if (existingPositions[node.id]) {
          return {
            ...node,
            x: existingPositions[node.id].x,
            y: existingPositions[node.id].y,
          };
        }
        const parentId = parentMap.get(node.id);
        if (parentId && existingPositions[parentId]) {
          const siblings = newNodesByParent.get(parentId) || [node];
          const idx = siblings.findIndex((s) => s.id === node.id);
          const total = siblings.length || 1;
          const pPos = existingPositions[parentId];
          // Distribute evenly along a wide circumference so labels never touch
          const angle = (idx / total) * 2 * Math.PI - Math.PI / 2;
          const radius = 240 + Math.min(total * 18, 260);
          return {
            ...node,
            x: pPos.x + Math.cos(angle) * radius,
            y: pPos.y + Math.sin(angle) * radius,
          };
        }
        const initPos = initialPositionsMap.get(node.id);
        if (initPos) {
          return {
            ...node,
            x: initPos.x,
            y: initPos.y,
          };
        }
        return node;
      });

      if (nodesDataSetRef.current && edgesDataSetRef.current) {
        nodesDataSetRef.current.clear();
        nodesDataSetRef.current.add(nodesWithPositions);

        edgesDataSetRef.current.clear();
        edgesDataSetRef.current.add(uniqueVisEdges);
      }

      if (isPhysicsActive) {
        networkRef.current.startSimulation();
      }
    }
  }, [
    data,
    expandedNodeIds,
    scopeFilter,
    selectedNodeCategories,
    selectedEdgeTypes,
    selectedCommunity,
    filterType,
    filterRel,
    isPhysicsActive,
    canvasTheme,
    highlightedChain,
    nodeDegrees,
    communityMap,
    isAllowedAndVisible,
    getVisibleProxy,
    findVisibleDescendant,
    isExpandedContainer,
    getContainingFile,
    getPrimaryVisibleChild,
    childrenMap,
    parentMap,
    initialPositionsMap,
  ]);

  // Focus on node with automatic expansion of ancestor path
  const focusOnNode = useCallback(
    (nodeId: string) => {
      // 1. Expand ancestors if hidden
      const targetNode = nodeMap.get(nodeId);
      if (targetNode) {
        const path = getBreadcrumbPath(targetNode);
        if (path.length > 1) {
          setExpandedNodeIds((prev) => {
            const next = new Set(prev);
            path.forEach((ancestor) => {
              if (ancestor.id !== nodeId) {
                next.add(ancestor.id);
              }
            });
            return next;
          });
        }
      }

      // 2. Select & center camera
      const selectAndCenter = () => {
        if (networkRef.current) {
          networkRef.current.selectNodes([nodeId]);
          const node = nodeMap.get(nodeId) || null;
          setSelectedNode(node);
          if (onSelectNode) onSelectNode(node);
          networkRef.current.focus(nodeId, {
            scale: 1.2,
            animation: { duration: 350, easingFunction: "easeInOutQuad" },
          });
        }
      };

      setTimeout(selectAndCenter, 50);
    },
    [nodeMap, onSelectNode, getBreadcrumbPath]
  );

  // Handle external selection
  useEffect(() => {
    if (externalSelectedNodeId) {
      focusOnNode(externalSelectedNodeId);
    }
  }, [externalSelectedNodeId, focusOnNode]);

  // Search filter
  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return [];
    const q = searchQuery.toLowerCase();
    return data.nodes
      .filter((n) => (n.label || "").toLowerCase().includes(q) || n.id.toLowerCase().includes(q))
      .slice(0, 10);
  }, [data.nodes, searchQuery]);

  const selectedDetails = selectedNode ? nodeDetailsMap.get(selectedNode.id) : null;
  const selectedPalette = selectedNode
    ? COMMUNITY_PALETTE[communityMap.get(selectedNode.id) ?? 0]
    : COMMUNITY_PALETTE[0];
  const breadcrumbPath = useMemo(() => getBreadcrumbPath(selectedNode), [selectedNode, getBreadcrumbPath]);

  return (
    <div className="w-full h-full flex flex-col relative select-none font-sans overflow-hidden bg-[#090a0f]">
      {/* 1. Top Controls Bar */}
      <div className="h-12 border-b border-white/[0.06] bg-[#0c0d12]/90 backdrop-blur-md px-4 flex items-center justify-between shrink-0 z-20 gap-3">
        {/* Left: Search & Scope Filter */}
        <div className="flex items-center gap-2.5 flex-1 min-w-0">
          {/* Node Search Bar */}
          <div className="relative w-52 sm:w-60">
            <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 top-2.5 pointer-events-none" />
            <input
              type="text"
              placeholder="Search symbols, files, folders..."
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
                    className="w-full px-3 py-2 text-left hover:bg-white/[0.04] flex items-center justify-between text-xs transition-colors cursor-pointer"
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

          {/* Scope / Level of Detail (LOD) Selector */}
          <div className="flex items-center gap-1 bg-white/[0.03] p-0.5 rounded-md border border-white/[0.06] text-xs">
            <span className="text-[10px] text-zinc-500 px-1 font-mono uppercase hidden sm:inline">Scope:</span>
            {(["all", "containers", "files", "folders"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setScopeFilter(s)}
                className={`px-2 py-0.5 rounded font-mono text-[10px] capitalize transition-colors cursor-pointer ${
                  scopeFilter === s
                    ? "bg-indigo-500/20 text-indigo-300 font-semibold border border-indigo-500/30"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                {s}
              </button>
            ))}
          </div>

          {/* Collapsible Hierarchy Controls */}
          <div className="flex items-center gap-1 bg-white/[0.03] p-0.5 rounded-md border border-white/[0.06] text-xs">
            <button
              onClick={collapseAll}
              className="px-2 py-0.5 rounded font-mono text-[10px] text-zinc-400 hover:text-amber-300 hover:bg-white/[0.04] transition-colors flex items-center gap-1 cursor-pointer"
              title="Collapse all folders to root view"
            >
              <FolderMinus className="w-3 h-3 text-amber-400" />
              <span className="hidden xl:inline">Collapse All</span>
            </button>
            <button
              onClick={expandAll}
              className="px-2 py-0.5 rounded font-mono text-[10px] text-zinc-400 hover:text-amber-300 hover:bg-white/[0.04] transition-colors flex items-center gap-1 cursor-pointer"
              title="Expand all folders"
            >
              <FolderPlus className="w-3 h-3 text-amber-400" />
              <span className="hidden xl:inline">Expand All</span>
            </button>
          </div>

          {/* Interactive Filters Dropdown Popover */}
          <div className="relative" ref={filterMenuRef}>
            <button
              onClick={() => setIsFilterMenuOpen((prev) => !prev)}
              className={`px-2.5 py-1 rounded-md border text-xs font-mono flex items-center gap-1.5 transition-colors cursor-pointer ${
                activeFilterCount > 0
                  ? "bg-amber-500/15 border-amber-500/40 text-amber-300 hover:bg-amber-500/25 shadow-sm shadow-amber-500/10"
                  : isFilterMenuOpen
                  ? "bg-white/[0.08] border-white/20 text-white"
                  : "bg-white/[0.03] border-white/[0.08] text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.06]"
              }`}
              title="Filter graph nodes and edge relations"
            >
              <Filter className="w-3.5 h-3.5" />
              <span>Filters</span>
              {activeFilterCount > 0 && (
                <span className="px-1.5 py-0.2 rounded-full bg-amber-400 text-black text-[10px] font-bold">
                  {activeFilterCount}
                </span>
              )}
              <ChevronDown
                className={`w-3 h-3 transition-transform ${isFilterMenuOpen ? "rotate-180" : ""}`}
              />
            </button>

            {/* Floating Filter Popover Dropdown */}
            {isFilterMenuOpen && (
              <div className="absolute left-0 top-full mt-2 w-80 sm:w-96 bg-[#0e1017] border border-white/10 rounded-xl shadow-2xl p-3.5 z-50 animate-fade-in text-xs font-mono space-y-3.5 divide-y divide-white/[0.06] max-h-[85vh] overflow-y-auto">
                {/* Header & Reset */}
                <div className="flex items-center justify-between pb-1">
                  <div className="flex items-center gap-2">
                    <SlidersHorizontal className="w-3.5 h-3.5 text-indigo-400" />
                    <span className="font-bold text-white text-xs">Graph Filters</span>
                    {activeFilterCount > 0 && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                        {activeFilterCount} active
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {activeFilterCount > 0 && (
                      <button
                        onClick={resetAllFilters}
                        className="text-[11px] text-amber-400 hover:text-amber-300 underline cursor-pointer"
                      >
                        Reset All
                      </button>
                    )}
                    <button
                      onClick={() => setIsFilterMenuOpen(false)}
                      className="p-1 rounded text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.06] cursor-pointer"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Quick Presets */}
                <div className="pt-2 space-y-1.5">
                  <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider block">
                    Presets
                  </span>
                  <div className="flex flex-wrap gap-1">
                    <button
                      onClick={() => applyPreset("all")}
                      className={`px-2 py-0.5 rounded text-[10px] border transition-colors cursor-pointer ${
                        activeFilterCount === 0
                          ? "bg-indigo-500/20 text-indigo-300 border-indigo-500/40 font-semibold"
                          : "bg-white/[0.02] text-zinc-400 border-white/[0.06] hover:text-white"
                      }`}
                    >
                      All
                    </button>
                    <button
                      onClick={() => applyPreset("callGraph")}
                      className="px-2 py-0.5 rounded text-[10px] border bg-white/[0.02] text-zinc-400 border-white/[0.06] hover:text-purple-300 hover:border-purple-500/30 transition-colors cursor-pointer"
                    >
                      ⚡ Call Graph
                    </button>
                    <button
                      onClick={() => applyPreset("dependencies")}
                      className="px-2 py-0.5 rounded text-[10px] border bg-white/[0.02] text-zinc-400 border-white/[0.06] hover:text-emerald-300 hover:border-emerald-500/30 transition-colors cursor-pointer"
                    >
                      📦 Dependencies
                    </button>
                    <button
                      onClick={() => applyPreset("architecture")}
                      className="px-2 py-0.5 rounded text-[10px] border bg-white/[0.02] text-zinc-400 border-white/[0.06] hover:text-amber-300 hover:border-amber-500/30 transition-colors cursor-pointer"
                    >
                      📁 Architecture
                    </button>
                    <button
                      onClick={() => applyPreset("pureSemantic")}
                      className="px-2 py-0.5 rounded text-[10px] border bg-white/[0.02] text-zinc-400 border-white/[0.06] hover:text-sky-300 hover:border-sky-500/30 transition-colors cursor-pointer"
                    >
                      ✨ Pure Semantic
                    </button>
                  </div>
                </div>

                {/* Node Types Section */}
                <div className="pt-2 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">
                      Node Kinds ({selectedNodeCategories.size}/{ALL_NODE_CATEGORIES.length})
                    </span>
                    <button
                      onClick={selectAllNodeCategories}
                      className="text-[10px] text-zinc-500 hover:text-zinc-300 cursor-pointer"
                    >
                      Select All
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-1.5">
                    {ALL_NODE_CATEGORIES.map((cat) => {
                      const isSelected = selectedNodeCategories.has(cat.id);
                      const count = nodeCategoryCounts[cat.id] || 0;
                      return (
                        <div
                          key={`popover-node-${cat.id}`}
                          className={`group flex items-center justify-between px-2 py-1.5 rounded-md border text-[11px] transition-colors cursor-pointer ${
                            isSelected
                              ? "bg-white/[0.05] border-white/[0.12] text-zinc-200"
                              : "bg-white/[0.01] border-white/[0.04] text-zinc-500 opacity-60"
                          }`}
                          onClick={() => toggleNodeCategory(cat.id)}
                        >
                          <div className="flex items-center gap-1.5 min-w-0 pr-1">
                            <span className="text-xs">{cat.icon}</span>
                            <span className="truncate">{cat.label}</span>
                          </div>
                          <div className="flex items-center gap-1 shrink-0">
                            <span className="text-[10px] text-zinc-500 font-mono">
                              {count}
                            </span>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                isolateNodeCategory(cat.id);
                              }}
                              className="text-[9px] uppercase px-1 py-0.2 rounded bg-white/[0.06] hover:bg-white/[0.15] text-zinc-400 hover:text-white hidden group-hover:inline-block cursor-pointer"
                              title={`Show only ${cat.label}`}
                            >
                              only
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Edge Types Section */}
                <div className="pt-2 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">
                      Edge Types ({selectedEdgeTypes.size}/{ALL_EDGE_CATEGORIES.length})
                    </span>
                    <button
                      onClick={selectAllEdgeTypes}
                      className="text-[10px] text-zinc-500 hover:text-zinc-300 cursor-pointer"
                    >
                      Select All
                    </button>
                  </div>
                  <div className="space-y-1">
                    {ALL_EDGE_CATEGORIES.map((edge) => {
                      const isSelected = selectedEdgeTypes.has(edge.id);
                      const count = edgeCategoryCounts[edge.id] || 0;
                      return (
                        <div
                          key={`popover-edge-${edge.id}`}
                          className={`group flex items-center justify-between p-1.5 rounded-md border text-[11px] transition-colors cursor-pointer ${
                            isSelected
                              ? "bg-white/[0.05] border-white/[0.12] text-zinc-200"
                              : "bg-white/[0.01] border-white/[0.04] text-zinc-500 opacity-60"
                          }`}
                          onClick={() => toggleEdgeType(edge.id)}
                        >
                          <div className="flex items-center gap-2 min-w-0 pr-2">
                            <span className={`font-mono text-xs font-bold ${edge.color}`}>
                              {edge.symbol}
                            </span>
                            <div className="min-w-0">
                              <span className="block truncate">{edge.label}</span>
                              <span className="text-[9px] text-zinc-500 block truncate font-mono">
                                {edge.desc}
                              </span>
                            </div>
                          </div>
                          <div className="flex items-center gap-1.5 shrink-0">
                            <span className="text-[10px] text-zinc-400 font-mono font-semibold">
                              {count}
                            </span>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                isolateEdgeType(edge.id);
                              }}
                              className="text-[9px] uppercase px-1 py-0.2 rounded bg-white/[0.06] hover:bg-white/[0.15] text-zinc-400 hover:text-white hidden group-hover:inline-block cursor-pointer"
                              title={`Show only ${edge.label}`}
                            >
                              only
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Active Community Filter Info */}
                {selectedCommunity && (
                  <div className="pt-2 flex items-center justify-between p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20">
                    <div className="min-w-0 pr-2">
                      <span className="text-[10px] text-indigo-400 block uppercase font-bold">
                        Isolated Code Area
                      </span>
                      <span className="text-zinc-200 truncate block font-mono text-[11px]">
                        {selectedCommunity}
                      </span>
                    </div>
                    <button
                      onClick={() => setSelectedCommunity(null)}
                      className="px-2 py-0.5 rounded bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-300 text-[10px] border border-indigo-500/30 cursor-pointer shrink-0"
                    >
                      Clear Area
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Middle: Graphify Statistic Pill Badges */}
        <div className="hidden lg:flex items-center gap-1.5 overflow-x-auto py-1">
          <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-xs font-mono">
            <Folder className="w-3 h-3 text-amber-400" />
            <span className="font-bold text-amber-400">{stats.directories}</span>
            <span className="text-amber-400/80 text-[10px]">Folders</span>
          </div>
          <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-sky-500/10 border border-sky-500/20 text-xs font-mono">
            <FileText className="w-3 h-3 text-sky-400" />
            <span className="font-bold text-sky-400">{stats.files}</span>
            <span className="text-sky-400/80 text-[10px]">Files</span>
          </div>
          <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-xs font-mono">
            <span className="font-bold text-indigo-400">{stats.symbols}</span>
            <span className="text-indigo-400/80 text-[10px]">Symbols</span>
          </div>
          <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.08] text-xs font-mono">
            <span className="font-bold text-white">{stats.edges}</span>
            <span className="text-zinc-400 text-[10px]">Edges</span>
          </div>
          {stats.inferred > 0 && (
            <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-xs font-mono">
              <span className="font-bold text-amber-400">{stats.inferred}</span>
              <span className="text-amber-400/80 text-[10px]">Inferred</span>
            </div>
          )}
        </div>

        {/* Right: Canvas Controls & Sidebar Toggle */}
        <div className="flex items-center gap-1.5 shrink-0">
          {/* Fit to View */}
          <button
            onClick={() => {
              if (networkRef.current) {
                networkRef.current.fit({ animation: { duration: 400, easingFunction: "easeInOutQuad" } });
                setTimeout(() => {
                  if (networkRef.current) updateZoomBadge(networkRef.current.getScale());
                }, 450);
              }
            }}
            className="p-1.5 rounded-md bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.06] text-zinc-400 hover:text-white text-xs transition-colors cursor-pointer"
            title="Fit to View"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>

          {/* Zoom Out */}
          <button
            onClick={() => handleZoom("out")}
            className="p-1.5 rounded-md bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.06] text-zinc-400 hover:text-white text-xs transition-colors cursor-pointer"
            title="Zoom Out"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>

          {/* Zoom Percentage (Click to reset to 100%) */}
          <button
            ref={zoomBadgeRef}
            onClick={() => {
              if (networkRef.current) {
                const currentPos = networkRef.current.getViewPosition();
                networkRef.current.moveTo({
                  position: currentPos,
                  scale: 1.0,
                  animation: { duration: 250, easingFunction: "easeInOutQuad" },
                });
                updateZoomBadge(1.0);
              }
            }}
            className="px-2 py-1 rounded-md bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.06] text-zinc-400 hover:text-white text-[11px] font-mono transition-colors cursor-pointer min-w-11 text-center"
            title="Click to Reset Zoom to 100%"
          >
            100%
          </button>

          {/* Zoom In */}
          <button
            onClick={() => handleZoom("in")}
            className="p-1.5 rounded-md bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.06] text-zinc-400 hover:text-white text-xs transition-colors cursor-pointer"
            title="Zoom In"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>

          {/* Reset Dimming / Highlight */}
          {highlightedChain && (
            <button
              onClick={() => setHighlightedChain(null)}
              className="px-2 py-1 rounded-md bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/30 text-purple-300 text-[10px] font-mono transition-colors cursor-pointer"
              title="Reset Flow Highlight"
            >
              Reset Flow
            </button>
          )}

          {/* Physics Play/Pause */}
          <button
            onClick={() => {
              const next = !isPhysicsActive;
              setIsPhysicsActive(next);
              if (networkRef.current) {
                networkRef.current.setOptions({ physics: { enabled: next } });
                if (next) networkRef.current.startSimulation();
              }
            }}
            className={`p-1.5 rounded-md border text-xs transition-colors cursor-pointer ${
              isPhysicsActive
                ? "bg-indigo-500/20 border-indigo-500/40 text-indigo-300"
                : "bg-white/[0.03] border-white/[0.06] text-zinc-400 hover:text-white"
            }`}
            title={isPhysicsActive ? "Pause Physics Simulation (Static Mode)" : "Resume Physics Simulation"}
          >
            {isPhysicsActive ? <Pause className="w-3.5 h-3.5 text-indigo-400" /> : <Play className="w-3.5 h-3.5" />}
          </button>

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
        {/* Network Canvas */}
        <div
          ref={containerRef}
          style={CANVAS_THEMES[canvasTheme].style}
          className="flex-1 h-full w-full cursor-grab active:cursor-grabbing transition-colors duration-150"
        />

        {/* 3. Docked Right Panel: Inspector or Overview Drawer */}
        {isDrawerOpen && (
          <aside className="w-80 md:w-92 border-l border-white/[0.06] bg-[#0e1017]/95 backdrop-blur-md h-full flex flex-col z-30 shadow-2xl transition-all duration-200">
            {selectedNode ? (
              /* Selected Node Inspector with Breadcrumb Path */
              <div className="h-full flex flex-col animate-fade-in">
                <div className="p-4 border-b border-white/[0.06] space-y-2">
                  <div className="flex items-center justify-between">
                    <button
                      onClick={() => {
                        setSelectedNode(null);
                        networkRef.current?.unselectAll();
                        if (onSelectNode) onSelectNode(null);
                      }}
                      className="text-[10px] font-mono text-zinc-400 hover:text-white flex items-center gap-1 transition-colors cursor-pointer"
                    >
                      <span>← Back to Overview</span>
                    </button>
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

                  {/* Breadcrumb Navigation Trail */}
                  {breadcrumbPath.length > 1 && (
                    <div className="flex items-center flex-wrap gap-1 text-[10px] font-mono text-zinc-400 py-1 px-2 rounded bg-white/[0.02] border border-white/[0.04]">
                      {breadcrumbPath.map((crumb, idx) => (
                        <React.Fragment key={crumb.id}>
                          {idx > 0 && <span className="text-zinc-600">/</span>}
                          <button
                            onClick={() => focusOnNode(crumb.id)}
                            className={`hover:text-white transition-colors cursor-pointer truncate max-w-28 ${
                              crumb.id === selectedNode.id
                                ? "text-indigo-400 font-semibold"
                                : "text-zinc-400 hover:underline"
                            }`}
                            title={crumb.id}
                          >
                            {crumb.label || crumb.id}
                          </button>
                        </React.Fragment>
                      ))}
                    </div>
                  )}

                  {/* Node Header */}
                  <div className="flex items-center justify-between gap-2 pt-1">
                    <div className="min-w-0">
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
                  </div>
                </div>

                {/* Inspector Content */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs font-mono">
                  {/* Interactive Collapse / Expand Action Button if container */}
                  {selectedNode && (childrenMap.get(selectedNode.id)?.length || 0) > 0 && (
                    <button
                      onClick={() => toggleExpand(selectedNode.id)}
                      className={`w-full py-2 px-3 rounded-md border font-mono text-xs flex items-center justify-center gap-2 transition-colors cursor-pointer ${
                        expandedNodeIds.has(selectedNode.id)
                          ? "bg-amber-500/15 hover:bg-amber-500/25 border-amber-500/30 text-amber-300"
                          : "bg-indigo-500/15 hover:bg-indigo-500/25 border-indigo-500/30 text-indigo-300"
                      }`}
                    >
                      {expandedNodeIds.has(selectedNode.id) ? (
                        <>
                          <FolderMinus className="w-3.5 h-3.5" />
                          <span>
                            Collapse {selectedNode.type === "Directory" ? "Folder" : selectedNode.type || "Container"} ({childrenMap.get(selectedNode.id)?.length || 0} items)
                          </span>
                        </>
                      ) : (
                        <>
                          <FolderPlus className="w-3.5 h-3.5" />
                          <span>
                            Expand {selectedNode.type === "Directory" ? "Folder" : selectedNode.type || "Container"} ({childrenMap.get(selectedNode.id)?.length || 0} items)
                          </span>
                        </>
                      )}
                    </button>
                  )}

                  {/* Trace Flow Chain Action Button */}
                  <button
                    onClick={() => traceCallChain(selectedNode)}
                    className="w-full py-2 px-3 rounded-md bg-indigo-500/15 hover:bg-indigo-500/25 border border-indigo-500/30 text-indigo-300 font-mono text-xs flex items-center justify-center gap-2 transition-colors cursor-pointer"
                  >
                    <Crosshair className="w-3.5 h-3.5" />
                    <span>Trace Upstream & Downstream Flow</span>
                  </button>

                  {/* File / Directory Location */}
                  {(selectedNode.props?.file_path || selectedNode.props?.path || selectedNode.path) && (
                    <div className="space-y-1">
                      <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">
                        Path Location
                      </span>
                      <div className="flex items-center gap-1.5 text-zinc-300 bg-[#11131a] p-2 rounded-md border border-white/[0.06] break-all text-[11px]">
                        <FileCode className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                        <span>
                          {selectedNode.props?.file_path || selectedNode.props?.path || selectedNode.path}
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Metrics: Degree & Containment */}
                  <div className="grid grid-cols-2 gap-2 text-center">
                    <div className="bg-[#11131a] border border-white/[0.06] rounded p-2">
                      <span className="text-[10px] text-zinc-500 block uppercase">Degree</span>
                      <span className="text-sm font-bold text-white mt-0.5 block">
                        {nodeDegrees.get(selectedNode.id) || 0}
                      </span>
                    </div>
                    <div className="bg-[#11131a] border border-white/[0.06] rounded p-2">
                      <span className="text-[10px] text-zinc-500 block uppercase">Contains</span>
                      <span className="text-sm font-bold text-white mt-0.5 block">
                        {childrenMap.get(selectedNode.id)?.length ?? selectedNode.childCount ?? 0} items
                      </span>
                    </div>
                  </div>

                  {/* Relationships: Defines / Contains */}
                  {selectedDetails && selectedDetails.defines.length > 0 && (
                    <div className="space-y-2">
                      <span className="text-[10px] text-zinc-500 uppercase tracking-wider block font-semibold text-amber-400">
                        {selectedNode.type === "Directory" ? "Contained Files" : "Defines"} (
                        {selectedDetails.defines.length})
                      </span>
                      <div className="space-y-1 max-h-36 overflow-y-auto pr-1">
                        {selectedDetails.defines.map((child, idx) => (
                          <button
                            key={`define-${child.id}-${idx}`}
                            onClick={() => focusOnNode(child.id)}
                            className="w-full text-left p-1.5 rounded bg-[#11131a] hover:bg-white/[0.04] border border-white/[0.06] hover:border-white/[0.12] flex items-center justify-between text-[11px] text-zinc-300 transition-colors cursor-pointer"
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
                      <span className="text-[10px] text-zinc-500 uppercase tracking-wider block font-semibold text-purple-400">
                        Calls ({selectedDetails.calls.length})
                      </span>
                      <div className="space-y-1 max-h-36 overflow-y-auto pr-1">
                        {selectedDetails.calls.map((callee, idx) => (
                          <button
                            key={`call-${callee.id}-${idx}`}
                            onClick={() => focusOnNode(callee.id)}
                            className="w-full text-left p-1.5 rounded bg-[#11131a] hover:bg-white/[0.04] border border-white/[0.06] hover:border-white/[0.12] flex items-center justify-between text-[11px] text-zinc-300 transition-colors cursor-pointer"
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
                        {selectedDetails.callers.map((caller, idx) => (
                          <button
                            key={`caller-${caller.id}-${idx}`}
                            onClick={() => focusOnNode(caller.id)}
                            className="w-full text-left p-1.5 rounded bg-[#11131a] hover:bg-white/[0.04] border border-white/[0.06] hover:border-white/[0.12] flex items-center justify-between text-[11px] text-zinc-300 transition-colors cursor-pointer"
                          >
                            <span className="truncate">{caller.label || caller.id}</span>
                            <ChevronRight className="w-3 h-3 text-zinc-500 shrink-0" />
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Relationships: Imports / Depends */}
                  {selectedDetails && selectedDetails.imports.length > 0 && (
                    <div className="space-y-2">
                      <span className="text-[10px] text-zinc-500 uppercase tracking-wider block font-semibold text-emerald-400">
                        Imports & Dependencies ({selectedDetails.imports.length})
                      </span>
                      <div className="space-y-1 max-h-36 overflow-y-auto pr-1">
                        {selectedDetails.imports.map((imp, idx) => (
                          <button
                            key={`import-${imp.id}-${idx}`}
                            onClick={() => focusOnNode(imp.id)}
                            className="w-full text-left p-1.5 rounded bg-[#11131a] hover:bg-white/[0.04] border border-white/[0.06] hover:border-white/[0.12] flex items-center justify-between text-[11px] text-zinc-300 transition-colors cursor-pointer"
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
              /* Overview Drawer: Filter Presets, Interactive Node Kinds, Interactive Edge Types, Most Connected, and Code Areas */
              <div className="h-full flex flex-col divide-y divide-white/[0.06] text-xs font-mono animate-fade-in overflow-y-auto">
                {/* Active Filter Banner if filtered */}
                {activeFilterCount > 0 && (
                  <div className="p-3 bg-amber-500/10 border-b border-amber-500/20 flex items-center justify-between shrink-0">
                    <div className="flex items-center gap-1.5 min-w-0 pr-2">
                      <Filter className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                      <span className="text-amber-300 font-semibold text-[11px] truncate">
                        {activeFilterCount} active filter{activeFilterCount > 1 ? "s" : ""}
                      </span>
                    </div>
                    <button
                      onClick={resetAllFilters}
                      className="px-2 py-0.5 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 text-[10px] border border-amber-500/30 cursor-pointer shrink-0"
                    >
                      Reset All
                    </button>
                  </div>
                )}

                {/* Filter Presets */}
                <div className="p-3.5 space-y-2 shrink-0">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider block">
                      Quick Presets
                    </span>
                    {activeFilterCount > 0 && (
                      <button
                        onClick={resetAllFilters}
                        className="text-[10px] text-amber-400 hover:text-amber-300 underline cursor-pointer"
                      >
                        Reset
                      </button>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1">
                    <button
                      onClick={() => applyPreset("all")}
                      className={`px-2 py-0.5 rounded text-[10px] border transition-colors cursor-pointer ${
                        activeFilterCount === 0
                          ? "bg-indigo-500/20 text-indigo-300 border-indigo-500/40 font-semibold"
                          : "bg-white/[0.02] text-zinc-400 border-white/[0.06] hover:text-white"
                      }`}
                    >
                      All
                    </button>
                    <button
                      onClick={() => applyPreset("callGraph")}
                      className="px-2 py-0.5 rounded text-[10px] border bg-white/[0.02] text-zinc-400 border-white/[0.06] hover:text-purple-300 hover:border-purple-500/30 transition-colors cursor-pointer"
                    >
                      ⚡ Call Graph
                    </button>
                    <button
                      onClick={() => applyPreset("dependencies")}
                      className="px-2 py-0.5 rounded text-[10px] border bg-white/[0.02] text-zinc-400 border-white/[0.06] hover:text-emerald-300 hover:border-emerald-500/30 transition-colors cursor-pointer"
                    >
                      📦 Dependencies
                    </button>
                    <button
                      onClick={() => applyPreset("architecture")}
                      className="px-2 py-0.5 rounded text-[10px] border bg-white/[0.02] text-zinc-400 border-white/[0.06] hover:text-amber-300 hover:border-amber-500/30 transition-colors cursor-pointer"
                    >
                      📁 Architecture
                    </button>
                    <button
                      onClick={() => applyPreset("pureSemantic")}
                      className="px-2 py-0.5 rounded text-[10px] border bg-white/[0.02] text-zinc-400 border-white/[0.06] hover:text-sky-300 hover:border-sky-500/30 transition-colors cursor-pointer"
                    >
                      ✨ Pure Semantic
                    </button>
                  </div>
                </div>

                {/* Node Kinds Filter */}
                <div className="p-3.5 space-y-2 shrink-0">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">
                      Node Kinds ({selectedNodeCategories.size}/{ALL_NODE_CATEGORIES.length})
                    </span>
                    <button
                      onClick={selectAllNodeCategories}
                      className="text-[10px] text-zinc-500 hover:text-zinc-300 cursor-pointer"
                    >
                      Select All
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-1.5">
                    {ALL_NODE_CATEGORIES.map((cat) => {
                      const isSelected = selectedNodeCategories.has(cat.id);
                      const count = nodeCategoryCounts[cat.id] || 0;
                      return (
                        <div
                          key={`drawer-node-${cat.id}`}
                          className={`group flex items-center justify-between px-2 py-1.5 rounded-md border text-[11px] transition-colors cursor-pointer ${
                            isSelected
                              ? "bg-white/[0.04] border-white/[0.12] text-zinc-200"
                              : "bg-white/[0.01] border-white/[0.04] text-zinc-500 opacity-60"
                          }`}
                          onClick={() => toggleNodeCategory(cat.id)}
                        >
                          <div className="flex items-center gap-1.5 min-w-0 pr-1">
                            <span className="text-xs">{cat.icon}</span>
                            <span className="truncate">{cat.label}</span>
                          </div>
                          <div className="flex items-center gap-1 shrink-0">
                            <span className="text-[10px] text-zinc-500 font-mono">
                              {count}
                            </span>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                isolateNodeCategory(cat.id);
                              }}
                              className="text-[9px] uppercase px-1 py-0.2 rounded bg-white/[0.06] hover:bg-white/[0.15] text-zinc-400 hover:text-white hidden group-hover:inline-block cursor-pointer"
                              title={`Show only ${cat.label}`}
                            >
                              only
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Interactive Edge Types & Legend */}
                <div className="p-3.5 space-y-2 shrink-0">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">
                      Edge Types ({selectedEdgeTypes.size}/{ALL_EDGE_CATEGORIES.length})
                    </span>
                    <button
                      onClick={selectAllEdgeTypes}
                      className="text-[10px] text-zinc-500 hover:text-zinc-300 cursor-pointer"
                    >
                      Select All
                    </button>
                  </div>
                  <div className="space-y-1.5">
                    {ALL_EDGE_CATEGORIES.map((edge) => {
                      const isSelected = selectedEdgeTypes.has(edge.id);
                      const count = edgeCategoryCounts[edge.id] || 0;
                      return (
                        <div
                          key={`drawer-edge-${edge.id}`}
                          onClick={() => toggleEdgeType(edge.id)}
                          className={`group flex items-center justify-between p-2 rounded-md border text-[11px] transition-colors cursor-pointer ${
                            isSelected
                              ? "bg-white/[0.04] border-white/[0.12] text-zinc-200"
                              : "bg-white/[0.01] border-white/[0.04] text-zinc-500 opacity-60"
                          }`}
                        >
                          <div className="flex items-center gap-2 min-w-0 pr-2">
                            <span className={`font-mono text-xs font-bold tracking-tighter ${edge.color}`}>
                              {edge.symbol}
                            </span>
                            <div className="min-w-0">
                              <span className="block truncate font-semibold">{edge.label}</span>
                              <span className="text-[9px] text-zinc-500 block truncate font-mono">
                                {edge.desc}
                              </span>
                            </div>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <span className="text-[10px] text-zinc-400 font-mono font-semibold">
                              {count}
                            </span>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                isolateEdgeType(edge.id);
                              }}
                              className="text-[9px] uppercase px-1.5 py-0.5 rounded bg-white/[0.06] hover:bg-white/[0.15] text-zinc-400 hover:text-white hidden group-hover:inline-block cursor-pointer"
                              title={`Show only ${edge.label}`}
                            >
                              only
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <div className="text-[10px] text-zinc-500 space-y-0.5 pt-1">
                    <p>• <span className="text-zinc-400">Click edge</span> to toggle visibility</p>
                    <p>• <span className="text-zinc-400">Single-click node</span>: select & inspect</p>
                    <p>• <span className="text-zinc-400">Double-click node</span>: expand / collapse</p>
                  </div>
                </div>

                {/* Most Connected Panel */}
                <div className="p-3.5 flex-1 min-h-[160px] flex flex-col">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">
                      Most connected
                    </span>
                    <span className="text-[10px] text-zinc-600">Top 15</span>
                  </div>
                  <div className="flex-1 overflow-y-auto space-y-1 pr-1 max-h-48">
                    {mostConnectedNodes.map((n, idx) => {
                      const deg = nodeDegrees.get(n.id) || 0;
                      const cIdx = communityMap.get(n.id) ?? 0;
                      const pal = COMMUNITY_PALETTE[cIdx];
                      const isInferred = n.props?.provenance === "INFERRED" || n.type === "Inferred";

                      return (
                        <button
                          key={`most-connected-${n.id}-${idx}`}
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

                {/* Code Area Legend & Filter Panel */}
                <div className="p-3.5 max-h-56 overflow-y-auto shrink-0">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">
                      Code Areas ({communities.length})
                    </span>
                    {selectedCommunity && (
                      <button
                        onClick={() => setSelectedCommunity(null)}
                        className="text-[10px] text-amber-400 hover:text-amber-300 underline cursor-pointer"
                      >
                        Show All
                      </button>
                    )}
                  </div>
                  <div className="space-y-1.5">
                    {communities.map((comm, idx) => {
                      const pal = COMMUNITY_PALETTE[idx % COMMUNITY_PALETTE.length];
                      const count = data.nodes.filter((n) => getCommunityName(n) === comm).length;
                      const isSelected = selectedCommunity === comm;
                      return (
                        <button
                          key={`comm-${comm}-${idx}`}
                          onClick={() => setSelectedCommunity(isSelected ? null : comm)}
                          className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded border text-[11px] transition-colors cursor-pointer text-left ${
                            isSelected
                              ? "bg-indigo-500/20 border-indigo-500/50 text-indigo-200"
                              : "bg-white/[0.02] border-white/[0.04] hover:bg-white/[0.05] hover:border-white/[0.1] text-zinc-300"
                          }`}
                          title={isSelected ? "Click to show all areas" : `Click to isolate ${comm}`}
                        >
                          <div className="flex items-center gap-2 min-w-0 pr-2">
                            <span
                              className="w-2.5 h-2.5 rounded-full shrink-0"
                              style={{ backgroundColor: pal.bg }}
                            />
                            <span className="truncate">{comm}</span>
                          </div>
                          <div className="flex items-center gap-1.5 shrink-0">
                            {isSelected && (
                              <span className="text-[9px] uppercase px-1 rounded bg-indigo-500/30 text-indigo-300 font-bold">
                                isolated
                              </span>
                            )}
                            <span className="text-[10px] text-zinc-500 font-mono font-semibold">
                              {count}
                            </span>
                          </div>
                        </button>
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
