import assert from 'node:assert/strict';
import ts from 'typescript';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../lib/dish-cover.ts',import.meta.url),'utf8');
const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const {singleEmoji}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
for(const emoji of ['🍕','🍽️','👩🏽‍🍳','🇮🇹','1️⃣'])assert.equal(singleEmoji(emoji),emoji);
for(const invalid of ['','паста','🍕🍔','a'])assert.equal(singleEmoji(invalid),null);
console.log('PASS: single emoji, joined emoji, skin tones and invalid input');
