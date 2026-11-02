import React, { useEffect } from 'react';
import { Icon } from './Icons';

export default function Toast({ toast, onDismiss }) {
  useEffect(() => { if (!toast) return undefined; const id = window.setTimeout(onDismiss, 5200); return () => window.clearTimeout(id); }, [toast, onDismiss]);
  if (!toast) return null;
  return <div className={`toast ${toast.type || 'error'}`} role="status"><Icon name={toast.type === 'success' ? 'Check' : 'AlertCircle'} /><span>{toast.message}</span><button onClick={onDismiss} aria-label="Dismiss notification"><Icon name="X" size={16} /></button></div>;
}
