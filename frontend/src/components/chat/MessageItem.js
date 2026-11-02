import React, { useState } from 'react';
import { AssistantAvatarLogo, BrandWordmark, Icon, UserAvatarBadge } from '../ui/Icons';
import MarkdownRenderer from './MarkdownRenderer';
import SourceCards from './SourceCards';

function normalizedCitations(content = '', references = []) {
  return String(content).replace(/\[(chunk|citation)_[^\]]+\]/gi, tag => {
    const value = tag.slice(1, -1);
    let index = references.findIndex(ref => String(ref?.chunk_id || '').toLowerCase() === value.toLowerCase() || String(ref?.citation_id || '').toLowerCase() === value.toLowerCase());
    if (index < 0) {
      const match = value.match(/_(\d+)$/);
      if (match) index = Number(match[1]) - 1;
    }
    return `[${index >= 0 ? index + 1 : 1}]`;
  });
}

export default function MessageItem({ message, user, onOpenResources }) {
  const [copied, setCopied] = useState(false);
  const [inspected, setInspected] = useState(null);
  const [hoveredReference, setHoveredReference] = useState(null);
  const assistant = message.role === 'assistant';
  async function copy() {
    try {
      await navigator.clipboard.writeText(normalizedCitations(message.content || '', message.source_references || []));
      setCopied(true); window.setTimeout(() => setCopied(false), 2000);
    } catch (_) { setCopied(false); }
  }
  return <article className={`message-row ${assistant ? 'assistant-message' : 'user-message'}`}>
    {assistant ? <div className="assistant-avatar"><AssistantAvatarLogo size={30} /></div> : <UserAvatarBadge className="user-avatar" identity={user?.email || 'Y'} size={29} />}
    <div className="message-content-wrap">
      <header className="message-heading"><span>{assistant ? <BrandWordmark compact /> : 'You'}</span>{assistant && <button className={`copy-response ${copied ? 'copied' : ''}`} onClick={copy} title={copied ? 'Response copied' : 'Copy response'} aria-label={copied ? 'Response copied' : 'Copy response'}><Icon name={copied ? 'Check' : 'Copy'} size={14} />{copied ? 'Copied!' : 'Copy response'}</button>}</header>
      <MarkdownRenderer content={message.content} sourceReferences={message.source_references || []} onCitation={(source, index) => { setInspected({ source, index }); setHoveredReference(source); }} onCitationHover={setHoveredReference} />
      {assistant && <SourceCards references={message.source_references || []} selected={inspected} highlightedReference={hoveredReference} onInspect={(source, index) => setInspected({ source, index })} onDismiss={() => setInspected(null)} onOpenResources={onOpenResources} />}
    </div>
  </article>;
}
