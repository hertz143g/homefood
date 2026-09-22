import assert from 'node:assert/strict';
import ts from 'typescript';
import {readFileSync} from 'node:fs';
const code=ts.transpileModule(readFileSync(new URL('../lib/tournament.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const {startTournament,advance}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
for(const n of [2,3,4,5,8,12,13,16]){
 let t=startTournament(Array.from({length:n},(_,i)=>String(i)));let votes=0;
 while(!t.champion){const p=t.rounds.at(-1).find(p=>!p.winner);assert.ok(p?.left&&p?.right);t=advance(t,p.left);assert.ok(++votes<=n-1)}
 assert.equal(votes,n-1);
 assert.equal(new Set(t.rounds[0].flatMap(p=>[p.left,p.right].filter(Boolean))).size,n);
}
console.log('PASS: tournament brackets for 2–16 entrants, byes and N−1 votes');
