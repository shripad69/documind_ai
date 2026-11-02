import React, { useMemo, useState } from 'react';
import { BrandLogo, BrandWordmark, Icon, UserAvatarBadge } from '../ui/Icons';
import { SidebarSkeleton } from '../ui/Skeleton';

export default function Sidebar({ user, workspaces = [], activeWorkspace, chats = [], activeChat, documents = [], loadingWorkspaces = false, loadingChats = false, collapsed = false, mobileOpen = false, onToggleCollapse, onMobileClose, onWorkspace, onCreateWorkspace, onRenameWorkspace, onDeleteWorkspace, onResources, onCreateChat, onChat, onLogout, onBrandHome, onCopyChatLink }) {
  const [filter, setFilter] = useState('');
  const filteredChats = useMemo(() => chats.filter(chat => (chat.title || '').toLowerCase().includes(filter.toLowerCase())), [chats, filter]);
  const readyCount = documents.filter(doc => doc.status === 'indexed').length;
  const indexing = documents.some(doc => doc.status !== 'indexed' && doc.status !== 'failed');
  const chooseWorkspace = workspace => { onWorkspace(workspace); onMobileClose?.(); };
  const chooseChat = chat => { onChat(chat); onMobileClose?.(); };
  return <>
    {mobileOpen && <button className="drawer-backdrop sidebar-backdrop" aria-label="Close navigation" onClick={onMobileClose} />}
    <aside className={`sidebar ${collapsed ? 'is-collapsed' : ''} ${mobileOpen ? 'mobile-open' : ''}`} aria-label="Workspace navigation">
      <div className="sidebar-top"><button className="sidebar-brand" onClick={() => { onBrandHome?.(); onMobileClose?.(); }} aria-label="DOCU MIND.ai home" title="Go to the latest chat"><BrandLogo size={31} /><BrandWordmark /></button><button className="sidebar-toggle" onClick={onToggleCollapse} aria-label="Collapse sidebar" title="Collapse sidebar"><Icon name="PanelLeftClose" /></button><button className="mobile-close icon-button" onClick={onMobileClose} aria-label="Close navigation"><Icon name="X" /></button></div>
      <div className="sidebar-scroll">
        <div className="section-heading"><span>WORKSPACES</span><span className="count-badge">{workspaces.length}</span><button className="section-add" onClick={onCreateWorkspace} title="Create workspace" aria-label="Create workspace"><Icon name="Plus" size={16} /></button></div>
        {loadingWorkspaces ? <SidebarSkeleton rows={3} /> : <div className="workspace-list">
          {workspaces.map(workspace => <div key={workspace.id} className={`workspace-row ${activeWorkspace?.id === workspace.id ? 'selected' : ''}`}>
            <button className="workspace-select" onClick={() => chooseWorkspace(workspace)} aria-label={`Open workspace ${workspace.title}`}><Icon name={activeWorkspace?.id === workspace.id ? 'FolderOpen' : 'Folder'} size={17} /><span className="workspace-title">{workspace.title}</span></button>
            <div className="workspace-actions"><button onClick={() => onRenameWorkspace(workspace)} title="Rename workspace" aria-label={`Rename ${workspace.title}`}><Icon name="Edit3" size={14} /></button><button onClick={() => onDeleteWorkspace(workspace)} title="Delete workspace" aria-label={`Delete ${workspace.title}`}><Icon name="Trash2" size={14} /></button></div>
          </div>)}
          {!workspaces.length && <div className="sidebar-empty">Create a workspace to start your library.</div>}
        </div>}
        {activeWorkspace && <>
          <div className="sidebar-divider" />
          <div className="active-context"><span className="context-label">ACTIVE WORKSPACE</span><strong title={activeWorkspace.title}>{activeWorkspace.title}</strong>
            <button className="resource-link" onClick={() => { onResources(); onMobileClose?.(); }} title="Open workspace resources" aria-label={`Open resources, ${readyCount} indexed documents`}><span className="resource-link-icon"><Icon name="BookOpen" size={16} /></span><span>Resources</span><span className="resource-count">{readyCount} docs</span>{indexing && <i className="indexing-dot" title="Documents indexing" />}</button>
          </div>
          <div className="chat-section-heading"><div className="section-heading chat-section-title"><span>CHATS</span><span className="count-badge">{chats.length}</span><button className="section-add" onClick={onCreateChat} title="New chat" aria-label="New chat"><Icon name="Plus" size={16} /></button></div>
            {chats.length > 3 && <label className="chat-filter"><Icon name="Search" size={15} /><input value={filter} onChange={event => setFilter(event.target.value)} placeholder="Filter chats…" aria-label="Filter chats" />{filter && <button onClick={() => setFilter('')} aria-label="Clear filter"><Icon name="X" size={13} /></button>}</label>}
          </div>
          <div className="chat-list">
            {loadingChats ? <SidebarSkeleton rows={4} /> : filteredChats.map(chat => <div key={chat.id} className={`chat-row ${activeChat?.id === chat.id ? 'active' : ''}`}><button className="chat-link" onClick={() => chooseChat(chat)} title={chat.title} aria-label={`Open chat ${chat.title || 'New chat'}`}><Icon name="MessageSquare" size={16} /><span>{chat.title || 'New chat'}</span></button><button className="chat-copy-link" onClick={event => { event.stopPropagation(); onCopyChatLink?.(chat); }} title="Copy chat link" aria-label={`Copy link to ${chat.title || 'New chat'}`}><Icon name="Copy" size={13} /></button></div>)}
            {!loadingChats && chats.length > 0 && !filteredChats.length && <div className="sidebar-empty">No chats match “{filter}”.</div>}
            {!loadingChats && !chats.length && <div className="sidebar-empty">No conversations yet.</div>}
          </div>
          <button className="new-chat-button" onClick={onCreateChat} title="Create a new chat" aria-label="Create a new chat"><Icon name="Plus" size={16} />New chat</button>
        </>}
      </div>
      <footer className="sidebar-footer"><div className="profile-avatar"><UserAvatarBadge identity={user?.email || 'U'} size={32} /><i /></div><div className="profile-details"><span title={user?.email}>{user?.email}</span><small><i /> Online</small></div><button className="logout-button" onClick={onLogout} title="Log out" aria-label="Log out"><Icon name="LogOut" size={17} /></button></footer>
    </aside>
  </>;
}
