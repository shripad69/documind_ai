import React, { useEffect, useRef } from 'react';
import { Icon } from './Icons';

export default function Modal({ open = true, onClose, title, children, className = '', labelledBy }) {
  const dialogRef = useRef(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    if (!open) return undefined;
    const previous = document.activeElement;
    const first = dialogRef.current?.querySelector('input,button,textarea,[tabindex="0"]');
    first?.focus();
    const keydown = event => {
      if (event.key === 'Escape') closeRef.current?.();
      if (event.key === 'Tab' && dialogRef.current) {
        const focusable = [...dialogRef.current.querySelectorAll('button:not(:disabled),input:not(:disabled),textarea:not(:disabled),[href],[tabindex="0"]')];
        if (!focusable.length) return;
        const firstEl = focusable[0], lastEl = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === firstEl) { event.preventDefault(); lastEl.focus(); }
        else if (!event.shiftKey && document.activeElement === lastEl) { event.preventDefault(); firstEl.focus(); }
      }
    };
    document.addEventListener('keydown', keydown);
    return () => { document.removeEventListener('keydown', keydown); previous?.focus?.(); };
  }, [open]);
  if (!open) return null;
  return <div className="modal-backdrop" onMouseDown={event => event.target === event.currentTarget && onClose?.()}>
    <section ref={dialogRef} className={`dialog-card ${className}`} role="dialog" aria-modal="true" aria-labelledby={labelledBy}>
      {(title || onClose) && <header className="dialog-header">{title && <h2 id={labelledBy}>{title}</h2>}{onClose && <button className="icon-button" onClick={onClose} aria-label="Close dialog"><Icon name="X" /></button>}</header>}
      {children}
    </section>
  </div>;
}
