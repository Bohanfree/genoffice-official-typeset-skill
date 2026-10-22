#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {chooseFonts,makePlan,FONT_CANDIDATES} from './official-typeset-core.mjs';

const DIR=path.dirname(fileURLToPath(import.meta.url));
import runtimeHelpers from './runtime.cjs';
const {resolveRuntime,inventory}=runtimeHelpers;
let runtime;
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
function help(){console.log('用法：node format-official.mjs 原文.txt|md|html|docx --out 输出.docx [--roles 段落类型.json] [--fonts 字体.json] [--profile 版式.json] [--plan-only] [--render]；环境检查：node format-official.mjs --doctor');}
function parseArgs(){
  const args=process.argv.slice(2),opts={};
  if(args.includes('--help')||!args.length){help();process.exit(0);}
  if(args.length===1 && args[0]==='--doctor') return {doctor:true};
  opts.input=args.shift();
  while(args.length){const a=args.shift();if(['--render','--plan-only'].includes(a))opts[a.slice(2)]=true;
    else if(['--out','--roles','--fonts','--profile'].includes(a)){if(!args.length)throw new Error(`缺少 ${a} 参数`);opts[a.slice(2)]=args.shift();}
    else throw new Error(`未知参数：${a}`);
  }
  if(!opts.out||path.extname(opts.out).toLowerCase()!=='.docx')throw new Error('请用 --out 指定新的 .docx 文件');
  opts.input=path.resolve(opts.input);opts.out=path.resolve(opts.out);return opts;
}
function cli(args,{bridge=false}={}){
  const cmd=runtime.runtime,argv=[bridge?path.join(DIR,'genoffice-bridge.cjs'):runtime.bundle,...args,'--json'];
  const p=spawnSync(cmd,argv,{encoding:'utf8',env:{...process.env,ELECTRON_RUN_AS_NODE:'1',GENOFFICE_RUNTIME:runtime.runtime,GENOFFICE_CLI:runtime.bundle},maxBuffer:64*1024*1024});
  let result;try{result=JSON.parse(p.stdout);}catch{throw new Error(p.stderr||p.stdout||p.error?.message||'GenOffice 未返回有效结果');}
  if(p.status!==0||result.status!=='ok')throw new Error(JSON.stringify(result));
  return result;
}
const load=p=>p?JSON.parse(fs.readFileSync(path.resolve(p),'utf8')):{};
function signature(r){return JSON.stringify(r.detail.items.map(b=>({index:b.index,type:b.type==='heading'?'paragraph':b.type,text:b.text,rows:b.rows,cells:b.cells})));}
function main(){
  const opts=parseArgs();runtime=resolveRuntime();
  if(opts.doctor){
    const available=inventory(),selection=chooseFonts(name=>available.has(name));
    for(const name of Object.values(selection.fonts))if(!available.has(name))throw new Error('缺少可用字体：'+name);
    console.log(JSON.stringify({status:'ok',platform:process.platform,node:process.version,genoffice:runtime,fonts:selection.fonts,fontSubstitutions:selection.substitutions},null,2));return;
  }
  if(!fs.existsSync(opts.input))throw new Error('原文不存在');
  const ext=path.extname(opts.input).toLowerCase();if(!['.txt','.md','.html','.htm','.docx'].includes(ext))throw new Error('支持 txt、md、html、docx');
  const base=opts.out.slice(0,-5),planPath=base+'.排版方案.json',reportPath=base+'.排版核验.json',renderPath=base+'.预览';
  for(const p of [opts.out,planPath,reportPath,...opts.render?[renderPath]:[]])if(fs.existsSync(p))throw new Error('为保留已有文件，请更换输出名称：'+p);
  fs.mkdirSync(path.dirname(opts.out),{recursive:true});
  const work=fs.mkdtempSync(path.join(path.dirname(opts.out),'.official-typeset-'));
  const sourceHash=hash(opts.input),cliHash=hash(runtime.bundle);
  try{
    let source=opts.input;
    if(ext!=='.docx'){
      let input=opts.input;
      let rawLines,markers;
      if(ext==='.txt'){
        input=path.join(work,'原文.html');
        rawLines=fs.readFileSync(opts.input,'utf8').replace(/\r\n?/g,'\n').split('\n');
        // The HTML importer collapses repeated spaces and empty paragraphs. Create one
        // unique marker per paragraph, then insert literal text through the engine.
        const prefix='GO_OFFICIAL_'+crypto.randomUUID().replace(/-/g,'')+'_';
        markers=rawLines.map((_,i)=>prefix+i);
        fs.writeFileSync(input,markers.map(t=>'<p>'+t+'</p>').join('\n'));
      }
      source=path.join(work,'原文.docx');cli(['create','--type','docx','--from',input,'--out',source]);
      if(rawLines){
        const restore=path.join(work,'literal-text.json');
        fs.writeFileSync(restore,JSON.stringify(rawLines.map((text,index)=>({op:'findReplace',target:{blockIndexes:[index]},find:markers[index],replace:text}))));
        const literal=path.join(work,'原文逐字.docx');
        cli(['docs','apply',source,'--ops',restore,'--out',literal]);source=literal;
        const restored=cli(['docs','read',source,'--full']);
        if(JSON.stringify(restored.detail.items.map(b=>b.text))!==JSON.stringify(rawLines))throw new Error('原文导入的逐字核验失败');
      }
    }
    const before=cli(['docs','read',source,'--full','--sections']);
    const available=inventory(),selection=chooseFonts(name=>available.has(name)),requestedFonts=load(opts.fonts),fonts={...selection.fonts,...requestedFonts};
    for(const k of Object.keys(requestedFonts))if(!Object.hasOwn(FONT_CANDIDATES,k))throw new Error('未知字体用途：'+k);
    for(const name of Object.values(fonts))if(!available.has(name))throw new Error('本机未安装指定字体：'+name);
    selection.substitutions=Object.entries(FONT_CANDIDATES).filter(([role,names])=>!Object.hasOwn(requestedFonts,role)&&fonts[role]!==names[0]).map(([role,names])=>({role,requested:names[0],actual:fonts[role]}));
    const plan=makePlan(before.detail.items,{fonts,overrides:load(opts.roles),profile:load(opts.profile)});
    if(!plan.ops.length)throw new Error('没有可排版的正文段落');
    const ops=[{op:'set_page_setup',...plan.pageSetup},...plan.ops];
    const opsFile=path.join(work,'ops.json');fs.writeFileSync(opsFile,JSON.stringify(ops));
    cli(['docs','apply',source,'--ops',opsFile,'--dry-run'],{bridge:true});
    fs.writeFileSync(planPath,JSON.stringify({...plan,input:opts.input,sourceHash,fontSubstitutions:selection.substitutions,ops},null,2)+'\n');
    if(opts['plan-only']){console.log(JSON.stringify({status:'ok',plan:planPath,counts:plan.counts,fontSubstitutions:selection.substitutions},null,2));return;}
    const candidate=path.join(work,'排版.docx');
    const applied=cli(['docs','apply',source,'--ops',opsFile,'--out',candidate],{bridge:true});
    const after=cli(['docs','read',candidate,'--full','--sections']);
    if(signature(before)!==signature(after))throw new Error('原文核验失败：段落文字、数量或对象结构发生变化');
    const check=cli(['docs','check',candidate]);
    const issues=check.detail?.issues||[];
    const critical=issues.filter(i=>['broken_ref','placeholder_left','field_not_evaluated'].includes(i.code)&&i.severity!=='info'&&i.level!=='info');
    if(critical.length)throw new Error('文档检查需处理：'+JSON.stringify(critical));
    if(hash(opts.input)!==sourceHash)throw new Error('原文文件在处理期间发生变化');
    if(hash(runtime.bundle)!==cliHash)throw new Error('软件文件在处理期间发生变化');
    let render;
    if(opts.render)render=cli(['render',candidate,'--out',renderPath]);
    fs.renameSync(candidate,opts.out);
    const report={status:'ok',output:opts.out,sourceUnchanged:true,textPreserved:true,appFilesUnchanged:true,version:plan.version,counts:plan.counts,fontSubstitutions:selection.substitutions,fonts,profile:plan.config,calibration:plan.calibration,check:check.detail,apply:applied.detail,render:render?.detail,sourceHash,outputHash:hash(opts.out)};
    fs.writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n');
    console.log(JSON.stringify({status:'ok',output:opts.out,plan:planPath,report:reportPath,preview:opts.render?renderPath:undefined,counts:plan.counts,fontSubstitutions:selection.substitutions,issues},null,2));
  }finally{fs.rmSync(work,{recursive:true,force:true});}
}
try{main();}catch(e){console.error(e.message);process.exitCode=1;}
