'use client';
import {useEffect,useRef} from 'react';
import {Dish} from '@/lib/model';
import {Art} from './ui';

// Pointer movement updates only the composited card, not the whole voting screen.
export function SwipeCard({dish,exit,busy,vote}:{dish:Dish;exit:number;busy:boolean;vote:(yes:boolean)=>void}){
  const card=useRef<HTMLDivElement>(null);const stamp=useRef<HTMLSpanElement>(null);
  const gesture=useRef<{x:number;y:number;dx:number;axis?:'x'|'y'}|null>(null);
  function paint(x:number){if(card.current)card.current.style.transform=`translate3d(${x}px,0,0) rotate(${x/28}deg)`;if(stamp.current){stamp.current.style.opacity=String(Math.min(Math.abs(x)/100,1));stamp.current.textContent=x>0?'ХОЧУ':'НЕ СЕГОДНЯ';stamp.current.className=`swipe-stamp ${x>0?'yes':'no'}`}}
  function reset(){gesture.current=null;if(card.current)card.current.style.transition='';paint(0)}
  useEffect(()=>{if(exit){card.current?.getAnimations().forEach(a=>a.cancel());gesture.current=null;if(card.current)card.current.style.transition='';paint(exit)}},[exit]);
  return <div ref={card} className="swipe-card" onPointerDown={e=>{if(busy||!e.isPrimary)return;e.currentTarget.getAnimations().forEach(a=>a.cancel());gesture.current={x:e.clientX,y:e.clientY,dx:0};e.currentTarget.setPointerCapture(e.pointerId)}} onPointerMove={e=>{const g=gesture.current;if(!g||busy)return;const dx=e.clientX-g.x,dy=e.clientY-g.y;if(!g.axis&&Math.max(Math.abs(dx),Math.abs(dy))>8)g.axis=Math.abs(dx)>Math.abs(dy)?'x':'y';if(g.axis!=='x')return;g.dx=dx;e.currentTarget.style.transition='none';paint(dx)}} onPointerUp={()=>{const g=gesture.current;if(!g||busy)return;gesture.current=null;if(card.current)card.current.style.transition='';if(g.axis==='x'&&Math.abs(g.dx)>90)vote(g.dx>0);else paint(0)}} onPointerCancel={reset} onLostPointerCapture={()=>{if(gesture.current)reset()}}><Art dish={dish} large/><h2>{dish.name}</h2><p className="muted">{dish.cookingTime} мин · {dish.category}</p><span ref={stamp} className="swipe-stamp yes" style={{opacity:0}}>ХОЧУ</span></div>
}
