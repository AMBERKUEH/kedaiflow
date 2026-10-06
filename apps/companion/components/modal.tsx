import { useEffect, useRef } from 'react';
import { X, LoaderCircle } from 'lucide-react';
export function Modal({title,children,close}: {title:string;children:React.ReactNode;close:()=>void}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(()=>{dialog.current?.showModal(); const el=dialog.current; return ()=>el?.close();},[]);
  return <dialog aria-label={title} ref={dialog} className="modal" onCancel={close} onClick={e=>{if(e.target===dialog.current)close();}}><div className="modal-head"><div><span className="eyebrow">KEDAIFLOW WORKSPACE</span><h2>{title}</h2></div><button className="icon-button" aria-label="Close dialog" onClick={close}><X size={20}/></button></div>{children}</dialog>;
}
export function Field({label,name,type='text',value,required=true,placeholder,options}: {label:string;name:string;type?:string;value?:string|number;required?:boolean;placeholder?:string;options?:{value:string;label:string}[]}) {
  return <label className="field"><span>{label}</span>{options?<select name={name} defaultValue={value} required={required}>{options.map(o=><option key={o.value} value={o.value}>{o.label}</option>)}</select>:type==='textarea'?<textarea name={name} defaultValue={value} required={required} placeholder={placeholder} rows={4}/>:<input name={name} type={type} defaultValue={value} required={required} placeholder={placeholder} step={type==='number'?'0.01':undefined}/>}</label>;
}
export function Submit({busy,label='Save and continue'}: {busy:boolean;label?:string}) {return <button className="button primary" disabled={busy} type="submit">{busy&&<LoaderCircle size={16} className="spin"/>}{busy?'Saving…':label}</button>;}

