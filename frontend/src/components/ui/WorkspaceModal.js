import React, { useEffect, useState } from 'react';
import Modal from './Modal';

export default function WorkspaceModal({ open, workspace, onClose, onSave }) {
  const [title, setTitle] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) { setTitle(workspace?.title || ''); setError(''); } }, [open, workspace]);
  async function submit(event) {
    event.preventDefault(); const value = title.trim();
    if (!value) { setError('Enter a workspace name.'); return; }
    if (value.length > 160) { setError('Workspace names can be up to 160 characters.'); return; }
    setBusy(true); setError('');
    try { await onSave(value); onClose(); } catch (err) { setError(err?.message || 'Could not save this workspace.'); }
    finally { setBusy(false); }
  }
  return <Modal open={open} onClose={onClose} title={workspace ? 'Rename workspace' : 'Create workspace'} className="workspace-dialog" labelledBy="workspace-title">
    <form onSubmit={submit}><label className="field-label" htmlFor="workspace-name">Workspace name</label><input id="workspace-name" autoFocus maxLength={160} value={title} onChange={event => setTitle(event.target.value)} placeholder="e.g. Product research" />
      <div className="field-meta">{error ? <span className="field-error">{error}</span> : <span>Give your documents a home.</span>}<span>{title.length}/160</span></div>
      <footer className="dialog-actions"><button type="button" className="secondary-button" onClick={onClose} disabled={busy}>Cancel</button><button className="primary-button" disabled={busy}>{busy && <span className="spinner" />}{busy ? 'Saving…' : workspace ? 'Save changes' : 'Create workspace'}</button></footer>
    </form>
  </Modal>;
}
