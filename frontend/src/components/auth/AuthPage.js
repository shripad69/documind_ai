import React, { useEffect, useState } from 'react';
import api, { getErrorMessage } from '../../api';
import { BrandLogo, BrandWordmark, Icon } from '../ui/Icons';

export default function AuthPage({ mode, onAuthenticated, navigate, initialError = '' }) {
  const signup = mode === 'signup';
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { setError(initialError); }, [initialError, mode]);
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      await api.post(`/api/auth/${signup ? 'register' : 'login'}`, { email, password });
      await onAuthenticated(); navigate('/');
    } catch (err) { setError(getErrorMessage(err)); }
    finally { setBusy(false); }
  }
  return <main className="auth-page"><div className="auth-ambient" /><div className="auth-grid" />
    <div className="auth-layout"><div className="auth-story"><div className="auth-brand"><BrandLogo size={42} /><BrandWordmark /></div><span className="auth-story-kicker"><i /> PRIVATE DOCUMENT INTELLIGENCE</span><h1>Your knowledge,<br /><em>in context.</em></h1><p>Ask better questions. Find the source. Move forward with confidence.</p><div className="auth-proof"><div className="proof-orb"><Icon name="Sparkles" size={19} /></div><span>Grounded answers<br /><b>anchored to your documents</b></span></div></div>
      <form className="auth-card" onSubmit={submit}>
        <div className="auth-card-top"><BrandLogo size={38} /><span>SECURE WORKSPACE</span></div>
        <div className="auth-tabs"><button type="button" className={!signup ? 'active' : ''} onClick={() => navigate('/login')}>Sign in</button><button type="button" className={signup ? 'active' : ''} onClick={() => navigate('/signup')}>Create account</button></div>
        <h2>{signup ? 'Create your account' : 'Welcome back'}</h2><p className="auth-subtitle">{signup ? 'Start building a private space for your knowledge.' : 'Sign in to continue to your workspace.'}</p>
        <label className="auth-field">Email address<input type="email" autoComplete="email" required value={email} onChange={event => setEmail(event.target.value)} placeholder="you@company.com" /></label>
        <label className="auth-field">Password<div className="password-wrap"><input type={showPassword ? 'text' : 'password'} autoComplete={signup ? 'new-password' : 'current-password'} minLength={signup ? 10 : undefined} required value={password} onChange={event => setPassword(event.target.value)} placeholder={signup ? 'Create a secure password' : 'Enter your password'} /><button type="button" onClick={() => setShowPassword(value => !value)} aria-label={showPassword ? 'Hide password' : 'Show password'}><Icon name={showPassword ? 'EyeOff' : 'Eye'} size={17} /></button></div>{signup ? <span className={`password-hint ${password.length >= 10 ? 'valid' : ''}`}>{password.length >= 10 ? <Icon name="Check" size={13} /> : null}{password.length}/10 characters · Min 10 characters</span> : null}</label>
        {error && <div className="auth-error"><Icon name="AlertCircle" size={16} /><span>{error}</span></div>}
        <button className="auth-submit primary-button" disabled={busy}>{busy && <span className="spinner" />}{busy ? 'Authenticating…' : signup ? 'Create account' : 'Sign in'}<Icon name="ChevronRight" size={17} /></button>
        <div className="auth-security"><Icon name="Check" size={13} /> Your documents stay private and secure.</div>
      </form>
    </div>
    <footer className="auth-footer"><span>DOCU MIND.ai</span><span>Grounded document intelligence</span></footer>
  </main>;
}
