"use client";

import React from "react";
import { VisGraph } from "./VisGraph";
import { GraphData, GraphNode } from "../../lib/types";

interface InteractiveGraphProps {
  data: GraphData;
  onSelectNode?: (node: GraphNode | null) => void;
  selectedNodeId?: string | null;
}

export const InteractiveGraph: React.FC<InteractiveGraphProps> = (props) => {
  return <VisGraph {...props} />;
};
