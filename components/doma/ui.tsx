'use client';
import {ReactNode,useEffect,useRef} from 'react';
import {Dialog,DialogContent,DialogTitle,DialogDescription} from '@/components/ui/dialog';
import {Select,SelectContent,SelectItem,SelectTrigger,SelectValue} from '@/components/ui/select';
import {Switch} from '@/components/ui/switch';
import {Dish} from '@/lib/model';
import {useTelegramBack} from './telegram';
import {ChevronRight} from 'lucide-react';
export function Modal({title,children,close,action,wide=false}:{title:string;children:ReactNode;close:()=>void;action?:ReactNode;wide?:boolean}){
  const panel=useRef<HTMLDivElement>(null);const closing=useRef(false);const latestClose=useRef(close);latestClose.current=close;
  const reduced=()=>window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  useEffect(()=>{const el=panel.current;if(!el||reduced())return;const animation=el.animate([{opacity:0,transform:'translate(-50%, 48px) scale(.98)'},{opacity:1,transform:'translate(-50%, 0) scale(1)'}],{duration:360,easing:'cubic-bezier(.16,1,.3,1)'});return()=>animation.cancel()},[]);
  async function dismiss(){if(closing.current)return;closing.current=true;const el=panel.current;if(el&&!reduced()){try{await Promise.race([el.animate([{opacity:1,transform:'translate(-50%, 0)'},{opacity:0,transform:'translate(-50%, 32px)'}],{duration:180,easing:'cubic-bezier(.4,0,1,1)',fill:'forwards'}).finished,new Promise(resolve=>setTimeout(resolve,220))])}catch{}}latestClose.current()}
  useTelegramBack(dismiss);
  return <Dialog open onOpenChange={v=>!v&&dismiss()}><DialogContent ref={panel} showCloseButton={false} className={`native-sheet ${wide?'wide':''}`} aria-describedby={undefined}><header className="sheet-bar"><button onClick={dismiss}>Закрыть</button><DialogTitle>{title}</DialogTitle><div>{action}</div></header><div className="sheet-body">{children}</div></DialogContent></Dialog>
}
export function Pick({label,value,options,onChange}:{label:string;value:string;options:string[];onChange:(v:string)=>void}){return <Select value={value||'__empty'} onValueChange={v=>onChange(v==='__empty'?'':v)}><SelectTrigger aria-label={label} className="native-select"><SelectValue/></SelectTrigger><SelectContent>{options.map(o=><SelectItem key={o||'__empty'} value={o||'__empty'}>{o||'Без единицы'}</SelectItem>)}</SelectContent></Select>}
export function Toggle({label,value,onChange}:{label:string;value:boolean;onChange:(v:boolean)=>void}){return <label className="form-row"><span>{label}</span><Switch aria-label={label} checked={value} onCheckedChange={onChange} className="native-switch"/></label>}
export function Art({dish,large=false}:{dish:Dish;large?:boolean}){return <div className={`food-art ${large?'large':''}`} aria-hidden>{dish.photo?<img src={dish.photo} alt="" decoding="async" loading={large?'eager':'lazy'}/>:<div className="plate"><span>{dish.symbol}</span></div>}</div>}
export function Row({dish,onClick}:{dish:Dish;onClick:()=>void}){return <button className="dish-row" onClick={onClick}><Art dish={dish}/><span><strong>{dish.name}</strong><small>{dish.noCooking?'Без готовки':`${dish.cookingTime} мин`}</small></span><ChevronRight size={16}/></button>}
export function Section({title,children,hint}:{title:string;children:ReactNode;hint?:string}){return <section className="form-section"><h3>{title}</h3><div className="form-group">{children}</div>{hint&&<p className="hint">{hint}</p>}</section>}
export function Primary({children,onClick,disabled=false}:{children:ReactNode;onClick?:()=>void;disabled?:boolean}){return <button className="primary" onClick={onClick} disabled={disabled}>{children}</button>}
