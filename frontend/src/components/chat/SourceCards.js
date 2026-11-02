import React, { useEffect, useRef, useState } from 'react';
import Modal from '../ui/Modal';
import { FileTypeLogo, Icon } from '../ui/Icons';

function sourceKey(ref) {
  return ref?.citation_id || ref?.chunk_id || `${ref?.document_id ?? ''}:${ref?.page_number ?? ''}:${ref?.snippet ?? ''}`;
}

function escapeRegex(value) { return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

function renderEvidence(text = '', highlight = '') {
  if (!highlight) return text;
  const source = String(text);
  const pattern = new RegExp(String(highlight).trim().split(/\s+/).map(escapeRegex).join('\\s+'), 'i');
  const match = pattern.exec(source);
  if (!match) return source;
  const start = match.index;
  const end = start + match[0].length;
  return <>{source.slice(0, start)}<mark className="source-evidence-highlight">{match[0]}</mark>{source.slice(end)}</>;
}

export default function SourceCards({ references = [], selected, highlightedReference, onInspect, onDismiss, onOpenResources }) {
  const cardElements = useRef(new Map());
  const [copied, setCopied] = useState(false);
  const highlightedKey = highlightedReference ? sourceKey(highlightedReference) : null;
  useEffect(() => {
    if (highlightedKey) cardElements.current.get(highlightedKey)?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' });
  }, [highlightedKey]);
  if (!references.length) return null;
  const source = selected?.source;
  async function copyPassage() {
    try {
      await navigator.clipboard.writeText(source?.full_text || source?.snippet || '');
      setCopied(true); window.setTimeout(() => setCopied(false), 2000);
    } catch (_) { setCopied(false); }
  }
  return <section className="sources-section" aria-label="Cited passages"><div className="sources-label"><span>SOURCES</span><span>{references.length} cited passage{references.length === 1 ? '' : 's'}</span></div>
    <div className="source-grid">{references.map((ref, index) => {
      const key = sourceKey(ref);
      const highlighted = highlightedKey === key;
      return <button type="button" className={`source-card ${highlighted ? 'highlighted' : ''}`} key={`${key}-${index}`} ref={element => {
        if (element) cardElements.current.set(key, element);
        else cardElements.current.delete(key);
      }} onClick={() => onInspect?.(ref, index)} aria-label={`Open source ${index + 1}: ${ref?.file_name || 'Workspace document'}`}>
        <div className="source-card-top"><span className="source-index">#{ref?.citation_number || index + 1}</span><FileTypeLogo fileName={ref?.file_name} size={38} /></div>
        <strong className="source-title" title={ref?.file_name}>{ref?.file_name || 'Workspace document'}</strong>
        {ref?.page_number != null && <span className="page-badge">Page {ref.page_number}</span>}
        <span className="source-preview">{renderEvidence(ref?.snippet || ref?.full_text || 'No passage preview available.', ref?.highlight_text)}</span>
      </button>;
    })}</div>
    <Modal open={Boolean(source)} onClose={onDismiss} title="Source passage" className="source-dialog" labelledBy="source-title">
      {source && <div className="source-inspector"><div className="source-inspector-meta"><FileTypeLogo fileName={source.file_name} size={42} /><div className="source-inspector-title"><strong>{source.file_name || 'Workspace document'}</strong><span>{source.page_number != null ? `Page ${source.page_number}` : 'Document passage'}</span></div></div><div className="source-full-text">{renderEvidence(source.full_text || source.snippet || 'No passage text is available for this citation.', source.highlight_text)}</div><div className="source-ref-id">Citation #{source.citation_number || (selected.index + 1)}</div><div className="source-inspector-actions"><button className="secondary-button" onClick={copyPassage} title="Copy the complete passage" aria-label="Copy passage"><Icon name={copied ? 'Check' : 'Copy'} size={14} />{copied ? 'Copied!' : 'Copy Passage'}</button><button className="primary-button" onClick={() => { onDismiss?.(); onOpenResources?.(); }} title="Open the workspace document library" aria-label="Open resources"><Icon name="BookOpen" size={14} />Open Resources</button></div></div>}
    </Modal>
  </section>;
}
