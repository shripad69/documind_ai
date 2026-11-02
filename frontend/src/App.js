import React, { useCallback, useEffect, useRef, useState } from 'react';
import api, { getErrorMessage } from './api';
import AuthPage from './components/auth/AuthPage';
import ChatView from './components/chat/ChatView';
import ResourcesPanel from './components/resources/ResourcesPanel';
import Sidebar from './components/layout/Sidebar';
import ConfirmDialog from './components/ui/ConfirmDialog';
import WorkspaceModal from './components/ui/WorkspaceModal';
import Toast from './components/ui/Toast';
import { SidebarSkeleton } from './components/ui/Skeleton';
import { BrandLogo, BrandWordmark, Icon } from './components/ui/Icons';
import './App.css';

const WORKSPACE_STORAGE_KEY = 'documind.activeWorkspace';
const CHAT_STORAGE_KEY = 'documind.activeChat';

function usePath() {
  const [path, setPath] = useState(window.location.pathname);
  useEffect(() => {
    const changed = () => setPath(window.location.pathname);
    window.addEventListener('popstate', changed);
    return () => window.removeEventListener('popstate', changed);
  }, []);
  const navigate = useCallback(next => {
    const current = new URL(window.location.href);
    const target = new URL(next, current.origin);
    if (!target.search && ['/', '/login', '/signup'].includes(target.pathname)) target.search = current.search;
    const destination = `${target.pathname}${target.search}${target.hash}`;
    if (`${window.location.pathname}${window.location.search}${window.location.hash}` !== destination) window.history.pushState({}, '', destination);
    setPath(target.pathname);
  }, []);
  return [path, navigate];
}

function storedSelection() {
  const params = new URLSearchParams(window.location.search);
  return {
    workspace: params.get('workspace') || localStorage.getItem(WORKSPACE_STORAGE_KEY),
    chat: params.get('chat') || localStorage.getItem(CHAT_STORAGE_KEY),
  };
}

export default function App() {
  const [path, navigate] = usePath();
  const [user, setUser] = useState(null);
  const [workspaces, setWorkspaces] = useState([]);
  const [workspace, setWorkspace] = useState(null);
  const [chats, setChats] = useState([]);
  const [chat, setChat] = useState(null);
  const [messages, setMessages] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [resourcesOpen, setResourcesOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingWorkspaces, setLoadingWorkspaces] = useState(false);
  const [loadingChats, setLoadingChats] = useState(false);
  const [workspaceDialog, setWorkspaceDialog] = useState(null);
  const [confirmation, setConfirmation] = useState(null);
  const [toast, setToast] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [composerFocusRequest, setComposerFocusRequest] = useState(0);
  const didInitialize = useRef(false);
  const workspaceRequest = useRef(0);
  const messageRequest = useRef(0);
  const isIndexing = documents.some(document => document.status === 'processing');

  const loadMessages = useCallback(async selected => {
    const requestId = ++messageRequest.current;
    if (!selected) { setMessages([]); return; }
    try {
      const response = await api.get(`/api/chats/${selected.id}/messages`);
      if (requestId === messageRequest.current) setMessages(response.data);
    } catch (error) { if (requestId === messageRequest.current) throw error; }
  }, []);

  const loadWorkspaceData = useCallback(async (selected, preferredChatId = null, requestId) => {
    if (!selected) {
      if (requestId === workspaceRequest.current) { setChats([]); setChat(null); setMessages([]); setDocuments([]); setLoadingChats(false); }
      return null;
    }
    setLoadingChats(true);
    try {
      const [chatResponse, docsResponse] = await Promise.all([
        api.get(`/api/workspaces/${selected.id}/chats`),
        api.get(`/api/workspaces/${selected.id}/documents`),
      ]);
      if (requestId !== workspaceRequest.current) return null;
      const chatEntries = chatResponse.data || [];
      setChats(chatEntries); setDocuments(docsResponse.data || []);
      const preferredChat = chatEntries.find(item => String(item.id) === String(preferredChatId)) || chatEntries[0] || null;
      setChat(preferredChat); return preferredChat;
    } catch (error) {
      if (requestId === workspaceRequest.current) throw error;
      return null;
    } finally { if (requestId === workspaceRequest.current) setLoadingChats(false); }
  }, []);

  const initialize = useCallback(async () => {
    try {
      const selection = storedSelection();
      const meResponse = await api.get('/api/auth/me');
      setUser(meResponse.data);
      setLoadingWorkspaces(true);
      const workspaceResponse = await api.get('/api/workspaces');
      const entries = workspaceResponse.data || [];
      setWorkspaces(entries);
      const selectedWorkspace = entries.find(item => String(item.id) === String(selection.workspace)) || entries[0] || null;
      setWorkspace(selectedWorkspace);
      const requestId = ++workspaceRequest.current;
      ++messageRequest.current;
      if (selectedWorkspace) {
        const selectedChat = await loadWorkspaceData(selectedWorkspace, selection.chat, requestId);
        if (requestId === workspaceRequest.current) await loadMessages(selectedChat);
      } else { await loadWorkspaceData(null, null, requestId); }
    } catch (err) {
      if (err.response?.status === 401) { setUser(null); setWorkspaces([]); setWorkspace(null); setChat(null); setChats([]); setMessages([]); }
      else setToast({ type: 'error', message: getErrorMessage(err) });
    } finally { setLoading(false); setLoadingWorkspaces(false); }
  }, [loadMessages, loadWorkspaceData]);

  useEffect(() => {
    if (didInitialize.current) return;
    didInitialize.current = true;
    initialize();
  }, [initialize]);

  useEffect(() => {
    if (loading) return;
    if (!user && path !== '/login' && path !== '/signup') navigate('/login');
    if (user && (path === '/login' || path === '/signup')) navigate('/');
  }, [loading, user, path, navigate]);

  useEffect(() => {
    const currentUserId = user?.id;
    const activeWorkspaceId = workspace?.id;
    if (!currentUserId || !activeWorkspaceId || !isIndexing) return undefined;
    let active = true;
    let timer;
    const refreshDocuments = async () => {
      try {
        const response = await api.get(`/api/workspaces/${activeWorkspaceId}/documents`);
        if (active) setDocuments(response.data || []);
      } catch (_) { /* retry after the next interval while indexing */ }
      finally { if (active) timer = window.setTimeout(refreshDocuments, 5000); }
    };
    timer = window.setTimeout(refreshDocuments, 5000);
    return () => { active = false; window.clearTimeout(timer); };
  }, [user?.id, workspace?.id, isIndexing]);

  useEffect(() => {
    if (!user) return;
    const url = new URL(window.location.href);
    if (workspace) { localStorage.setItem(WORKSPACE_STORAGE_KEY, workspace.id); url.searchParams.set('workspace', workspace.id); }
    else { localStorage.removeItem(WORKSPACE_STORAGE_KEY); url.searchParams.delete('workspace'); }
    if (chat) { localStorage.setItem(CHAT_STORAGE_KEY, chat.id); url.searchParams.set('chat', chat.id); }
    else { localStorage.removeItem(CHAT_STORAGE_KEY); url.searchParams.delete('chat'); }
    window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`);
  }, [user, workspace, chat]);

  async function selectWorkspace(selected) {
    const requestId = ++workspaceRequest.current;
    ++messageRequest.current;
    setWorkspace(selected); setChat(null); setMessages([]); setDocuments([]); setToast(null);
    try { const selectedChat = await loadWorkspaceData(selected, null, requestId); if (requestId === workspaceRequest.current) await loadMessages(selectedChat); }
    catch (err) { setToast({ type: 'error', message: getErrorMessage(err) }); }
  }
  async function selectChat(selected) {
    setChat(selected); setMessages([]); setToast(null);
    try { await loadMessages(selected); } catch (err) { setToast({ type: 'error', message: getErrorMessage(err) }); }
  }
  async function saveWorkspace(title) {
    const selected = workspaceDialog?.workspace;
    try {
      if (selected) {
        const response = await api.patch(`/api/workspaces/${selected.id}`, { title });
        setWorkspaces(current => current.map(item => item.id === selected.id ? response.data : item));
        if (workspace?.id === selected.id) setWorkspace(response.data);
      } else {
        const response = await api.post('/api/workspaces', { title, description: '' });
        ++workspaceRequest.current; ++messageRequest.current; setLoadingChats(false);
        setWorkspaces(current => [response.data, ...current]); setWorkspace(response.data); setChats([]); setChat(null); setMessages([]); setDocuments([]);
      }
    } catch (err) { throw new Error(getErrorMessage(err)); }
  }
  function requestDeleteWorkspace(selected) {
    setConfirmation({ kind: 'workspace', item: selected });
  }
  function requestDeleteDocument(doc) {
    setConfirmation({ kind: 'document', item: doc });
  }
  async function confirmDelete() {
    const current = confirmation;
    if (!current) return;
    try {
      if (current.kind === 'workspace') {
        await api.delete(`/api/workspaces/${current.item.id}`);
        const next = workspaces.filter(item => item.id !== current.item.id);
        setWorkspaces(next); setConfirmation(null);
        if (workspace?.id === current.item.id) {
          const requestId = ++workspaceRequest.current;
          ++messageRequest.current;
          setWorkspace(next[0] || null); setChat(null); setChats([]); setMessages([]); setDocuments([]);
          if (!next[0]) setLoadingChats(false);
          if (next[0]) { const selectedChat = await loadWorkspaceData(next[0], null, requestId); if (requestId === workspaceRequest.current) await loadMessages(selectedChat); }
        }
        setToast({ type: 'success', message: 'Workspace deleted.' });
      } else {
        await api.delete(`/api/workspaces/${workspace.id}/documents/${current.item.id}`);
        setConfirmation(null);
        const response = await api.get(`/api/workspaces/${workspace.id}/documents`); setDocuments(response.data || []);
        setToast({ type: 'success', message: 'Document deleted.' });
      }
    } catch (err) { setConfirmation(null); setToast({ type: 'error', message: getErrorMessage(err) }); }
  }
  async function createChat() {
    if (!workspace) { setToast({ type: 'error', message: 'Create a workspace before starting a chat.' }); return; }
    try {
      const response = await api.post(`/api/workspaces/${workspace.id}/chats`, { title: 'New chat' });
      setChats(current => [response.data, ...current]); setChat(response.data); setMessages([]); setToast(null); setMobileSidebarOpen(false); setComposerFocusRequest(request => request + 1);
    } catch (err) { setToast({ type: 'error', message: getErrorMessage(err) }); }
  }
  function goToLatestChat() {
    if (chats.length) selectChat(chats[0]);
    else { setChat(null); setMessages([]); setToast(null); }
  }
  async function copyChatLink(selected) {
    const url = new URL(window.location.href);
    if (workspace) url.searchParams.set('workspace', workspace.id);
    if (selected) url.searchParams.set('chat', selected.id);
    try { await navigator.clipboard.writeText(url.toString()); setToast({ type: 'success', message: 'Chat link copied.' }); }
    catch (_) { setToast({ type: 'error', message: 'Could not copy the chat link.' }); }
  }
  async function logout() {
    try { await api.post('/api/auth/logout'); } catch (_) { /* clear local state even when the session is already expired */ }
    ++workspaceRequest.current; ++messageRequest.current; setLoadingChats(false);
    localStorage.removeItem(WORKSPACE_STORAGE_KEY); localStorage.removeItem(CHAT_STORAGE_KEY);
    const cleanUrl = new URL(window.location.href);
    cleanUrl.searchParams.delete('workspace'); cleanUrl.searchParams.delete('chat');
    window.history.replaceState({}, '', `${cleanUrl.pathname}${cleanUrl.search}${cleanUrl.hash}`);
    setUser(null); setWorkspaces([]); setWorkspace(null); setChats([]); setChat(null); setMessages([]); setDocuments([]); setResourcesOpen(false); navigate('/login');
  }
  async function authenticated() { setLoading(true); setToast(null); await initialize(); }

  if (loading) return <div className="loading-screen"><aside className="loading-sidebar"><div className="loading-sidebar-brand"><BrandLogo size={30} /><BrandWordmark /></div><div className="section-heading"><span>WORKSPACES</span></div><SidebarSkeleton rows={3} /><div className="section-heading loading-chat-label"><span>CHATS</span></div><SidebarSkeleton rows={4} /></aside><main className="loading-main"><div className="loading-brand"><BrandLogo size={39} /><BrandWordmark /></div><span>Opening your workspace…</span><i className="loading-line" /></main></div>;
  if (!user) return <AuthPage mode={path === '/signup' ? 'signup' : 'login'} navigate={navigate} onAuthenticated={authenticated} initialError={toast?.type === 'error' ? toast.message : ''} />;

  return <div className="app-shell">
    <Sidebar user={user} workspaces={workspaces} activeWorkspace={workspace} chats={chats} activeChat={chat} documents={documents} loadingWorkspaces={loadingWorkspaces} loadingChats={loadingChats}
      collapsed={sidebarCollapsed} mobileOpen={mobileSidebarOpen} onToggleCollapse={() => setSidebarCollapsed(true)} onMobileClose={() => setMobileSidebarOpen(false)}
      onWorkspace={selectWorkspace} onCreateWorkspace={() => setWorkspaceDialog({ mode: 'create' })} onRenameWorkspace={selected => setWorkspaceDialog({ mode: 'rename', workspace: selected })} onDeleteWorkspace={requestDeleteWorkspace}
      onResources={() => setResourcesOpen(true)} onCreateChat={createChat} onChat={selectChat} onLogout={logout} onBrandHome={goToLatestChat} onCopyChatLink={copyChatLink} />
    {sidebarCollapsed && <button className="sidebar-reopen" onClick={() => setSidebarCollapsed(false)} aria-label="Open sidebar" title="Open sidebar"><Icon name="PanelLeftOpen" /></button>}
    <div className={`main-column ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
      {workspace ? <ChatView workspace={workspace} chat={chat} messages={messages} setMessages={setMessages} documents={documents} user={user} onResources={() => setResourcesOpen(true)} onToggleResources={() => setResourcesOpen(value => !value)} onCreateChat={createChat} focusComposerRequest={composerFocusRequest}
        onToggleSidebar={() => { if (window.matchMedia('(max-width: 768px)').matches) setMobileSidebarOpen(true); else setSidebarCollapsed(false); }}
        onChatUpdated={async () => { try { const response = await api.get(`/api/workspaces/${workspace.id}/chats`); setChats(response.data || []); const updated = response.data.find(item => item.id === chat?.id); if (updated) setChat(updated); } catch (_) { /* the next navigation will reload the chat list */ } }} />
        : <div className="no-workspace"><div className="no-workspace-logo"><BrandLogo size={47} /></div><p className="eyebrow">A PRIVATE KNOWLEDGE SPACE</p><h1>Make room for better questions.</h1><p>Create a workspace to bring documents and conversations together.</p><button className="primary-button" onClick={() => setWorkspaceDialog({ mode: 'create' })}><Icon name="Plus" size={16} />Create a workspace</button></div>}
    </div>
    <ResourcesPanel open={resourcesOpen} workspace={workspace} documents={documents} refresh={async () => { if (!workspace) return; const response = await api.get(`/api/workspaces/${workspace.id}/documents`); setDocuments(response.data || []); }} onClose={() => setResourcesOpen(false)} onDeleteDocument={requestDeleteDocument} />
    <WorkspaceModal open={Boolean(workspaceDialog)} workspace={workspaceDialog?.workspace} onClose={() => setWorkspaceDialog(null)} onSave={saveWorkspace} />
    <ConfirmDialog open={Boolean(confirmation)} title={confirmation?.kind === 'workspace' ? 'Delete workspace?' : 'Delete document?'} itemName={confirmation?.item?.title || confirmation?.item?.file_name}
      description={confirmation?.kind === 'workspace' ? 'Deleting this workspace permanently removes all associated documents, embeddings, and chat threads.' : 'This document will be permanently removed from the workspace and excluded from future answers.'}
      onCancel={() => setConfirmation(null)} onConfirm={confirmDelete} />
    <Toast toast={toast} onDismiss={() => setToast(null)} />
  </div>;
}
