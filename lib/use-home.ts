'use client';
import {useCallback,useEffect,useRef,useState} from 'react';
import {DataState,Dish,Home,Plan,Preference} from './model';
import {useTelegram} from '@/components/doma/telegram';
export type SharedHome=DataState&{member:string;partnerConnected:boolean};
export function useHome(){
  const telegram=useTelegram();const[data,setData]=useState<SharedHome|null>(null);const[error,setError]=useState('');const[loading,setLoading]=useState(false);
  const[needsHome,setNeedsHome]=useState(false);
  const apply=useCallback((result:SharedHome&{needsHome?:boolean})=>{setNeedsHome(!!result.needsHome);setData(previous=>{if(result.needsHome)return null;const byId=new Map(previous?.dishes.map(d=>[d.id,d]));const dishes=result.dishes.map(d=>{const old=byId.get(d.id);if(old?.photo&&d.photo&&old.photo.split('?')[0]===d.photo.split('?')[0]&&Number(new URLSearchParams(old.photo.split('?')[1]).get('expires'))>Date.now()/1000+60)return {...d,photo:old.photo};return d});const next={...result,dishes};return JSON.stringify(previous)===JSON.stringify(next)?previous:next})},[]);
  const token=useRef('');const sequence=useRef(0);const busy=useRef(false);
  const api=useCallback(async(path:string,body?:unknown)=>{
    const response=await fetch('/api/backend/'+path,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json',...(token.current?{Authorization:`Bearer ${token.current}`}:{})},body:body===undefined?undefined:JSON.stringify(body),cache:'no-store',signal:AbortSignal.timeout(25000)});
    const result=await response.json();if(!response.ok)throw new Error(result.error||'Не удалось выполнить запрос');return result;
  },[]);
  const login=useCallback(async()=>{
    if(!telegram)return;setLoading(true);const request=++sequence.current;
    try{const result=await api('session',{initData:telegram.initData});if(request!==sequence.current)return;token.current=result.token;delete result.token;apply(result);setError('')}
    catch(e){if(request===sequence.current)setError((e as Error).message)}finally{if(request===sequence.current)setLoading(false)}
  },[telegram,api,apply]);
  useEffect(()=>{login();return()=>{sequence.current++;token.current=''}},[login]);
  const refresh=useCallback(async()=>{
    if(!token.current||busy.current)return;const request=++sequence.current;
    try{const result=await api('state');if(request===sequence.current){apply(result);setError('')}}catch{if(request===sequence.current)setError('Нет связи с сервером. Повторим подключение автоматически.')}
  },[api,apply]);
  useEffect(()=>{const timer=setInterval(()=>{if(document.visibilityState==='visible')refresh()},6000);const visible=()=>{if(document.visibilityState==='visible')refresh()};document.addEventListener('visibilitychange',visible);return()=>{clearInterval(timer);document.removeEventListener('visibilitychange',visible)}},[refresh]);
  async function mutate(body:{action:string;kind?:string;value?:unknown;id?:string;source?:Plan;target?:Plan}){
    if(busy.current)throw new Error('Предыдущее изменение ещё сохраняется.');busy.current=true;++sequence.current;
    const previous=data;
    if(previous){const next={...previous};if(body.action==='save'){
      const upsert=<T extends {id:string}>(rows:T[],v:T)=>rows.some(x=>x.id===v.id)?rows.map(x=>x.id===v.id?v:x):[...rows,v];
      if(body.kind==='dish')next.dishes=upsert(previous.dishes,body.value as Dish);
      if(body.kind==='home')next.home=body.value as Home;
      if(body.kind==='plan')next.plans=upsert(previous.plans,body.value as Plan);
      if(body.kind==='preference')next.preferences=upsert(previous.preferences,body.value as Preference);
    }else if(body.action==='delete'){
      if(body.kind==='dish'){next.dishes=previous.dishes.filter(x=>x.id!==body.id);next.plans=previous.plans.filter(x=>x.dishId!==body.id);next.preferences=previous.preferences.filter(x=>x.dishId!==body.id)}
      if(body.kind==='plan')next.plans=previous.plans.filter(x=>x.id!==body.id);
    }setData(next)}
    try{apply(await api('mutate',body));setError('')}catch(e){setData(previous);setError((e as Error).message);throw e}finally{busy.current=false}
  }
  async function createHome(){if(busy.current)return;busy.current=true;setLoading(true);++sequence.current;try{apply(await api('homes',{}));setError('')}catch(e){setError((e as Error).message)}finally{busy.current=false;setLoading(false)}}
  return {data,error,loading,needsHome,createHome,telegram,login,mutate,api};
}
