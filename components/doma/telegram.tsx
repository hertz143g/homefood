'use client';

import Script from 'next/script';
import {createContext, useContext, useEffect, useRef, useState, type ReactNode} from 'react';

type Insets = {top:number; bottom:number; left:number; right:number};
type TelegramApp = {
  initData:string;
  colorScheme:'light'|'dark';
  viewportStableHeight:number;
  safeAreaInset?:Insets;
  contentSafeAreaInset?:Insets;
  ready:()=>void;
  expand:()=>void;
  isVersionAtLeast:(version:string)=>boolean;
  setHeaderColor:(color:string)=>void;
  setBackgroundColor:(color:string)=>void;
  setBottomBarColor?:(color:string)=>void;
  onEvent:(name:string, callback:()=>void)=>void;
  offEvent:(name:string, callback:()=>void)=>void;
  BackButton:{show:()=>void; hide:()=>void; onClick:(fn:()=>void)=>void; offClick:(fn:()=>void)=>void};
  HapticFeedback?:{selectionChanged:()=>void; impactOccurred:(style:'light')=>void};
};
declare global {interface Window {Telegram?:{WebApp:TelegramApp}}}
const TelegramContext=createContext<TelegramApp|null>(null);
const backHandlers=new Map<symbol,{priority:number;order:number;run:()=>void}>();
let order=0;
function updateBack(app:TelegramApp){if(!app.isVersionAtLeast('6.1'))return;if(backHandlers.size)app.BackButton.show();else app.BackButton.hide()}
function goBack(){const handlers=[...backHandlers.values()].sort((a,b)=>b.priority-a.priority||b.order-a.order);handlers[0]?.run()}

export function TelegramProvider({children}:{children:ReactNode}){
  const[app,setApp]=useState<TelegramApp|null>(null);
  function connect(){const webApp=window.Telegram?.WebApp;if(webApp?.initData)setApp(webApp)}
  useEffect(()=>{
    if(!app)return;
    const root=document.documentElement;
    const sync=()=>{
      root.dataset.telegram='true';
      root.dataset.theme=app.colorScheme;
      root.style.colorScheme=app.colorScheme;
      if(app.viewportStableHeight>0)root.style.setProperty('--app-height',`${app.viewportStableHeight}px`);
      for(const side of ['top','bottom','left','right'] as const){
        const inset=Math.max(0,app.safeAreaInset?.[side]||0)+Math.max(0,app.contentSafeAreaInset?.[side]||0);
        root.style.setProperty(`--app-safe-${side}`,`${inset}px`);
      }
      const background=app.colorScheme==='dark'?'#000000':'#ffffff';
      if(app.isVersionAtLeast('6.1')){app.setHeaderColor(background);app.setBackgroundColor(background)}
      if(app.isVersionAtLeast('7.10'))app.setBottomBarColor?.(background);
    };
    sync();app.ready();app.expand();
    const events=['themeChanged','viewportChanged','safeAreaChanged','contentSafeAreaChanged'];
    events.forEach(event=>app.onEvent(event,sync));
    if(app.isVersionAtLeast('6.1')){app.BackButton.onClick(goBack);updateBack(app)}
    return()=>{events.forEach(event=>app.offEvent(event,sync));if(app.isVersionAtLeast('6.1')){app.BackButton.offClick(goBack);app.BackButton.hide()}delete root.dataset.telegram;delete root.dataset.theme;root.style.removeProperty('color-scheme');root.style.removeProperty('--app-height');['top','bottom','left','right'].forEach(side=>root.style.removeProperty(`--app-safe-${side}`))};
  },[app]);
  return <TelegramContext.Provider value={app}><Script src="https://telegram.org/js/telegram-web-app.js" strategy="afterInteractive" onReady={connect}/>{children}</TelegramContext.Provider>;
}

export function useTelegramBack(callback:()=>void,active=true,priority=100){
  const app=useContext(TelegramContext);const callbackRef=useRef(callback);callbackRef.current=callback;
  useEffect(()=>{if(!app||!active)return;const key=Symbol();backHandlers.set(key,{priority,order:++order,run:()=>callbackRef.current()});updateBack(app);return()=>{backHandlers.delete(key);updateBack(app)}},[app,active,priority]);
}
export function selectionHaptic(){const app=typeof window!=='undefined'?window.Telegram?.WebApp:null;if(app?.initData&&app.isVersionAtLeast('6.1'))app.HapticFeedback?.selectionChanged()}
