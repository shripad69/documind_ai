import React, { act, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ReactFlow, ReactFlowProvider } from '@xyflow/react';
import MindMapNode from './MindMapNode';
import { useMindMapLayout, getDefaultCollapsedIds } from './useMindMapLayout';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

if (typeof globalThis.structuredClone === 'undefined') {
  globalThis.structuredClone = obj => JSON.parse(JSON.stringify(obj));
}

// Mock ResizeObserver for JSDOM
globalThis.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

const sampleMindMapTree = {
  id: 'root',
  label: 'Architecture Overview',
  query: 'Summarize Architecture Overview',
  children: [
    {
      id: 'branch-1',
      label: 'Core Services',
      query: 'Explain Core Services',
      children: [
        {
          id: 'branch-1-1',
          label: 'Auth & Security',
          query: 'Explain Auth & Security',
          children: [
            {
              id: 'leaf-1-1-1',
              label: 'JWT Token Rotation',
              query: 'Explain JWT Token Rotation',
              children: [],
            },
          ],
        },
        {
          id: 'leaf-1-2',
          label: 'Ingestion Pipeline',
          query: 'Explain Ingestion Pipeline',
          children: [],
        },
      ],
    },
    {
      id: 'leaf-2',
      label: 'Vector Store (Leaf)',
      query: 'Explain Vector Store',
      children: [],
    },
  ],
};

const nodeTypes = {
  mindMapNode: MindMapNode,
};

function MindMapCanvasHarness({ onQuerySpy }) {
  const [collapsedIds, setCollapsedIds] = useState(() => getDefaultCollapsedIds(sampleMindMapTree));

  const handleToggleCollapse = React.useCallback(nodeId => {
    setCollapsedIds(prev => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  }, []);

  const { nodes, edges } = useMindMapLayout(
    sampleMindMapTree,
    collapsedIds,
    handleToggleCollapse,
    onQuerySpy
  );

  return (
    <ReactFlowProvider>
      <div style={{ width: 800, height: 600 }}>
        <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} nodesDraggable={false} nodesConnectable={false} elementsSelectable={false} zoomOnDoubleClick={false} />
      </div>
    </ReactFlowProvider>
  );
}

describe('MindMapNode expand and collapse interactions', () => {
  let container;
  let root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
  });

  test('clicking an expandable node expands it and reveals children without triggering query', () => {
    const queryCalls = [];
    const onQuery = (query, label) => queryCalls.push({ query, label });

    act(() => {
      root.render(<MindMapCanvasHarness onQuerySpy={onQuery} />);
    });

    // Initial state: Level 1 branch Core Services is collapsed
    expect(container.textContent).toContain('Core Services');
    expect(container.textContent).not.toContain('Auth & Security');
    expect(container.textContent).not.toContain('Ingestion Pipeline');

    // Click Core Services node body
    const coreServicesNode = Array.from(container.querySelectorAll('.mindmap-node')).find(
      el => el.textContent.includes('Core Services')
    );
    expect(coreServicesNode).toBeTruthy();
    expect(coreServicesNode.closest('.react-flow__node').style.pointerEvents).toBe('all');

    act(() => {
      coreServicesNode.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    });

    // Children are now revealed
    expect(container.textContent).toContain('Auth & Security');
    expect(container.textContent).toContain('Ingestion Pipeline');
    expect(queryCalls).toHaveLength(0); // Should NOT have triggered a chat query

    // Click Core Services node again to collapse
    act(() => {
      coreServicesNode.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    });

    // Children should now be hidden
    expect(container.textContent).not.toContain('Auth & Security');
    expect(container.textContent).not.toContain('Ingestion Pipeline');
    expect(queryCalls).toHaveLength(0);
  });

  test('clicking toggle badge button expands and collapses children', () => {
    const queryCalls = [];
    const onQuery = (query, label) => queryCalls.push({ query, label });

    act(() => {
      root.render(<MindMapCanvasHarness onQuerySpy={onQuery} />);
    });

    const coreServicesNode = Array.from(container.querySelectorAll('.mindmap-node')).find(
      el => el.textContent.includes('Core Services')
    );
    const badge = coreServicesNode.querySelector('.mindmap-toggle-badge');
    expect(badge).toBeTruthy();

    // Click badge to expand
    act(() => {
      badge.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    });

    expect(container.textContent).toContain('Auth & Security');
    expect(queryCalls).toHaveLength(0);

    // Click badge to collapse
    act(() => {
      badge.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    });

    expect(container.textContent).not.toContain('Auth & Security');
    expect(queryCalls).toHaveLength(0);
  });

  test('multi-level hierarchy expansion works across Level 1, 2, and 3', () => {
    const queryCalls = [];
    const onQuery = (query, label) => queryCalls.push({ query, label });

    act(() => {
      root.render(<MindMapCanvasHarness onQuerySpy={onQuery} />);
    });

    // Level 1: Expand Core Services
    const coreServicesNode = Array.from(container.querySelectorAll('.mindmap-node')).find(
      el => el.textContent.includes('Core Services')
    );
    act(() => {
      coreServicesNode.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    });
    expect(container.textContent).toContain('Auth & Security');
    expect(container.textContent).not.toContain('JWT Token Rotation');

    // Level 2: Expand Auth & Security
    const authNode = Array.from(container.querySelectorAll('.mindmap-node')).find(
      el => el.textContent.includes('Auth & Security')
    );
    expect(authNode).toBeTruthy();
    act(() => {
      authNode.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    });

    // Level 3: JWT Token Rotation should now be visible
    expect(container.textContent).toContain('JWT Token Rotation');
    expect(queryCalls).toHaveLength(0);
  });

  test('clicking a leaf node triggers onQuery for RAG chat exploration', () => {
    const queryCalls = [];
    const onQuery = (query, label) => queryCalls.push({ query, label });

    act(() => {
      root.render(<MindMapCanvasHarness onQuerySpy={onQuery} />);
    });

    // Vector Store is a leaf node
    const vectorStoreNode = Array.from(container.querySelectorAll('.mindmap-node')).find(
      el => el.textContent.includes('Vector Store')
    );
    expect(vectorStoreNode).toBeTruthy();
    expect(vectorStoreNode.querySelector('.mindmap-toggle-badge')).toBeNull();

    act(() => {
      vectorStoreNode.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    });

    expect(queryCalls).toHaveLength(1);
    expect(queryCalls[0]).toEqual({
      query: 'Explain Vector Store',
      label: 'Vector Store (Leaf)',
    });
  });

  test('pressing Enter or Space on an expandable node toggles collapse', () => {
    const queryCalls = [];
    const onQuery = (query, label) => queryCalls.push({ query, label });

    act(() => {
      root.render(<MindMapCanvasHarness onQuerySpy={onQuery} />);
    });

    const coreServicesNode = Array.from(container.querySelectorAll('.mindmap-node')).find(
      el => el.textContent.includes('Core Services')
    );

    // Press Enter to expand
    act(() => {
      coreServicesNode.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
    });
    expect(container.textContent).toContain('Auth & Security');

    // Press Space to collapse
    act(() => {
      coreServicesNode.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true, cancelable: true }));
    });
    expect(container.textContent).not.toContain('Auth & Security');
  });
});
