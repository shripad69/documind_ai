import { useMemo } from 'react';
import dagre from '@dagrejs/dagre';

export function getDefaultCollapsedIds(root) {
  const collapsed = new Set();
  if (!root || !Array.isArray(root.children)) {
    return collapsed;
  }

  function traverse(node, level) {
    if (!node) return;
    const hasChildren = Array.isArray(node.children) && node.children.length > 0;
    // Level 0 (root) is open. Level 1 nodes with children start collapsed.
    if (level >= 1 && hasChildren) {
      collapsed.add(node.id);
    }
    if (hasChildren) {
      const seenLabels = new Set();
      const seenIds = new Set();
      node.children.forEach(child => {
        if (!child || !child.id) return;
        const normLabel = (child.label || '').trim().toLowerCase();
        if (seenIds.has(child.id) || (normLabel && seenLabels.has(normLabel))) return;
        seenIds.add(child.id);
        if (normLabel) seenLabels.add(normLabel);
        traverse(child, level + 1);
      });
    }
  }

  traverse(root, 0);
  return collapsed;
}

export function getAllCollapsibleIds(root) {
  const ids = new Set();
  if (!root) return ids;

  function traverse(node) {
    if (!node) return;
    if (Array.isArray(node.children) && node.children.length > 0) {
      ids.add(node.id);
      const seenLabels = new Set();
      const seenIds = new Set();
      node.children.forEach(child => {
        if (!child || !child.id) return;
        const normLabel = (child.label || '').trim().toLowerCase();
        if (seenIds.has(child.id) || (normLabel && seenLabels.has(normLabel))) return;
        seenIds.add(child.id);
        if (normLabel) seenLabels.add(normLabel);
        traverse(child);
      });
    }
  }

  traverse(root);
  return ids;
}

export function useMindMapLayout(treeData, collapsedIds, onToggleCollapse, onQuery) {
  return useMemo(() => {
    if (!treeData) {
      return { nodes: [], edges: [] };
    }

    const g = new dagre.graphlib.Graph();
    g.setDefaultEdgeLabel(() => ({}));
    g.setGraph({
      rankdir: 'LR',
      nodesep: 34,
      ranksep: 90,
      marginx: 80,
      marginy: 60,
    });

    const visibleNodes = [];
    const visibleEdges = [];
    const seenEdgeIds = new Set();
    const nodeMeta = new Map();

    function visit(node, level, parentId = null) {
      if (!node || !node.id) return;
      const isRoot = level === 0;
      const hasChildren = Array.isArray(node.children) && node.children.length > 0;
      const isCollapsed = collapsedIds.has(node.id);

      const labelLength = (node.label || '').length;
      const width = isRoot ? Math.max(200, Math.min(300, labelLength * 10 + 64)) : Math.max(160, Math.min(260, labelLength * 9 + 52));
      const height = isRoot ? 54 : 46;

      g.setNode(node.id, { width, height });
      nodeMeta.set(node.id, { node, level, isRoot, hasChildren, isCollapsed, width, height });

      if (parentId) {
        const edgeId = `edge-${parentId}-${node.id}`;
        if (!seenEdgeIds.has(edgeId)) {
          seenEdgeIds.add(edgeId);
          g.setEdge(parentId, node.id);
          visibleEdges.push({
            id: edgeId,
            source: parentId,
            target: node.id,
            type: 'bezier',
            animated: false,
            style: {
              stroke: level === 1 ? 'rgba(56, 189, 248, 0.55)' : 'rgba(56, 189, 248, 0.28)',
              strokeWidth: 2,
            },
          });
        }
      }

      // If not collapsed, recursively visit all unique children
      if (hasChildren && !isCollapsed) {
        const seenChildLabels = new Set();
        const seenChildIds = new Set();
        const uniqueChildren = [];
        for (const child of node.children) {
          if (!child || !child.id) continue;
          const normLabel = (child.label || '').trim().toLowerCase();
          if (seenChildIds.has(child.id) || (normLabel && seenChildLabels.has(normLabel))) {
            continue;
          }
          seenChildIds.add(child.id);
          if (normLabel) seenChildLabels.add(normLabel);
          uniqueChildren.push(child);
        }
        uniqueChildren.forEach(child => visit(child, level + 1, node.id));
      }
    }

    visit(treeData, 0);
    dagre.layout(g);

    const seenNodeIds = new Set();
    nodeMeta.forEach(({ node, level, isRoot, hasChildren, isCollapsed, width, height }, id) => {
      if (seenNodeIds.has(id)) return;
      seenNodeIds.add(id);
      const pos = g.node(id);
      if (!pos) return;

      visibleNodes.push({
        id,
        type: 'mindMapNode',
        position: {
          x: Math.round(pos.x - width / 2),
          y: Math.round(pos.y - height / 2),
        },
        // React Flow sets pointer-events: none on non-draggable, non-selectable
        // nodes without node handlers. The custom node owns its click behavior.
        style: { pointerEvents: 'all' },
        data: {
          label: node.label,
          query: node.query,
          level,
          isRoot,
          hasChildren,
          isCollapsed,
          onToggleCollapse,
          onQuery,
        },
      });
    });

    return { nodes: visibleNodes, edges: visibleEdges };
  }, [treeData, collapsedIds, onToggleCollapse, onQuery]);
}
