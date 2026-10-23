import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';

test('site login establishes the portal-origin session and returns to Code Collective',()=>{
 const removed=[],events={};
 const link={dataset:{},classList:{contains:()=>false,remove(){},add(){}},removeAttribute:key=>removed.push(key),setAttribute(){},addEventListener:(name,handler)=>events[name]=handler,replaceChildren(){}};
 const assigned=[];
 const context=vm.createContext({HTMLElement:class{},customElements:{define(){}},document:{querySelectorAll:()=>[link],addEventListener(){},createElement:()=>({className:'',setAttribute(){},append(){}})},window:{location:{assign:value=>assigned.push(value)}}});
 vm.runInContext(readFileSync(new URL('../js/reusableComponents.js',import.meta.url),'utf8'),context);
 vm.runInContext('configurePortalLogin()',context);
 assert.equal(link.href,'https://orgportal.cc/users/login?next=%2Forgs%2Fcode-collective');
 assert.ok(removed.includes('aria-haspopup'));
 assert.equal(events.click,undefined,'login must follow the portal link instead of opening the old modal');
 context.testLink=link;
 vm.runInContext("renderAuthenticatedNav(testLink,{full_name:'Dummy User'},'/pidp')",context);
 assert.equal(link.href,'https://orgportal.cc/orgs/code-collective');
 events.click({preventDefault(){}});assert.deepEqual(assigned,['https://orgportal.cc/orgs/code-collective']);
 const home=readFileSync(new URL('../index.html',import.meta.url),'utf8');
 assert.match(home,/href="https:\/\/orgportal.cc\/users\/login\?next=%2Forgs%2Fcode-collective"/);
});

test('built pages invalidate cached navigation only when shared script bytes change',async()=>{
 const {mkdtempSync,writeFileSync,mkdirSync,rmSync}=await import('node:fs');
 const {tmpdir}=await import('node:os');const {join}=await import('node:path');
 const {execFileSync}=await import('node:child_process');
 const root=mkdtempSync(join(tmpdir(),'cc-header-'));
 try{
  mkdirSync(join(root,'js'));mkdirSync(join(root,'nested'));
  const script=join(root,'js/reusableComponents.js');writeFileSync(script,'version one');
  writeFileSync(join(root,'index.html'),'<script src="/js/reusableComponents.js?v=old"></script>');
  writeFileSync(join(root,'nested/index.html'),"<script src='../js/reusableComponents.js'></script>");
  const run=()=>execFileSync('python3',[new URL('../scripts/version_shared_header.py',import.meta.url).pathname,root]);
  run();const first=readFileSync(join(root,'index.html'),'utf8');assert.match(first,/\?v=[a-f0-9]{16}/);
  assert.equal(readFileSync(join(root,'nested/index.html'),'utf8').match(/\?v=([a-f0-9]+)/)[1],first.match(/\?v=([a-f0-9]+)/)[1]);
  run();assert.equal(readFileSync(join(root,'index.html'),'utf8'),first);
  writeFileSync(script,'version two');run();assert.notEqual(readFileSync(join(root,'index.html'),'utf8'),first);
 }finally{rmSync(root,{recursive:true,force:true})}
});
