import React from 'react';

export function Skeleton({ className = '' }) { return <span className={`skeleton ${className}`} aria-hidden="true" />; }
export function SidebarSkeleton({ rows = 3 }) { return <div className="skeleton-list" aria-label="Loading"><Skeleton className="skeleton-title" />{Array.from({ length: rows }, (_, i) => <Skeleton key={i} className="skeleton-row" />)}</div>; }
export function MessageSkeleton() { return <div className="message-skeleton"><Skeleton /><div><Skeleton /><Skeleton /><Skeleton /></div></div>; }
