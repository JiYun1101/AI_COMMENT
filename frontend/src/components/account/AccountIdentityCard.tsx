import { Check, LogIn, LogOut, Pencil, ShieldCheck, UserRound, KeyRound } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  cachedAccount, ensureAccountProfile, getAccount, signOutAccount,
  subscribeToAccountChange, updateAccountNickname,
} from '../../api/account';
import type { AccountProfile, AuthAccount } from '../../api/account';

export function AccountIdentityCard() {
  const navigate = useNavigate();
  const [account, setAccount] = useState<AuthAccount | null>(()=>cachedAccount());
  const [profile, setProfile] = useState<AccountProfile | null>(null);
  const [loading, setLoading] = useState(Boolean(cachedAccount()));
  const [nickname, setNickname] = useState('');
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  useEffect(()=>{
    let active=true;
    const unsub = subscribeToAccountChange(()=> {
      if (!active) return;
      setAccount(cachedAccount());
    });
    getAccount().then(async user=>{
      if (!active) return;
      setAccount(user);
      if (user) {
        const next = await ensureAccountProfile().catch(()=>null);
        if (active) {
          setProfile(next);
          setNickname(next?.nickname||'');
          if (!next) setError('프로필 데이터를 불러오지 못했습니다. 잠시 후 다시 확인해주세요.');
        }
      }
    }).finally(()=>{if(active)setLoading(false)});
    return ()=>{active=false;unsub()};
  },[]);

  const save = async () => {
    setBusy(true);setError('');setMessage('');
    try {
      const next=await updateAccountNickname(nickname);
      setProfile(next);setEditing(false);setMessage('닉네임이 저장됐습니다.');
    } catch (cause) {setError(cause instanceof Error?cause.message:'저장하지 못했습니다.');}
    finally {setBusy(false);}
  };
  const logout = async () => {
    setBusy(true);setError('');
    await signOutAccount();
    setAccount(null);setProfile(null);setEditing(false);setBusy(false);
    navigate('/account', {replace:true});
  };
  return (
    <section className="account-identity-card" aria-label="AI_COMMENT 사용자 계정">
      {account ? (
        <>
          <div className="account-identity-heading">
            <div className="account-identity-avatar"><UserRound size={22}/></div>
            <div className="account-identity-headline">
              <span className="credential-kicker">SIGNED IN · PRIVATE WORKSPACE</span>
              <h2>{profile?.nickname||'내 계정'}</h2>
              <p>{account.email} · 계정별 분석 기록을 안전하게 보관합니다.</p>
            </div>
            <span className="account-identity-check"><ShieldCheck size={14}/> 로그인됨</span>
          </div>
          {loading&&<p className="eng-note">계정 프로필 확인 중...</p>}
          {editing ? <div className="account-nickname-editor">
            <label>닉네임 (중복 가능)<input className="account-text-input" value={nickname} minLength={2} maxLength={32}
              onChange={(e)=>setNickname(e.target.value)} /></label>
            <button className="btn primary sm" type="button" disabled={busy} onClick={()=>void save()}><Check size={14}/>저장</button>
            <button className="btn secondary sm" type="button" onClick={()=>setEditing(false)}>취소</button>
          </div> : <div className="account-identity-actions">
            <button type="button" className="btn secondary sm" onClick={()=>setEditing(true)}><Pencil size={14}/> 닉네임 수정</button>
            <button type="button" className="btn secondary sm" onClick={()=>navigate('/account/auth?view=recover')}><KeyRound size={14}/> 비밀번호 관리</button>
            <button type="button" className="btn secondary sm" disabled={busy} onClick={()=>void logout()}><LogOut size={14}/> 로그아웃</button>
          </div>}
          {message && <div className="inline-status" role="status">{message}</div>}
          {error && <div className="inline-status error" role="alert">{error}</div>}
        </>
      ) : (
        <>
          <div className="account-identity-heading">
            <div className="account-identity-avatar"><UserRound size={22}/></div>
            <div className="account-identity-headline">
              <span className="credential-kicker">AI_COMMENT ACCOUNT</span>
              <h2>계정으로 내 분석을 보관하세요</h2>
              <p>이메일로 가입하고 분석 기록을 내 계정에 저장하면 다른 기기에서도 확인할 수 있어요.</p>
            </div>
          </div>
          <div className="account-identity-actions">
            <button type="button" className="btn primary" onClick={()=>navigate('/account/auth')}><LogIn size={15}/> 로그인</button>
            <button type="button" className="btn secondary" onClick={()=>navigate('/account/auth?view=signup')}><UserRound size={15}/> 회원가입</button>
          </div>
          <p className="eng-note">회원 계정과 아래의 YouTube 게시 모드는 서로 다릅니다. 데모 댓글 생성은 회원가입 없이도 이용할 수 있어요.</p>
        </>
      )}
    </section>
  );
}
