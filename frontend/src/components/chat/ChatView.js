import React, { useEffect, useRef, useState } from 'react';
import api, { getErrorMessage } from '../../api';
import { AssistantAvatarLogo, BrandLogo, BrandWordmark, Icon } from '../ui/Icons';
import MessageItem from './MessageItem';

const starterPrompts = [
  'Summarize the key findings and methodology',
  'Extract core metrics, dates, and quantitative changes',
  'Compare conclusions across uploaded documents',
];
const thinkingStages = ['Searching vector index…', 'Retrieving relevant document chunks…', 'Synthesizing grounded answer…'];

function ThinkingCard() {
  const [stage, setStage] = useState(0);
  useEffect(() => { const timer = window.setInterval(() => setStage(value => (value + 1) % thinkingStages.length), 2300); return () => window.clearInterval(timer); }, []);
  return <div className="thinking-card"><div className="thinking-mark"><AssistantAvatarLogo size={30} animated /></div><div><strong>Working through your sources</strong><span key={stage}>{thinkingStages[stage]}</span></div><div className="thinking-bars"><i /><i /><i /></div></div>;
}

export default function ChatView({ workspace, chat, messages, setMessages, documents = [], user, onResources, onToggleResources, onChatUpdated, onCreateChat, onToggleSidebar, focusComposerRequest = 0 }) {
  const [text, setText] = useState('');
  const [sendingChatId, setSendingChatId] = useState(null);
  const [error, setError] = useState('');
  const endRef = useRef(null);
  const textareaRef = useRef(null);
  const activeChatId = useRef(chat?.id);
  activeChatId.current = chat?.id;
  const sending = Boolean(chat?.id && sendingChatId === chat.id);
  const readyCount = documents.filter(doc => doc.status === 'indexed').length;
  const indexingCount = documents.filter(doc => doc.status !== 'indexed' && doc.status !== 'failed').length;
  const activeCount = documents.length;
  const empty = messages.length === 0;
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [messages, sending]);
  useEffect(() => { setText(''); setError(''); }, [chat?.id]);
  useEffect(() => { if (focusComposerRequest) textareaRef.current?.focus(); }, [focusComposerRequest]);
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto'; textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
  }, [text]);

  async function send(event, suppliedText) {
    event?.preventDefault();
    const content = (suppliedText ?? text).trim();
    if (!content || sending || !chat) return;
    const requestChatId = chat.id;
    setText(''); setError(''); setSendingChatId(requestChatId);
    setMessages(current => [...current, { id: `pending-${Date.now()}`, role: 'user', content, source_references: [] }]);
    try {
      const response = await api.post(`/api/chats/${chat.id}/messages`, { content });
      if (activeChatId.current === requestChatId) {
        setMessages(current => [...current.filter(message => !String(message.id).startsWith('pending-')), response.data.user_message, response.data.assistant_message]);
        onChatUpdated?.();
      }
    } catch (err) {
      if (activeChatId.current === requestChatId) {
        setError(getErrorMessage(err)); setMessages(current => current.filter(message => !String(message.id).startsWith('pending-'))); setText(content);
      }
    } finally { setSendingChatId(current => current === requestChatId ? null : current); }
  }
  return <main className="chat-main">
    <header className="chat-header"><div className="chat-header-left"><button className="header-menu-button" onClick={onToggleSidebar} aria-label="Open navigation" title="Open navigation"><Icon name="PanelLeftOpen" size={18} /></button><div className="crumb"><button className="crumb-workspace" onClick={onResources} title={`Open resources for ${workspace?.title || 'workspace'}`}><Icon name="Folder" size={15} />{workspace?.title || 'Workspace'}</button><Icon name="ChevronRight" size={14} /><strong title={chat?.title || 'New chat'}>{chat?.title || 'New chat'}</strong></div></div><div className="header-actions"><button className={`grounding-status ${indexingCount ? 'indexing' : ''}`} onClick={onResources} title="Open workspace document status" aria-label={indexingCount ? `${indexingCount} documents indexing. Open resources` : `${readyCount} documents ready. Open resources`}><i />{indexingCount ? `${indexingCount} Indexing…` : `${readyCount} Ready`}</button><button className="header-resource-button" onClick={onToggleResources || onResources} title="Toggle resources" aria-label={`Toggle resources, ${activeCount} documents`}><Icon name="BookOpen" size={16} /><span>Resources</span><b>{activeCount}</b></button></div></header>
    <section className={`conversation ${empty ? 'empty-conversation' : ''}`}>
      {empty && <div className="welcome"><div className="welcome-logo"><BrandLogo size={53} /></div><BrandWordmark /><p className="eyebrow">GROUNDED RAG WORKSPACE</p><h1>Ask anything across your<br className="desktop-break" /> workspace documents</h1><p className="welcome-description">Your documents, connected to answers you can verify.</p>
        {!activeCount ? <div className="welcome-callout"><div className="callout-icon"><Icon name="UploadCloud" size={19} /></div><div><strong>Your knowledge base is ready</strong><span>Add documents to get grounded answers with verifiable sources.</span></div><button className="primary-button" onClick={onResources}><Icon name="Plus" size={16} />Upload Documents to Get Started</button></div>
          : !chat ? <div className="welcome-callout"><div className="callout-icon"><Icon name="MessageSquare" size={19} /></div><div><strong>Start a conversation</strong><span>{readyCount ? `${readyCount} indexed documents are ready to explore.` : 'Your documents are being indexed.'}</span></div><button className="primary-button" onClick={onCreateChat}><Icon name="Plus" size={16} />New chat</button></div>
          : readyCount > 0 ? <div className="starter-prompts">{starterPrompts.map((prompt, index) => <button key={prompt} className="starter-card" onClick={() => send(undefined, prompt)} title={`Ask: ${prompt}`} aria-label={`Submit starter prompt: ${prompt}`}><span className={`starter-icon icon-${index}`}><Icon name={index === 0 ? 'BookOpen' : index === 1 ? 'Search' : 'Sparkles'} size={17} /></span><span>{prompt}</span><Icon className="starter-arrow" name="ChevronRight" size={16} /></button>)}</div>
            : <div className="indexing-note"><span className="mini-spinner" />Documents are indexing. You can start asking as soon as they’re ready.</div>}
      </div>}
      <div className="message-stack">{messages.map(message => <MessageItem key={message.id} message={message} user={user} onOpenResources={onResources} />)}</div>
      {sending && <div className="message-stack"><ThinkingCard /></div>}
      {error && <div className="chat-inline-error"><Icon name="AlertCircle" size={16} />{error}</div>}
      <div ref={endRef} />
    </section>
    <form className="composer-area" onSubmit={send}><div className="composer"><textarea ref={textareaRef} value={text} onChange={event => setText(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); send(); } }} placeholder={chat ? 'Ask a question about your documents…' : 'Create a chat to start asking questions…'} rows="1" disabled={!chat || sending} aria-label="Message composer" />
      <div className="composer-toolbar"><div className="composer-tools"><button type="button" onClick={onResources} title="Open resources to attach or manage documents"><Icon name="Plus" size={15} /><span>Attach / Manage Docs</span></button><button type="button" className="composer-doc-count" onClick={onResources} title={`Open ${activeCount} workspace documents`} aria-label={`Open ${activeCount} workspace documents`}><Icon name="FileText" size={13} />{activeCount}</button></div><div className="composer-submit-area"><span className="keyboard-hint">Enter ↵ to send · Shift + Enter for new line</span><button className="send-button" type="submit" disabled={!text.trim() || sending || !chat} title="Send message" aria-label="Send message">{sending ? <span className="spinner" /> : <Icon name="Send" size={17} />}</button></div></div>
    </div><p className="grounding-disclaimer">Responses are grounded in workspace documents. Click any citation to inspect the source passage.</p></form>
  </main>;
}
