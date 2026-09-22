import {env} from 'cloudflare:workers';
import {cookies} from 'next/headers';
export function db(){if(!env.DB)throw new Error('Хранилище пока недоступно');return env.DB}
export function bucket(){if(!env.BUCKET)throw new Error('Фотографии пока недоступны');return env.BUCKET}
export async function hash(value:string){return [...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value)))].map(n=>n.toString(16).padStart(2,'0')).join('')}
export function token(){return crypto.randomUUID()+crypto.randomUUID()}
export async function identity(){const c=await cookies();const t=c.get('doma-session')?.value;if(!t)return null;return db().prepare('SELECT home_id,member FROM sessions WHERE hash=? AND expires>?').bind(await hash(t),Date.now()).first<{home_id:string;member:string}>()}
export async function setSession(home:string,member:string,request:Request){const t=token();await db().prepare('INSERT INTO sessions(hash,home_id,member,expires) VALUES(?,?,?,?)').bind(await hash(t),home,member,Date.now()+365*86400000).run();(await cookies()).set('doma-session',t,{httpOnly:true,secure:new URL(request.url).protocol==='https:',sameSite:'lax',path:'/',maxAge:365*86400})}
export function checkOrigin(request:Request){const origin=request.headers.get('origin');if(!origin||origin!==new URL(request.url).origin)throw new Error('Запрос отклонён. Обновите страницу.')}
export function failure(error:unknown){console.error(error instanceof Error?error.message:'App error');return Response.json({error:error instanceof Error?error.message:'Не удалось сохранить. Попробуйте ещё раз.'},{status:400})}
