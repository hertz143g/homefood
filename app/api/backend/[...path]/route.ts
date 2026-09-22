import {request as httpsRequest} from 'node:https';
import {vpsCertificate} from '@/server/vps-certificate';
export const runtime='nodejs';
export const dynamic='force-dynamic';
export const maxDuration=30;

async function proxy(request:Request,{params}:{params:Promise<{path:string[]}>}){
  const {path}=await params;
  const route='/'+path.join('/');
  const allowed=request.method==='GET'?route==='/state'||route==='/health'||/^\/photos\/[a-f0-9]{32}$/.test(route):['/session','/mutate','/invite','/photos'].includes(route);
  if(!allowed)return Response.json({error:'Не найдено'},{status:404});
  const limit=2*1024*1024;
  if(Number(request.headers.get('content-length')||0)>limit)return new Response(null,{status:413});
  let body:Buffer|undefined;
  if(request.method==='POST'){
    const reader=request.body?.getReader();let length=0;const chunks:Uint8Array[]=[];
    if(reader){while(true){const {done,value}=await reader.read();if(done)break;length+=value.length;if(length>limit){await reader.cancel();return new Response(null,{status:413})}chunks.push(value)}}
    body=Buffer.concat(chunks);
  }
  const search=new URL(request.url).search;
  try{
    return await new Promise<Response>((resolve,reject)=>{
      const upstream=httpsRequest({hostname:'72.4.67.204',port:8443,path:route+search,method:request.method,ca:vpsCertificate,rejectUnauthorized:true,timeout:20000,headers:{'Content-Type':'application/json',...(body?{'Content-Length':String(body.length)}:{}),...(request.headers.get('authorization')?{Authorization:request.headers.get('authorization')!}:{})}},res=>{
        const chunks:Buffer[]=[];let size=0;
        res.on('data',(chunk:Buffer)=>{size+=chunk.length;if(size>4*1024*1024){res.destroy();reject(new Error('Response too large'))}else chunks.push(chunk)});
        res.on('error',reject);
        res.on('end',()=>resolve(new Response(Buffer.concat(chunks),{status:res.statusCode||502,headers:{'Content-Type':res.headers['content-type']||'application/json','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}})));
      });
      upstream.on('timeout',()=>upstream.destroy(new Error('Backend timeout')));upstream.on('error',reject);upstream.end(body);
    });
  }catch{return Response.json({error:'Сервер временно недоступен. Попробуйте ещё раз.'},{status:503})}
}
export {proxy as GET,proxy as POST};
