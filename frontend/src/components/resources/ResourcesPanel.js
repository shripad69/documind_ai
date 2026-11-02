import React, { useEffect, useRef, useState } from 'react';
import api, { getErrorMessage } from '../../api';
import { FileTypeLogo, Icon } from '../ui/Icons';

export default function ResourcesPanel({ open, workspace, documents = [], refresh, onClose, onDeleteDocument }) {
  const inputRef = useRef(null);
  const panelRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [entered, setEntered] = useState(false);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  const restoreFocusRef = useRef(null);
  useEffect(() => {
    if (open) {
      restoreFocusRef.current = document.activeElement;
      setEntered(true);
      const first = [...(panelRef.current?.querySelectorAll('button:not(:disabled),input:not(:disabled)') || [])].find(element => element.getClientRects().length);
      (first || panelRef.current)?.focus();
    } else {
      setEntered(false);
      restoreFocusRef.current?.focus?.();
    }
  }, [open]);
  useEffect(() => {
    const keydown = event => {
      if (event.key === 'Escape' && open) closeRef.current?.();
      if (event.key === 'Tab' && open && panelRef.current) {
        const focusable = [...panelRef.current.querySelectorAll('button:not(:disabled),input:not(:disabled),[tabindex="0"]')].filter(element => element.getClientRects().length);
        if (!focusable.length) return;
        const first = focusable[0], last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener('keydown', keydown); return () => document.removeEventListener('keydown', keydown);
  }, [open]);
  async function upload(fileList) {
    const files = [...(fileList || [])];
    if (!files.length) return;
    const oversized = files.find(file => file.size > 25 * 1024 * 1024);
    if (oversized) { setError(`${oversized.name} is larger than the 25 MB per-file limit.`); return; }
    if (files.length > 20) { setError('Upload up to 20 files at a time.'); return; }
    const invalid = files.find(file => !/\.(pdf|docx)$/i.test(file.name));
    if (invalid) { setError(`${invalid.name} is not a PDF or DOCX file.`); return; }
    const data = new FormData(); files.forEach(file => data.append('files', file));
    setBusy(true); setError('');
    try { await api.post(`/api/workspaces/${workspace.id}/documents`, data); await refresh(); }
    catch (err) { setError(getErrorMessage(err)); }
    finally { setBusy(false); if (inputRef.current) inputRef.current.value = ''; }
  }
  const indexed = documents.filter(doc => doc.status === 'indexed').length;
  return <div className={`resources-overlay ${open ? 'open' : ''} ${entered ? 'entered' : ''}`} aria-hidden={!open} onMouseDown={event => event.target === event.currentTarget && onClose()}>
    <section ref={panelRef} tabIndex="-1" className="resources-panel" role="dialog" aria-modal="true" aria-labelledby="resources-title">
      <header className="panel-header"><div><p className="eyebrow">WORKSPACE LIBRARY</p><h2 id="resources-title">Resources</h2><span title={workspace?.title}>{workspace?.title}</span></div><button className="icon-button" onClick={onClose} aria-label="Close resources"><Icon name="X" /></button></header>
      <div className={`dropzone ${busy ? 'disabled' : ''} ${dragging ? 'dragging' : ''}`} role="button" tabIndex={busy ? -1 : 0} aria-label="Choose PDF or DOCX documents to upload" onClick={() => !busy && inputRef.current?.click()} onKeyDown={event => { if (!busy && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); inputRef.current?.click(); } }} onDragEnter={event => { event.preventDefault(); setDragging(true); }} onDragOver={event => event.preventDefault()} onDragLeave={event => { if (event.currentTarget === event.target) setDragging(false); }} onDrop={event => { event.preventDefault(); setDragging(false); upload(event.dataTransfer.files); }}>
        <input ref={inputRef} type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" multiple hidden onChange={event => upload(event.target.files)} />
        <span className="upload-symbol"><Icon name="UploadCloud" size={22} /></span><strong>{busy ? 'Uploading and indexing…' : 'Drop documents to add them'}</strong><span className="dropzone-browse">or <b>browse files</b></span><small>PDF & DOCX · Up to 20 files · Max 25 MB each</small>
        {busy && <div className="upload-progress"><i /></div>}
      </div>
      {error && <div className="error-banner"><Icon name="AlertCircle" size={16} />{error}</div>}
      <div className="resource-list-heading"><span>DOCUMENTS</span><span className="doc-summary">{indexed} ready · {documents.length} total</span></div>
      <div className="resource-list">{documents.map(doc => {
        const failed = doc.status === 'failed'; const ready = doc.status === 'indexed';
        return <div className="resource-item" key={doc.id}><FileTypeLogo fileName={doc.file_name} size={42} /><div className="resource-info"><strong title={doc.file_name}>{doc.file_name}</strong><span className={`status-pill ${ready ? 'ready' : failed ? 'failed' : 'processing'}`}>{ready ? <Icon name="Check" size={12} /> : failed ? <Icon name="AlertCircle" size={12} /> : <i className="mini-spinner" />}{ready ? 'Ready to chat' : failed ? 'Failed' : 'Indexing chunks…'}</span>{failed && doc.error_message && <small className="document-error">{doc.error_message}</small>}</div><button className="icon-button delete-doc" title="Delete document" aria-label={`Delete ${doc.file_name}`} onClick={() => onDeleteDocument?.(doc)}><Icon name="Trash2" size={16} /></button></div>;
      })}
        {!documents.length && <div className="empty-resources"><Icon name="BookOpen" size={24} /><strong>Your library is empty</strong><span>Add a PDF or DOCX to start asking grounded questions.</span></div>}
      </div>
      <footer className="panel-footer"><span className="status-orb" /> Documents become searchable when indexing completes.</footer>
    </section>
  </div>;
}
