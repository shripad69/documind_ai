import React, { useId } from 'react';

const paths = {
  Folder: <><path d="M3.5 6.5h6l2 2h9v10a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/><path d="M3.5 8.5h17"/></>,
  FolderOpen: <><path d="M3.5 6.5h6l2 2h9v8a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/><path d="m2.7 13 1.1-3h17.5l-2.1 7"/></>,
  MessageSquare: <><path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H5l-2 2v-6.5A7.5 7.5 0 1 1 20 11.5Z"/><path d="M7.5 10.5h7M7.5 14h4"/></>,
  Plus: <><path d="M12 5v14M5 12h14"/></>,
  FileText: <><path d="M13 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10z"/><path d="M13 3v7h7M8 14h8M8 17h6"/></>,
  UploadCloud: <><path d="M16 16l-4-4-4 4M12 12v9"/><path d="M20 16.5a4.5 4.5 0 0 0-1.2-8.84A6.5 6.5 0 0 0 6.18 9.1 4 4 0 0 0 7 17h1"/></>,
  Search: <><circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 4 4"/></>,
  Send: <><path d="m21 3-7.2 18-3.6-7.2L3 10.2z"/><path d="M21 3 10.2 13.8"/></>,
  Sparkles: <><path d="m12 3 1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z"/><path d="m19 15 .8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8zM5 3l.6 1.7L7.3 5.3l-1.7.6L5 7.6l-.6-1.7-1.7-.6 1.7-.6z"/></>,
  BookOpen: <><path d="M12 7v14M3 5.5A2.5 2.5 0 0 1 5.5 3H12v18H5.5A2.5 2.5 0 0 0 3 23z"/><path d="M21 5.5A2.5 2.5 0 0 0 18.5 3H12v18h6.5A2.5 2.5 0 0 1 21 23z"/></>,
  Check: <><path d="m5 12 4.5 4.5L19 7"/></>,
  Copy: <><rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h3"/></>,
  Trash2: <><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 10v6M14 10v6"/></>,
  Edit3: <><path d="m15 5 4 4M4 20l4-.8L19 8a2.8 2.8 0 0 0-4-4L4 15z"/></>,
  MoreHorizontal: <><circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/></>,
  ChevronRight: <><path d="m9 18 6-6-6-6"/></>,
  ChevronDown: <><path d="m6 9 6 6 6-6"/></>,
  PanelLeftClose: <><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16M15 9l-3 3 3 3"/></>,
  PanelLeftOpen: <><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16m6-10 3 3-3 3"/></>,
  LogOut: <><path d="M10 17l5-5-5-5M15 12H3"/><path d="M12 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6"/></>,
  Eye: <><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z"/><circle cx="12" cy="12" r="2.5"/></>,
  EyeOff: <><path d="m3 3 18 18M10.6 6.2A9.7 9.7 0 0 1 12 6c6 0 9.5 6 9.5 6a15.6 15.6 0 0 1-3.1 3.7M6.2 6.3C3.8 8 2.5 12 2.5 12s3.5 6 9.5 6c1.1 0 2.1-.2 3-.6"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/></>,
  AlertCircle: <><circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16.5v.1"/></>,
  X: <><path d="m6 6 12 12M18 6 6 18"/></>,
  ExternalLink: <><path d="M13 5h6v6M19 5l-9 9"/><path d="M17 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h5"/></>,
};

export function Icon({ name, size = 18, strokeWidth = 1.75, className = '', ...props }) {
  if (name === 'BrandLogo') return <DocuMindLogo size={size} className={className} />;
  if (name === 'FileBadgePdf') return <FileTypeLogo fileName="source.pdf" size={size} className={className} />;
  if (name === 'FileBadgeDocx') return <FileTypeLogo fileName="source.docx" size={size} className={className} />;
  return <svg aria-hidden="true" className={`icon ${className}`} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" {...props}>{paths[name] || paths.FileText}</svg>;
}

function safeId(value) { return value.replace(/[^a-zA-Z0-9_-]/g, ''); }

export function DocuMindLogo({ size = 32, className = '' }) {
  const rawId = useId();
  const id = safeId(rawId);
  return <svg aria-hidden="true" className={`brand-logo documind-logo ${className}`} width={size} height={size} viewBox="0 0 32 32" fill="none">
    <defs>
      <linearGradient id={`docu-border-${id}`} x1="1" y1="1" x2="31" y2="31" gradientUnits="userSpaceOnUse"><stop stopColor="#A855F7"/><stop offset="1" stopColor="#6366F1"/></linearGradient>
      <linearGradient id={`docu-prism-${id}`} x1="7" y1="6" x2="26" y2="26" gradientUnits="userSpaceOnUse"><stop stopColor="#C084FC"/><stop offset=".52" stopColor="#8B5CF6"/><stop offset="1" stopColor="#6366F1"/></linearGradient>
      <filter id={`docu-glow-${id}`} x="-35%" y="-35%" width="170%" height="170%"><feGaussianBlur stdDeviation="1.25" result="blur"/><feColorMatrix in="blur" type="matrix" values="0.6 0 0 0 0.45 0 0.35 0 0 0.18 0 0 0.8 0 0.97 0 0 0 .46 0"/><feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>
    </defs>
    <rect x=".5" y=".5" width="31" height="31" rx="9" fill="#120B24" stroke={`url(#docu-border-${id})`}/>
    <g filter={`url(#docu-glow-${id})`} stroke={`url(#docu-prism-${id})`} strokeWidth="1.15" strokeLinejoin="round" strokeLinecap="round">
      <path d="m16 6.7 8 4.55v9.15L16 25l-8-4.6v-9.15z" fill="rgba(139,92,246,.08)"/>
      <path d="m8 11.25 8 4.6 8-4.6M16 15.85V25"/>
      <path d="m12 9 8 4.6v4.55l-4 2.3-4-2.3z" opacity=".76"/>
      <path d="m12 9 4 2.3L20 9" opacity=".76"/>
      <circle cx="16" cy="15.85" r="1.3" fill="#E9D5FF" stroke="none"/>
    </g>
  </svg>;
}

export function BrandLogo({ size = 36, className = '' }) {
  return <DocuMindLogo size={size} className={className} />;
}

export function AssistantAvatarLogo({ size = 28, className = '', animated = false }) {
  const rawId = useId();
  const id = safeId(rawId);
  return <svg aria-hidden="true" className={`assistant-avatar-logo ${animated ? 'is-animated' : ''} ${className}`} width={size} height={size} viewBox="0 0 28 28" fill="none">
    <defs><linearGradient id={`assistant-spark-${id}`} x1="5" y1="4" x2="24" y2="25" gradientUnits="userSpaceOnUse"><stop stopColor="#C084FC"/><stop offset="1" stopColor="#7C3AED"/></linearGradient></defs>
    <rect x=".5" y=".5" width="27" height="27" rx="8" fill="#150D2A" stroke="rgba(168,85,247,.35)"/>
    <g className="assistant-sparkle" fill={`url(#assistant-spark-${id})`}>
      <path d="M14 5.2c.55 4.6 1.3 7.05 6.1 8.8-4.8 1.75-5.55 4.2-6.1 8.8-.55-4.6-1.3-7.05-6.1-8.8 4.8-1.75 5.55-4.2 6.1-8.8Z"/>
      <path d="M21.1 4.2c.23 1.9.55 2.9 2.55 3.62-2 .72-2.32 1.72-2.55 3.62-.23-1.9-.55-2.9-2.55-3.62 2-.72 2.32-1.72 2.55-3.62Z" opacity=".86"/>
      <path d="M6.8 17.3c.18 1.45.42 2.22 1.95 2.77-1.53.55-1.77 1.32-1.95 2.77-.18-1.45-.42-2.22-1.95-2.77 1.53-.55 1.77-1.32 1.95-2.77Z" opacity=".72"/>
    </g>
  </svg>;
}

export function UserAvatarBadge({ identity = '', size = 32, className = '' }) {
  const initial = String(identity || 'U').trim().charAt(0).toUpperCase() || 'U';
  return <span className={`user-avatar-badge ${className}`} style={{ width: size, height: size }} aria-hidden="true">{initial}</span>;
}

export function FileTypeLogo({ fileName = '', size = 36, className = '' }) {
  const extension = String(fileName).split('.').pop()?.toLowerCase();
  const type = extension === 'pdf' ? 'PDF' : extension === 'docx' ? 'DOCX' : extension === 'doc' ? 'DOC' : 'FILE';
  const theme = type === 'PDF' ? 'pdf' : type === 'FILE' ? 'file' : 'docx';
  return <span className={`file-type-logo ${theme} ${className}`} style={{ width: size, height: size }} role="img" aria-label={`${type} file`}>
    <svg aria-hidden="true" width={Math.round(size * .58)} height={Math.round(size * .58)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 2.8h8l4 4v14.4H6z"/><path d="M14 2.8v4h4"/>
      {type === 'PDF' ? <><path d="M8.5 15.5h7M8.5 18h5"/><path d="M8.5 10.5h2a1.5 1.5 0 0 1 0 3h-2z"/></> : <><path d="M8.5 11.5h7M8.5 14.5h7M8.5 17.5h5"/></>}
    </svg>
    <b>{type}</b>
  </span>;
}

export const BrandWordmark = ({ compact = false }) => <span className={`brand-wordmark ${compact ? 'compact' : ''}`}>DOCU MIND<span className="ai-badge">.ai</span></span>;

function namedIcon(name) {
  const Component = props => <Icon name={name} {...props} />;
  Component.displayName = name;
  return Component;
}

export const Folder = namedIcon('Folder');
export const FolderOpen = namedIcon('FolderOpen');
export const MessageSquare = namedIcon('MessageSquare');
export const Plus = namedIcon('Plus');
export const FileText = namedIcon('FileText');
export const FileBadgePdf = props => <FileTypeLogo fileName="source.pdf" {...props} />;
export const FileBadgeDocx = props => <FileTypeLogo fileName="source.docx" {...props} />;
export const UploadCloud = namedIcon('UploadCloud');
export const Search = namedIcon('Search');
export const Send = namedIcon('Send');
export const Sparkles = namedIcon('Sparkles');
export const BookOpen = namedIcon('BookOpen');
export const Check = namedIcon('Check');
export const Copy = namedIcon('Copy');
export const Trash2 = namedIcon('Trash2');
export const Edit3 = namedIcon('Edit3');
export const MoreHorizontal = namedIcon('MoreHorizontal');
export const ChevronRight = namedIcon('ChevronRight');
export const ChevronDown = namedIcon('ChevronDown');
export const PanelLeftClose = namedIcon('PanelLeftClose');
export const PanelLeftOpen = namedIcon('PanelLeftOpen');
export const LogOut = namedIcon('LogOut');
export const Eye = namedIcon('Eye');
export const EyeOff = namedIcon('EyeOff');
export const AlertCircle = namedIcon('AlertCircle');
export const X = namedIcon('X');
export const ExternalLink = namedIcon('ExternalLink');
