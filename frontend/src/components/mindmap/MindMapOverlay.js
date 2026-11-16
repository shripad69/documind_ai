import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Background,
  BackgroundVariant,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { toPng } from 'html-to-image';

import api, { getErrorMessage } from '../../api';
import { Icon } from '../ui/Icons';
import MindMapNode from './MindMapNode';
import {
  getAllCollapsibleIds,
  getDefaultCollapsedIds,
  useMindMapLayout,
} from './useMindMapLayout';

const nodeTypes = {
  mindMapNode: MindMapNode,
};

const loadingStages = [
  'Reading document sections…',
  'Extracting core hierarchy and topics…',
  'Formulating exploration queries…',
  'Assembling interactive mind map…',
];

function MindMapCanvas({
  treeData,
  documentTitle,
  workspace,
  document: doc,
  onClose,
  onQuery,
  onRefresh,
}) {
  const { zoomIn, zoomOut, fitView } = useReactFlow();
  const [collapsedIds, setCollapsedIds] = useState(() => getDefaultCollapsedIds(treeData));
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const containerRef = useRef(null);

  // Smooth fitView whenever layout changes
  const handleToggleCollapse = useCallback(nodeId => {
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
    treeData,
    collapsedIds,
    handleToggleCollapse,
    onQuery
  );

  // Trigger fitView after initial node render and subsequent layout shifts
  useEffect(() => {
    const timer = setTimeout(() => {
      fitView({ padding: 0.22, duration: 450 });
    }, 60);
    return () => clearTimeout(timer);
  }, [collapsedIds, fitView]);

  // Expand / Collapse all toggle
  const allCollapsible = useMemo(() => getAllCollapsibleIds(treeData), [treeData]);
  const isAllCollapsed = allCollapsible.size > 0 && Array.from(allCollapsible).every(id => collapsedIds.has(id));

  function toggleAll() {
    if (isAllCollapsed) {
      setCollapsedIds(new Set());
    } else {
      setCollapsedIds(new Set(allCollapsible));
    }
  }

  // Fullscreen toggle
  function toggleFullscreen() {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen?.().catch(() => {});
      setIsFullscreen(true);
    } else {
      document.exitFullscreen?.().catch(() => {});
      setIsFullscreen(false);
    }
  }

  // Export as PNG
  async function exportPng() {
    if (exporting) return;
    const viewport = containerRef.current?.querySelector('.react-flow__viewport');
    if (!viewport) return;
    setExporting(true);
    try {
      const dataUrl = await toPng(viewport, {
        backgroundColor: '#0B0E14',
        quality: 0.95,
        pixelRatio: 2,
      });
      const link = document.createElement('a');
      link.download = `${(documentTitle || 'document').replace(/[^a-zA-Z0-9_-]/g, '_')}-mindmap.png`;
      link.href = dataUrl;
      link.click();
    } catch (err) {
      console.error('Failed to export mind map as PNG', err);
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="mindmap-container" ref={containerRef}>
      {/* Top Header Bar */}
      <header className="mindmap-header">
        <div className="mindmap-header-left">
          <div className="mindmap-header-icon">
            <Icon name="MindMap" size={20} />
          </div>
          <div className="mindmap-header-title-wrap">
            <strong className="mindmap-header-title" title={documentTitle}>
              {documentTitle} Mind Map
            </strong>
            <span className="mindmap-source-pill">
              <Icon name="BookOpen" size={12} />
              View 1 source
            </span>
          </div>
        </div>

        <div className="mindmap-header-actions">
          <button
            type="button"
            className="mindmap-header-btn"
            onClick={onRefresh}
            title="Regenerate mind map"
            aria-label="Regenerate mind map"
          >
            <Icon name="Sparkles" size={16} />
            <span className="btn-text">Regenerate</span>
          </button>
          <button
            type="button"
            className="mindmap-header-btn"
            onClick={toggleFullscreen}
            title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
            aria-label={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
          >
            <Icon name={isFullscreen ? 'Minimize' : 'Maximize'} size={17} />
          </button>
          <button
            type="button"
            className="mindmap-header-btn close-btn"
            onClick={onClose}
            title="Close mind map (Esc)"
            aria-label="Close mind map"
          >
            <Icon name="X" size={19} />
          </button>
        </div>
      </header>

      {/* React Flow Canvas */}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.2}
        maxZoom={2.2}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={24}
          size={1.5}
          color="rgba(255, 255, 255, 0.08)"
        />
      </ReactFlow>

      {/* Floating Bottom-Right Control Dock */}
      <nav className="mindmap-control-dock" aria-label="Mind map controls">
        <button
          type="button"
          className="dock-button"
          onClick={toggleAll}
          title={isAllCollapsed ? 'Expand all branches' : 'Collapse all branches'}
          aria-label={isAllCollapsed ? 'Expand all branches' : 'Collapse all branches'}
        >
          <Icon name="ChevronsUpDown" size={18} />
        </button>
        <button
          type="button"
          className="dock-button"
          onClick={() => zoomIn({ duration: 250 })}
          title="Zoom in"
          aria-label="Zoom in"
        >
          <Icon name="ZoomIn" size={18} />
        </button>
        <button
          type="button"
          className="dock-button"
          onClick={() => zoomOut({ duration: 250 })}
          title="Zoom out"
          aria-label="Zoom out"
        >
          <Icon name="ZoomOut" size={18} />
        </button>
        <button
          type="button"
          className={`dock-button ${exporting ? 'disabled' : ''}`}
          onClick={exportPng}
          disabled={exporting}
          title="Download mind map as PNG"
          aria-label="Download mind map as PNG"
        >
          {exporting ? <span className="mini-spinner" /> : <Icon name="Download" size={18} />}
        </button>
      </nav>

      <div className="mindmap-click-hint">
        Click expandable nodes to reveal sub-topics · Click leaf nodes to explore with RAG chat
      </div>
    </div>
  );
}

export default function MindMapOverlay({
  open,
  workspace,
  document: doc,
  onClose,
  onQuery,
}) {
  const [loading, setLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [loadingStage, setLoadingStage] = useState(0);
  const [error, setError] = useState('');
  const [treeData, setTreeData] = useState(null);

  const activeDocIdRef = useRef(null);
  const inFlightRef = useRef(false);
  const stageTimerRef = useRef(null);
  const openRef = useRef(open);
  const isMountedRef = useRef(true);

  const clearStageTimer = useCallback(() => {
    if (stageTimerRef.current) {
      clearInterval(stageTimerRef.current);
      stageTimerRef.current = null;
    }
  }, []);

  const startStageTimer = useCallback(() => {
    clearStageTimer();
    setLoadingStage(0);
    stageTimerRef.current = setInterval(() => {
      setLoadingStage(prev => (prev + 1) % loadingStages.length);
    }, 2800);
  }, [clearStageTimer]);

  // Track mount status and cleanup timer on unmount
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      clearStageTimer();
    };
  }, [clearStageTimer]);

  // Close on Escape key
  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === 'Escape' && open) {
        onClose();
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  // Reset state when overlay is closed
  useEffect(() => {
    openRef.current = open;
    if (!open) {
      clearStageTimer();
      activeDocIdRef.current = null;
      inFlightRef.current = false;
      setLoading(false);
      setIsGenerating(false);
      setTreeData(null);
      setError('');
    }
  }, [open, clearStageTimer]);

  const fetchOrGenerateMindMap = useCallback(async (forceRegenerate = false) => {
    if (!workspace?.id || !doc?.id) return;
    if (inFlightRef.current) return;

    const targetDocId = doc.id;
    inFlightRef.current = true;
    setError('');

    try {
      if (forceRegenerate) {
        // Immediate clean reset of mind map state for fresh generation
        setTreeData(null);
        setIsGenerating(true);
        setLoading(true);
        startStageTimer();

        const url = `/api/workspaces/${workspace.id}/documents/${doc.id}/mindmap?force=true&refresh=true`;
        const response = await api.post(url, {
          force: true,
          force_regenerate: true,
          refresh: true,
        });

        if (isMountedRef.current && openRef.current && activeDocIdRef.current === targetDocId) {
          setTreeData(response.data?.tree_data || null);
        }
      } else {
        // Fast-path: check if valid cached mind map already exists
        setLoading(true);
        setIsGenerating(false);

        let cachedTree = null;
        try {
          const cachedRes = await api.get(`/api/workspaces/${workspace.id}/documents/${doc.id}/mindmap`);
          const tree = cachedRes.data?.tree_data;
          if (tree && Array.isArray(tree.children) && tree.children.length > 0) {
            cachedTree = tree;
          }
        } catch (_) {
          // Not cached or incomplete
          cachedTree = null;
        }

        if (cachedTree) {
          if (isMountedRef.current && openRef.current && activeDocIdRef.current === targetDocId) {
            setTreeData(cachedTree);
          }
        } else {
          // Not cached, start fresh generation
          setIsGenerating(true);
          startStageTimer();

          const response = await api.post(`/api/workspaces/${workspace.id}/documents/${doc.id}/mindmap`);
          if (isMountedRef.current && openRef.current && activeDocIdRef.current === targetDocId) {
            setTreeData(response.data?.tree_data || null);
          }
        }
      }
    } catch (err) {
      if (isMountedRef.current && openRef.current && activeDocIdRef.current === targetDocId) {
        setError(getErrorMessage(err));
      }
    } finally {
      clearStageTimer();
      if (isMountedRef.current && activeDocIdRef.current === targetDocId) {
        setLoading(false);
        setIsGenerating(false);
      }
      inFlightRef.current = false;
    }
  }, [workspace?.id, doc?.id, startStageTimer, clearStageTimer]);

  useEffect(() => {
    if (open && doc?.id) {
      if (activeDocIdRef.current === doc.id) {
        return; // Prevent polling re-triggers while viewing
      }
      activeDocIdRef.current = doc.id;
      fetchOrGenerateMindMap(false);
    }
  }, [open, doc?.id, fetchOrGenerateMindMap]);

  if (!open) return null;

  return (
    <div className="mindmap-overlay" role="dialog" aria-modal="true" aria-label="Mind Map">
      {loading && (
        <div className="mindmap-loading-card">
          <div className="mindmap-spinner-wrap">
            <Icon name="MindMap" size={36} className="rotating-mindmap-icon" />
          </div>
          <h3>{isGenerating ? 'Generating Interactive Mind Map' : 'Loading Mind Map'}</h3>
          <p className="loading-subtitle">
            {isGenerating ? 'Analyzing' : 'Opening'} <strong>{doc?.file_name}</strong>
          </p>
          {isGenerating && (
            <span className="loading-stage-text" key={loadingStage}>
              {loadingStages[loadingStage]}
            </span>
          )}
          <div className="mindmap-loading-bar">
            <i />
          </div>
        </div>
      )}

      {error && !loading && (
        <div className="mindmap-error-card">
          <Icon name="AlertCircle" size={32} />
          <h3>Could Not Load Mind Map</h3>
          <p>{error}</p>
          <div className="mindmap-error-actions">
            <button
              type="button"
              className="primary-button"
              onClick={() => fetchOrGenerateMindMap(true)}
            >
              <Icon name="Sparkles" size={16} />
              Retry Generation
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={onClose}
            >
              Close
            </button>
          </div>
        </div>
      )}

      {!loading && !error && treeData && (
        <ReactFlowProvider>
          <MindMapCanvas
            treeData={treeData}
            documentTitle={doc?.file_name}
            workspace={workspace}
            document={doc}
            onClose={onClose}
            onQuery={onQuery}
            onRefresh={() => fetchOrGenerateMindMap(true)}
          />
        </ReactFlowProvider>
      )}
    </div>
  );
}
