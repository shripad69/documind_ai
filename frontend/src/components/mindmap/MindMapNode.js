import React, { memo } from 'react';
import { Handle, Position } from '@xyflow/react';

function MindMapNode({ id, data }) {
  const {
    label,
    query,
    isRoot = false,
    hasChildren = false,
    isCollapsed = false,
    onToggleCollapse,
    onQuery,
  } = data;

  function handleClick(event) {
    event.stopPropagation();
    if (hasChildren) {
      if (onToggleCollapse) {
        onToggleCollapse(id);
      }
    } else if (onQuery && query) {
      onQuery(query, label);
    }
  }

  function handleToggleClick(event) {
    event.stopPropagation();
    if (onToggleCollapse) {
      onToggleCollapse(id);
    }
  }

  const tooltipTitle = hasChildren
    ? isCollapsed
      ? `Expand "${label}" sub-topics`
      : `Collapse "${label}" sub-topics`
    : query
      ? `Ask chatbot: "${query}"`
      : label;

  return (
    <div
      className={`mindmap-node ${isRoot ? 'root-node' : 'branch-node'} ${hasChildren ? 'has-children' : ''} ${isCollapsed ? 'is-collapsed' : 'is-expanded'}`}
      onClick={handleClick}
      title={tooltipTitle}
      role="button"
      tabIndex={0}
      onKeyDown={event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          handleClick(event);
        }
      }}
    >
      {!isRoot && (
        <Handle
          type="target"
          position={Position.Left}
          className="mindmap-handle target-handle"
          isConnectable={false}
        />
      )}

      <div className="mindmap-node-content">
        <span className="mindmap-node-label">{label}</span>
      </div>

      {hasChildren && (
        <button
          type="button"
          className="mindmap-toggle-badge nodrag nopan"
          onClick={handleToggleClick}
          aria-label={isCollapsed ? `Expand ${label} sub-topics` : `Collapse ${label} sub-topics`}
          title={isCollapsed ? 'Expand branches' : 'Collapse branches'}
        >
          {isCollapsed ? '>' : '<'}
        </button>
      )}

      {hasChildren && (
        <Handle
          type="source"
          position={Position.Right}
          className="mindmap-handle source-handle"
          isConnectable={false}
        />
      )}
    </div>
  );
}

export default memo(MindMapNode);
