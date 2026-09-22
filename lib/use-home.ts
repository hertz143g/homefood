'use client';
import {useCallback,useEffect,useRef,useState} from 'react';
import {DataState} from './model';
import {useTelegram} from '@/components/doma/telegram';
export type SharedHome=DataState&{member:string;partnerConnected:boolean};
export function useHome(){
  const telegram=useTelegram();const[data,setData]=useState<SharedHome|null>(null);const[error,setError]=useState('');const[loading,setLoading]=useState(false);
  const[needsHome,setNeedsHome]=useState(false);
  const apply=useCallback((result:SharedHome&{needsHome?:boolean})=>{setNeedsHome(!!result.needsHome);setData(result.needsHome?null:result)},[]);
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
  async function mutate(body:unknown){
    if(busy.current)throw new Error('Предыдущее изменение ещё сохраняется.');busy.current=true;++sequence.current;
    try{setData(await api('mutate',body));setError('')}catch(e){setError((e as Error).message);throw e}finally{busy.current=false}
  }
  async function createHome(){if(busy.current)return;busy.current=true;setLoading(true);++sequence.current;try{apply(await api('homes',{}));setError('')}catch(e){setError((e as Error).message)}finally{busy.current=false;setLoading(false)}}
  return {data,error,loading,needsHome,createHome,telegram,login,mutate,api};
}
