import { ArrowRight, KeyRound, LoaderCircle, Lock, Mail, ShieldCheck, UserRound } from 'lucide-react';
import { FormEvent, useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  acceptAuthRedirect, changeAccountPassword, recoverAccount, signInAccount, signUpAccount,
} from '../api/account';
import { Header } from '../components/layout/Header';
import { Sidebar, type SidebarKey } from '../components/layout/Sidebar';

type AuthView = 'login' | 'signup' | 'recover' | 'reset';
export function AccountAuthPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [view, setView] = useState<AuthView>(location.pathname === '/account/reset' ? 'reset' : new URLSearchParams(location.search).get('view') === 'signup' ? 'signup' : new URLSearchParams(location.search).get('view') === 'recover' ? 'recover' : 'login');
  const [email, setEmail] = useState('');
  const [nickname, setNickname] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [recoveryReady, setRecoveryReady] = useState(false);

  useEffect(() => {
    if (!window.location.hash.includes('access_token=')) {
      if (location.pathname === '/account/reset') setError('재설정 링크가 없거나 만료됐습니다. 이메일에서 새 링크를 열어주세요.');
      return;
    }
    acceptAuthRedirect().then((kind) => {
      if (kind === 'signup') {
        navigate('/account', { replace: true });
      } else if (kind === 'recovery') {
        setView('reset');
        setRecoveryReady(true);
        setError('');
      } else {
        setError('인증 링크의 형식이 올바르지 않습니다.');
      }
    }).catch((cause) => setError(cause instanceof Error ? cause.message : '인증 링크를 확인하지 못했습니다.'));
  }, [location.pathname, navigate]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      if (view === 'login') {
        await signInAccount(email, password);
        navigate('/account', { replace: true });
      } else if (view === 'signup') {
        if (password !== confirmation) throw new Error('비밀번호가 서로 일치하지 않습니다.');
        const status = await signUpAccount(email, password, nickname);
        if (status === 'confirmed') navigate('/account', { replace: true });
        else {
          setNotice('가입 확인 메일을 보냈습니다. 이메일에서 인증을 완료한 후 로그인해주세요.');
          setView('login');
        }
      } else if (view === 'recover') {
        await recoverAccount(email);
        setNotice('해당 이메일로 계정이 있다면 비밀번호 재설정 안내가 전송됩니다.');
      } else {
        if (!recoveryReady) throw new Error('비밀번호 재설정 링크부터 확인해주세요.');
        if (password !== confirmation) throw new Error('비밀번호가 서로 일치하지 않습니다.');
        await changeAccountPassword(password);
        setNotice('비밀번호가 변경됐습니다. 이제 계정 화면에서 로그인 상태를 확인할 수 있습니다.');
        navigate('/account', { replace: true });
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '계정 요청에 실패했습니다.');
    } finally {
      setBusy(false);
    }
  };
  const changeView = (next: AuthView) => {
    setView(next);
    setError('');
    setNotice('');
    setPassword('');
    setConfirmation('');
  };
  const handleNav = (key: SidebarKey) => {
    if (key === 'comments') navigate('/');
    else if (key === 'dashboard') navigate('/dashboard');
    else if (key === 'persona') navigate('/persona');
  };

  return (
    <div className="app">
      <Sidebar current="account" onNav={handleNav} />
      <div className="main">
        <Header title={view==='signup'?'회원가입':view==='login'?'로그인':'계정 복구'} subtitle="AI_COMMENT 회원 계정 · 이메일 인증 및 개인 저장 공간" />
        <main className="account-auth-page">
          <section className="account-auth-card">
            <div className="account-auth-icon"><ShieldCheck size={23} /></div>
            <span className="credential-kicker">YOUR PRIVATE WORKSPACE</span>
            <h1>{view==='signup'?'나만의 작업 공간 만들기':view==='login'?'다시 오신 것을 환영해요':view==='recover'?'비밀번호 찾기':'비밀번호 다시 설정'}</h1>
            <p>계정을 만들면 추천 분석 기록을 개인 작업 공간에 보관하고 다른 기기에서도 확인할 수 있어요.</p>
            {(view==='login'||view==='signup') && (
              <div className="account-auth-tabs" role="group" aria-label="인증 방식">
                <button type="button" aria-pressed={view==='login'} className={view==='login'?'active':''} onClick={()=>changeView('login')}>로그인</button>
                <button type="button" aria-pressed={view==='signup'} className={view==='signup'?'active':''} onClick={()=>changeView('signup')}>회원가입</button>
              </div>
            )}
            <form onSubmit={(event)=>void submit(event)} className="account-auth-form">
              {view==='signup' && <label>닉네임
                <span className="account-auth-field"><UserRound size={17}/><input autoComplete="nickname" value={nickname} maxLength={32} minLength={2}
                  required placeholder="2~32자 · 중복 가능" onChange={e=>setNickname(e.target.value)}/></span></label>}
              {view!=='reset' && <label>이메일
                <span className="account-auth-field"><Mail size={17}/><input type="email" autoComplete="email" value={email}
                  required placeholder="you@example.com" onChange={e=>setEmail(e.target.value)}/></span></label>}
              {view!=='recover' && <label>{view==='reset'?'새 비밀번호':'비밀번호'}
                <span className="account-auth-field"><Lock size={17}/><input type="password" minLength={view==='login'?1:8}
                  autoComplete={view==='login'?'current-password':'new-password'} value={password} required
                  placeholder={view==='login'?'비밀번호':'8자 이상'} onChange={e=>setPassword(e.target.value)}/></span></label>}
              {(view==='signup'||view==='reset') && <label>비밀번호 확인
                <span className="account-auth-field"><KeyRound size={17}/><input type="password" minLength={8}
                  autoComplete="new-password" value={confirmation} required
                  placeholder="비밀번호를 다시 입력해주세요" onChange={e=>setConfirmation(e.target.value)}/></span></label>}
              {error && <div className="inline-status error" role="alert">{error}</div>}
              {notice && <div className="inline-status" role="status">{notice}</div>}
              <button className="btn primary account-auth-submit" type="submit" disabled={busy || (view==='reset'&&!recoveryReady)}>
                {busy?<LoaderCircle size={17} className="spin"/>:<ArrowRight size={17}/>}
                {view==='login'?'로그인':view==='signup'?'이메일로 가입':view==='recover'?'재설정 메일 보내기':'새 비밀번호 저장'}
              </button>
            </form>
            {view==='login' && <button type="button" className="account-auth-link" onClick={()=>changeView('recover')}>비밀번호를 잊으셨나요?</button>}
            {(view==='recover'||view==='reset') && <button type="button" className="account-auth-link" onClick={()=>navigate('/account/auth')}>로그인 화면으로</button>}
            <p className="account-auth-footnote">비밀번호는 AI_COMMENT 서버에 저장하지 않으며 Supabase Auth에서 처리합니다. 공개 데모는 로그인 없이도 사용할 수 있습니다.</p>
          </section>
        </main>
      </div>
    </div>
  );
}
