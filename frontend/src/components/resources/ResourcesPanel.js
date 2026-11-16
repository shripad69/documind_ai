import React, { useEffect, useRef, useState } from 'react';
import api, { getErrorMessage } from '../../api';
import { FileTypeLogo, Icon } from '../ui/Icons';

export default function ResourcesPanel({
  open,
  workspace,
  documents = [],
  refresh,
  onClose,
  onDeleteDocument,
  onOpenMindMap,
}) {
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
      const first = [
        ...(panelRef.current?.querySelectorAll('button:not(:disabled),input:not(:disabled)') || []),
      ].find(element => element.getClientRects().length);
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
        const focusable = [
          ...panelRef.current.querySelectorAll(
            'button:not(:disabled),input:not(:disabled),[tabindex="0"]'
          ),
        ].filter(element => element.getClientRects().length);
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener('keydown', keydown);
    return () => document.removeEventListener('keydown', keydown);
  }, [open]);

  async function upload(fileList) {
    const files = [...(fileList || [])];
    if (!files.length) return;
    const oversized = files.find(file => file.size > 25 * 1024 * 1024);
    if (oversized) {
      setError(`${oversized.name} exceeds the 25 MB file limit.`);
      return;
    }
    if (files.length > 20) {
      setError('You can upload up to 20 files at a time.');
      return;
    }
    const invalid = files.find(file => !/\.(pdf|docx)$/i.test(file.name));
    if (invalid) {
      setError(`${invalid.name} is not a supported PDF or DOCX file.`);
      return;
    }
    const data = new FormData();
    files.forEach(file => data.append('files', file));
    setBusy(true);
    setError('');
    try {
      await api.post(`/api/workspaces/${workspace.id}/documents`, data);
      await refresh();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  }

  const indexed = documents.filter(doc => doc.status === 'indexed').length;

  return (
    <div
      className={`resources-overlay ${open ? 'open' : ''} ${entered ? 'entered' : ''}`}
      aria-hidden={!open}
      onMouseDown={event => event.target === event.currentTarget && onClose()}
    >
      <section
        ref={panelRef}
        tabIndex="-1"
        className="resources-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="resources-title"
      >
        <header className="panel-header">
          <div>
            <p className="eyebrow">Workspace Library</p>
            <h2 id="resources-title">Documents</h2>
            <span title={workspace?.title}>{workspace?.title}</span>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Close resources panel">
            <Icon name="X" size={18} />
          </button>
        </header>

        <div
          className={`dropzone ${busy ? 'disabled' : ''} ${dragging ? 'dragging' : ''}`}
          role="button"
          tabIndex={busy ? -1 : 0}
          aria-label="Upload PDF or DOCX documents"
          onClick={() => !busy && inputRef.current?.click()}
          onKeyDown={event => {
            if (!busy && (event.key === 'Enter' || event.key === ' ')) {
              event.preventDefault();
              inputRef.current?.click();
            }
          }}
          onDragEnter={event => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragOver={event => event.preventDefault()}
          onDragLeave={event => {
            if (event.currentTarget === event.target) setDragging(false);
          }}
          onDrop={event => {
            event.preventDefault();
            setDragging(false);
            upload(event.dataTransfer.files);
          }}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            multiple
            hidden
            onChange={event => upload(event.target.files)}
          />
          <span className="upload-symbol">
            <Icon name="UploadCloud" size={20} />
          </span>
          <strong>{busy ? 'Uploading and indexing…' : 'Drop documents here to upload'}</strong>
          <span className="dropzone-browse">
            or <b>browse files</b>
          </span>
          <small>PDF and DOCX · Up to 20 files · Max 25 MB each</small>
          {busy && (
            <div className="upload-progress">
              <i />
            </div>
          )}
        </div>

        {error && (
          <div className="error-banner">
            <Icon name="AlertCircle" size={16} />
            <span>{error}</span>
          </div>
        )}

        <div className="resource-list-heading">
          <span>Files</span>
          <span className="doc-summary">
            {indexed} ready · {documents.length} total
          </span>
        </div>

        <div className="resource-list">
          {documents.map(doc => {
            const failed = doc.status === 'failed';
            const ready = doc.status === 'indexed';
            return (
              <div className="resource-item" key={doc.id}>
                <FileTypeLogo fileName={doc.file_name} size={36} />
                <div className="resource-info">
                  <strong title={doc.file_name}>{doc.file_name}</strong>
                  <span
                    className={`status-pill ${
                      ready ? 'ready' : failed ? 'failed' : 'processing'
                    }`}
                  >
                    {ready ? (
                      <Icon name="Check" size={12} />
                    ) : failed ? (
                      <Icon name="AlertCircle" size={12} />
                    ) : (
                      <i className="mini-spinner" />
                    )}
                    {ready ? 'Indexed' : failed ? 'Failed' : 'Indexing…'}
                  </span>
                  {failed && doc.error_message && (
                    <small className="document-error">{doc.error_message}</small>
                  )}
                </div>
                <div className="resource-actions">
                  {ready && (
                    <button
                      className="icon-button mindmap-btn"
                      title="Open interactive topic mind map"
                      aria-label={`Open topic mind map for ${doc.file_name}`}
                      onClick={() => onOpenMindMap?.(doc)}
                    >
                      <Icon name="MindMap" size={16} />
                    </button>
                  )}
                  <button
                    className="icon-button delete-doc"
                    title="Delete document"
                    aria-label={`Delete ${doc.file_name}`}
                    onClick={() => onDeleteDocument?.(doc)}
                  >
                    <Icon name="Trash2" size={15} />
                  </button>
                </div>
              </div>
            );
          })}
          {!documents.length && (
            <div className="empty-resources">
              <Icon name="BookOpen" size={24} />
              <strong>No documents uploaded</strong>
              <span>Add a PDF or DOCX file to begin grounded interrogation.</span>
            </div>
          )}
        </div>

        <footer className="panel-footer">
          <span className="status-orb" />
          <span>Documents become searchable once indexing completes.</span>
        </footer>
      </section>
    </div>
  );
}
