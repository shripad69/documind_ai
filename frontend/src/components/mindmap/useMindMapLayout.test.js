import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import {
  getAllCollapsibleIds,
  getDefaultCollapsedIds,
  useMindMapLayout,
} from './useMindMapLayout';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

if (typeof globalThis.structuredClone === 'undefined') {
  globalThis.structuredClone = obj => JSON.parse(JSON.stringify(obj));
}

describe('useMindMapLayout helpers', () => {
  const sampleTree = {
    id: 'root',
    label: 'Main Document Topic',
    query: 'Summarize main topic',
    children: [
      {
        id: 'node-1',
        label: 'Subtopic 1',
        query: 'Explain subtopic 1',
        children: [
          {
            id: 'node-1-1',
            label: 'Detail 1.1',
            query: 'Detail 1.1',
            children: [],
          },
        ],
      },
      {
        id: 'node-2',
        label: 'Subtopic 2 (Leaf)',
        query: 'Explain subtopic 2',
        children: [],
      },
      {
        id: 'node-3',
        label: 'Subtopic 3',
        query: 'Explain subtopic 3',
        children: [
          {
            id: 'node-3-1',
            label: 'Detail 3.1',
            query: 'Detail 3.1',
            children: [
              {
                id: 'node-3-1-1',
                label: 'Deep Point',
                query: 'Deep Point',
                children: [],
              },
            ],
          },
        ],
      },
    ],
  };

  test('getDefaultCollapsedIds starts with root open and level 1 branches collapsed', () => {
    const collapsed = getDefaultCollapsedIds(sampleTree);
    // Root should not be in collapsed set
    expect(collapsed.has('root')).toBe(false);
    // Node-1 has children, so it should be collapsed by default
    expect(collapsed.has('node-1')).toBe(true);
    // Node-2 has no children, so it should not be in collapsed set
    expect(collapsed.has('node-2')).toBe(false);
    // Node-3 has children, so it should be collapsed by default
    expect(collapsed.has('node-3')).toBe(true);
    // Node-3-1 has children, so it should also be in collapsed set
    expect(collapsed.has('node-3-1')).toBe(true);
  });

  test('getAllCollapsibleIds returns all nodes that possess children', () => {
    const all = getAllCollapsibleIds(sampleTree);
    expect(all.has('root')).toBe(true);
    expect(all.has('node-1')).toBe(true);
    expect(all.has('node-2')).toBe(false);
    expect(all.has('node-3')).toBe(true);
    expect(all.has('node-3-1')).toBe(true);
  });

  test('deduplicates sibling nodes with duplicate IDs and identical normalized labels', () => {
    const treeWithDuplicates = {
      id: 'root',
      label: 'Artificial Intelligence',
      query: 'AI Overview',
      children: [
        {
          id: 'child-1',
          label: 'Definitions and Core Approaches',
          query: 'Explain Definitions',
          children: [
            { id: 'sub-1', label: 'Turing Test', query: 'Turing test', children: [] },
          ],
        },
        {
          id: 'child-2',
          // Sibling with identical label (differing only in case/whitespace)
          label: '  definitions and core approaches  ',
          query: 'Duplicate Definitions',
          children: [
            { id: 'sub-2', label: 'Turing Test Duplicate', query: 'Turing test 2', children: [] },
          ],
        },
        {
          id: 'child-1',
          // Sibling with duplicate ID
          label: 'Different Label With Reused ID',
          query: 'Reused ID query',
          children: [],
        },
        {
          id: 'child-3',
          label: 'Philosophical Foundations',
          query: 'Explain Philosophy',
          children: [],
        },
      ],
    };

    const collapsible = getAllCollapsibleIds(treeWithDuplicates);
    // child-1 is collapsible, but duplicate child-2 and second child-1 are dropped
    expect(collapsible.has('child-1')).toBe(true);
    expect(collapsible.has('child-2')).toBe(false);
    expect(collapsible.has('child-3')).toBe(false);

    // Test useMindMapLayout hook with all nodes expanded via test harness component
    let hookResult = null;
    function TestHarness() {
      hookResult = useMindMapLayout(treeWithDuplicates, new Set(), () => {}, () => {});
      return null;
    }

    const testContainer = document.createElement('div');
    const testRoot = createRoot(testContainer);
    act(() => {
      testRoot.render(<TestHarness />);
    });

    expect(hookResult).toBeTruthy();
    const renderedLabels = hookResult.nodes.map(n => n.data.label);
    const definitionsCount = renderedLabels.filter(
      l => l.trim().toLowerCase() === 'definitions and core approaches'
    ).length;
    expect(definitionsCount).toBe(1);

    const nodeIds = hookResult.nodes.map(n => n.id);
    expect(new Set(nodeIds).size).toBe(nodeIds.length); // All node IDs are strictly unique
    expect(nodeIds).toContain('child-1');
    expect(nodeIds).not.toContain('child-2'); // Duplicate sibling skipped
    expect(nodeIds).toContain('child-3');

    // Edges are strictly unique
    const edgeIds = hookResult.edges.map(e => e.id);
    expect(new Set(edgeIds).size).toBe(edgeIds.length);

    act(() => {
      testRoot.unmount();
    });
  });
});
