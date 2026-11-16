import React, { useMemo, useState } from 'react';
import { BrandLogo, BrandWordmark, Icon, UserAvatarBadge } from '../ui/Icons';
import { SidebarSkeleton } from '../ui/Skeleton';

export default function Sidebar({
  user,
  workspaces = [],
  activeWorkspace,
  chats = [],
  activeChat,
  documents = [],
  loadingWorkspaces = false,
  loadingChats = false,
  collapsed = false,
  mobileOpen = false,
  onToggleCollapse,
  onMobileClose,
  onWorkspace,
  onCreateWorkspace,
  onRenameWorkspace,
  onDeleteWorkspace,
  onResources,
  onCreateChat,
  onChat,
  onLogout,
  onBrandHome,
  onCopyChatLink,
  onDeleteChat,
}) {
  const [filter, setFilter] = useState('');
  const filteredChats = useMemo(
    () =>
      chats.filter(chat =>
        (chat.title || '').toLowerCase().includes(filter.toLowerCase())
      ),
    [chats, filter]
  );
  const readyCount = documents.filter(doc => doc.status === 'indexed').length;
  const indexing = documents.some(
    doc => doc.status !== 'indexed' && doc.status !== 'failed'
  );

  const chooseWorkspace = workspace => {
    onWorkspace(workspace);
    onMobileClose?.();
  };
  const chooseChat = chat => {
    onChat(chat);
    onMobileClose?.();
  };

  return (
    <>
      {mobileOpen && (
        <button
          className="drawer-backdrop sidebar-backdrop"
          aria-label="Close navigation"
          onClick={onMobileClose}
        />
      )}
      <aside
        className={`sidebar ${collapsed ? 'is-collapsed' : ''} ${
          mobileOpen ? 'mobile-open' : ''
        }`}
        aria-label="Workspace navigation"
      >
        <div className="sidebar-top">
          <button
            className="sidebar-brand"
            onClick={() => {
              onBrandHome?.();
              onMobileClose?.();
            }}
            aria-label="DocuMind home"
            title="Go to latest chat"
          >
            <BrandLogo size={30} />
            <BrandWordmark />
          </button>
          <button
            className="sidebar-toggle"
            onClick={onToggleCollapse}
            aria-label="Collapse sidebar"
            title="Collapse sidebar"
          >
            <Icon name="PanelLeftClose" size={17} />
          </button>
          <button
            className="mobile-close icon-button"
            onClick={onMobileClose}
            aria-label="Close navigation"
          >
            <Icon name="X" size={18} />
          </button>
        </div>
        <div className="sidebar-scroll">
          <div className="section-heading">
            <span>Workspaces</span>
            <span className="count-badge">{workspaces.length}</span>
            <button
              className="section-add"
              onClick={onCreateWorkspace}
              title="Create workspace"
              aria-label="Create workspace"
            >
              <Icon name="Plus" size={15} />
            </button>
          </div>
          {loadingWorkspaces ? (
            <SidebarSkeleton rows={3} />
          ) : (
            <div className="workspace-list">
              {workspaces.map(workspace => (
                <div
                  key={workspace.id}
                  className={`workspace-row ${
                    activeWorkspace?.id === workspace.id ? 'selected' : ''
                  }`}
                >
                  <button
                    className="workspace-select"
                    onClick={() => chooseWorkspace(workspace)}
                    aria-label={`Open workspace ${workspace.title}`}
                  >
                    <Icon
                      name={
                        activeWorkspace?.id === workspace.id ? 'FolderOpen' : 'Folder'
                      }
                      size={16}
                    />
                    <span className="workspace-title">{workspace.title}</span>
                  </button>
                  <div className="workspace-actions">
                    <button
                      onClick={() => onRenameWorkspace(workspace)}
                      title="Rename workspace"
                      aria-label={`Rename ${workspace.title}`}
                    >
                      <Icon name="Edit3" size={13} />
                    </button>
                    <button
                      onClick={() => onDeleteWorkspace(workspace)}
                      title="Delete workspace"
                      aria-label={`Delete ${workspace.title}`}
                    >
                      <Icon name="Trash2" size={13} />
                    </button>
                  </div>
                </div>
              ))}
              {!workspaces.length && (
                <div className="sidebar-empty">Create a workspace to begin.</div>
              )}
            </div>
          )}
          {activeWorkspace && (
            <>
              <div className="sidebar-divider" />
              <div className="active-context">
                <span className="context-label">Active Workspace</span>
                <strong title={activeWorkspace.title}>{activeWorkspace.title}</strong>
                <button
                  className="resource-link"
                  onClick={() => {
                    onResources();
                    onMobileClose?.();
                  }}
                  title="Open workspace resources"
                  aria-label={`Open resources, ${readyCount} indexed documents`}
                >
                  <span className="resource-link-icon">
                    <Icon name="BookOpen" size={15} />
                  </span>
                  <span>Resources</span>
                  <span className="resource-count">{readyCount} docs</span>
                  {indexing && (
                    <i className="indexing-dot" title="Documents indexing in background" />
                  )}
                </button>
              </div>
              <div className="chat-section-heading">
                <div className="section-heading chat-section-title">
                  <span>Chats</span>
                  <span className="count-badge">{chats.length}</span>
                  <button
                    className="section-add"
                    onClick={onCreateChat}
                    title="New chat"
                    aria-label="New chat"
                  >
                    <Icon name="Plus" size={15} />
                  </button>
                </div>
                {chats.length > 3 && (
                  <label className="chat-filter">
                    <Icon name="Search" size={14} />
                    <input
                      value={filter}
                      onChange={event => setFilter(event.target.value)}
                      placeholder="Filter conversations…"
                      aria-label="Filter conversations"
                    />
                    {filter && (
                      <button onClick={() => setFilter('')} aria-label="Clear filter">
                        <Icon name="X" size={12} />
                      </button>
                    )}
                  </label>
                )}
              </div>
              <div className="chat-list">
                {loadingChats ? (
                  <SidebarSkeleton rows={4} />
                ) : (
                  filteredChats.map(chat => (
                    <div
                      key={chat.id}
                      className={`chat-row ${activeChat?.id === chat.id ? 'active' : ''}`}
                    >
                      <button
                        className="chat-link"
                        onClick={() => chooseChat(chat)}
                        title={chat.title}
                        aria-label={`Open chat ${chat.title || 'New chat'}`}
                      >
                        <Icon name="MessageSquare" size={15} />
                        <span>{chat.title || 'New chat'}</span>
                      </button>
                      <button
                        className="chat-copy-link"
                        onClick={event => {
                          event.stopPropagation();
                          onCopyChatLink?.(chat);
                        }}
                        title="Copy chat link"
                        aria-label={`Copy link to ${chat.title || 'New chat'}`}
                      >
                        <Icon name="Copy" size={12} />
                      </button>
                      <button
                        className="chat-delete"
                        onClick={event => {
                          event.stopPropagation();
                          onDeleteChat?.(chat);
                        }}
                        title="Delete chat"
                        aria-label={`Delete ${chat.title || 'New chat'}`}
                      >
                        <Icon name="Trash2" size={12} />
                      </button>
                    </div>
                  ))
                )}
                {!loadingChats && chats.length > 0 && !filteredChats.length && (
                  <div className="sidebar-empty">No chats match “{filter}”.</div>
                )}
                {!loadingChats && !chats.length && (
                  <div className="sidebar-empty">No conversations yet.</div>
                )}
              </div>
              <button
                className="new-chat-button"
                onClick={onCreateChat}
                title="Create a new conversation"
                aria-label="Create a new conversation"
              >
                <Icon name="Plus" size={15} />
                New chat
              </button>
            </>
          )}
        </div>
        <footer className="sidebar-footer">
          <div className="profile-avatar">
            <UserAvatarBadge identity={user?.email || 'U'} size={32} />
            <i />
          </div>
          <div className="profile-details">
            <span title={user?.email}>{user?.email}</span>
            <small>
              <i /> Connected
            </small>
          </div>
          <button
            className="logout-button"
            onClick={onLogout}
            title="Log out"
            aria-label="Log out"
          >
            <Icon name="LogOut" size={16} />
          </button>
        </footer>
      </aside>
    </>
  );
}
