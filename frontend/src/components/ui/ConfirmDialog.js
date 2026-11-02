import React, { useState } from 'react';
import Modal from './Modal';
import { Icon } from './Icons';

export default function ConfirmDialog({ open, title = 'Delete item?', itemName, description, confirmLabel = 'Delete', onCancel, onConfirm }) {
  const [busy, setBusy] = useState(false);
  async function confirm() { setBusy(true); try { await onConfirm?.(); } finally { setBusy(false); } }
  return <Modal open={open} onClose={onCancel} title={title} className="confirm-dialog" labelledBy="confirm-title">
    <div className="confirm-content"><div className="confirm-icon"><Icon name="AlertCircle" size={22} /></div>
      <p>{description || 'This action permanently deletes this item and its associated data.'}</p>
      {itemName && <div className="confirm-item">{itemName}</div>}
    </div>
    <footer className="dialog-actions"><button className="secondary-button" onClick={onCancel} disabled={busy}>Cancel</button><button className="danger-button" onClick={confirm} disabled={busy}>{busy && <span className="spinner" />}{busy ? 'Deleting…' : confirmLabel}</button></footer>
  </Modal>;
}
