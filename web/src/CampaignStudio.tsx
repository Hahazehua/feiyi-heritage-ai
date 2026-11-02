import { useEffect, useState, type FormEvent } from 'react';
import { ArrowRight, Download, LoaderCircle } from 'lucide-react';

type Result = {
  status:string; checks_passed:boolean;
  assets:{id:string;channel:string;content:string}[];
  events:{author:string;stage:string;issue_count?:number;revision_count?:number}[];
  sources:string[]; facts:{field:string;value:unknown}[];
  trace:Record<string,string|number>;
};
type Props = {api:(path:string, body?:unknown)=>Promise<any>};

export default function CampaignStudio({api}:Props){
  const [products,setProducts]=useState<{id:string;title:string}[]>([]);
  const [product,setProduct]=useState(''),[goal,setGoal]=useState('Introduce this heritage gift concept to a business audience.');
  const [channel,setChannel]=useState('LinkedIn'),[enabled,setEnabled]=useState(false);
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  const [result,setResult]=useState<Result|null>(null),[reviewed,setReviewed]=useState(false);
  useEffect(()=>{api('campaign/products').then(d=>{setProducts(d.items);setProduct(d.items[0]?.id||'');setEnabled(d.enabled)}).catch(e=>setError(e.message));},[api]);
  async function submit(e:FormEvent){
    e.preventDefault();setBusy(true);setError('');setResult(null);setReviewed(false);
    try{setResult(await api('campaign',{product_id:product,goal,channel}))}
    catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  function download(){
    if(!result||!reviewed)return;
    const text='HAHA — manually reviewed draft, not published\nMVP demo data\n\n'+result.assets.map(a=>a.channel+'\n'+a.content).join('\n\n')+'\n\nReference sources\n'+result.sources.join('\n');
    const url=URL.createObjectURL(new Blob([text],{type:'text/plain;charset=utf-8'}));
    const a=document.createElement('a');a.href=url;a.download='haha-campaign-draft.txt';a.click();URL.revokeObjectURL(url);
  }
  return <section className="page campaign"><p className="eyebrow">THE DRAFT STUDIO</p><h1>Tell the story.<br/><em>Check every promise.</em></h1>
    <p className="intro">Shape an English campaign draft for a demo gift concept. Review the evidence and wording before using it. Nothing is posted or sent.</p>
    <form onSubmit={submit} className="brief-card">
      <div className="fields"><label>Demo concept<select required value={product} onChange={e=>setProduct(e.target.value)}>{products.map(p=><option key={p.id} value={p.id}>{p.title}</option>)}</select></label>
      <label>Format<select value={channel} onChange={e=>setChannel(e.target.value)}><option>LinkedIn</option><option>Instagram</option><option>Landing Page</option></select></label></div>
      <label>What should the draft achieve?<textarea required minLength={8} maxLength={500} value={goal} onChange={e=>setGoal(e.target.value)}/></label>
      <p className="small muted">Your brief is sent to DeepSeek. Avoid personal or confidential details. Demo prices and delivery capabilities are not verified commercial promises. Limit: 3 drafts per browser per day.</p>
      <button className="primary" disabled={busy||!enabled||!product}>{busy?<><LoaderCircle className="spin" size={18}/> Drafting and checking…</>:<>Create a draft <ArrowRight size={18}/></>}</button>
      {!enabled&&<p className="notice">The draft studio is not enabled on this deployment yet.</p>}
    </form>
    {error&&<p className="error" role="alert">{error}</p>}
    {result&&<div aria-live="polite" className="campaign-result">
      <h2>{result.checks_passed?'Ready for your review.':'This draft needs more work.'}</h2>
      <p className="notice">{result.trace.generation==='deepseek'?'DeepSeek draft':'Template fallback · AI generation was unavailable'} · Rule-based review · Not published</p>
      <p>Checks flag unsupported fields and known risky wording. They do not establish the truth of every sentence. Review all claims against the evidence below.</p>
      <ol className="campaign-steps">{result.events.map((e,i)=><li key={i}><strong>{e.stage==='draft'?'Draft':e.stage==='review'?'Evidence check':'Revision'}</strong>{e.issue_count!==undefined&&<span> · {e.issue_count} issues flagged</span>}{e.revision_count!==undefined&&<span> · revision {e.revision_count}</span>}</li>)}</ol>
      {!result.checks_passed&&<p className="error">Checks still failed after the bounded review loop. No draft is available for export.</p>}
      {result.assets.map(a=><article className="campaign-copy" key={a.id}><p className="eyebrow">{a.channel} · DRAFT</p><p>{a.content}</p></article>)}
      <details className="trace"><summary>Inspect the evidence and run details</summary><h3>Catalogue facts supplied to the writer</h3><dl>{result.facts.map(f=><div key={f.field}><dt>{f.field.replaceAll('_',' ')}</dt><dd>{typeof f.value==='string'?f.value:JSON.stringify(f.value)}</dd></div>)}</dl><h3>Reference sources</h3>{result.sources.length?result.sources.map(s=><p key={s}><a href={s} target="_blank" rel="noreferrer">{s}</a></p>):<p>No confirmed cultural source is attached to this concept.</p>}<h3>Run details</h3><dl>{Object.entries(result.trace).map(([k,v])=><div key={k}><dt>{k.replaceAll('_',' ')}</dt><dd>{v}</dd></div>)}</dl></details>
      {result.checks_passed&&<><label className="check-label consent"><input type="checkbox" checked={reviewed} onChange={e=>setReviewed(e.target.checked)}/> I have reviewed the wording and evidence. I understand this is a demo draft, not a verified offer.</label><button className="outline" disabled={!reviewed} onClick={download}><Download size={16}/> Export reviewed draft</button></>}
      <p className="small muted">Drafts are not saved to your workspace. Export before leaving this page. Your confirmation enables local export only.</p>
    </div>}
  </section>;
}
