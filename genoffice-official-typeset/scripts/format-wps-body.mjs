#!/usr/bin/env node
// Use the installed GenOffice engine, then carry measured WPS OOXML formatting.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import helpers from './runtime.cjs';

const DIR=path.dirname(fileURLToPath(import.meta.url));
const ASSET=JSON.parse(fs.readFileSync(path.join(DIR,'../assets/wps-body-format.json'),'utf8'));
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const FINAL_FONTS={title:'方正小标宋简体',body:'仿宋_GB2312',heading1:'黑体',heading2:'楷体_GB2312',latin:'Times New Roman',footer:'宋体'};
// These are the glyph families recorded as WPS's actual aliases on the measured
// Mac. A canonical font installed by the user always takes precedence.
const WPS_ALIASES={
  '方正小标宋简体':['汉仪书宋二KW','HYShuSongErKW'],
  '仿宋_GB2312':['FangSong_GB2312'],
  '黑体':['汉仪中黑KW','HYZhongHeiKW'],
  '楷体_GB2312':['汉仪楷体简','HYKaiTiJ'],
  '宋体':['汉仪书宋二KW','HYShuSongErKW']
};

function run(cmd,args,env=process.env){
  const p=spawnSync(cmd,args,{encoding:'utf8',env,maxBuffer:64*1024*1024});
  if(p.status!==0)throw new Error(p.stderr||p.stdout||p.error?.message||'命令执行失败');
  let r;try{r=JSON.parse(p.stdout);}catch{throw new Error(p.stdout||'未返回有效 JSON');}
  if(r.status!=='ok')throw new Error(JSON.stringify(r));
  return r;
}
function main(){
  const args=process.argv.slice(2),opts={};
  if(!args.length||args.includes('--help')){
    console.log('用法：node format-wps-body.mjs 原文.txt|md|html|docx --out 输出.docx [--roles 段落类型.json] [--plan-only] [--render]；环境检查：--doctor');return;
  }
  const runtime=helpers.resolveRuntime();
  const python=process.env.PYTHON3||'python3';
  let pythonRuntime;
  try{pythonRuntime=run(python,['-c','import json,sys; print(json.dumps({"status":"ok" if sys.version_info.major == 3 else "error","executable":sys.executable,"version":sys.version.split()[0]}))']);}
  catch{throw new Error('未找到可用的 Python 3。请安装 Python 3，或用 PYTHON3 指定解释器路径后重试。');}
  const cli=a=>run(runtime.runtime,[runtime.bundle,...a,'--json'],{...process.env,ELECTRON_RUN_AS_NODE:'1'});
  const fonts=helpers.inventory();
  const fontResolution=ASSET.requiredFonts.map(requested=>{
    const resolved=fonts.has(requested)?requested:(WPS_ALIASES[requested]||[]).find(f=>fonts.has(f));
    return {requested,resolved:resolved||null,match:resolved===requested?'canonical':resolved?'measured-wps-alias':'missing'};
  });
  const missingFonts=fontResolution.filter(f=>!f.resolved).map(f=>f.requested);
  const renderFontMap=Object.fromEntries(fontResolution.filter(f=>f.resolved&&f.resolved!==f.requested).map(f=>[f.requested,f.resolved]));
  const finalFonts=Object.fromEntries(Object.entries(FINAL_FONTS).map(([role,font])=>[role,renderFontMap[font]||font]));
  if(args.length===1&&args[0]==='--doctor'){
    console.log(JSON.stringify({status:'ok',genoffice:runtime,python:pythonRuntime,formatPreset:'wps-official-body-measured-12.1.28496',fonts:FINAL_FONTS,fontResolution,missingFonts,visualParity:'not-verified'},null,2));return;
  }
  opts.input=path.resolve(args.shift());
  while(args.length){
    const a=args.shift();
    if(['--render','--plan-only'].includes(a))opts[a.slice(2)]=true;
    else if(['--out','--roles'].includes(a)){if(!args.length)throw new Error('缺少参数 '+a);opts[a.slice(2)]=args.shift();}
    else throw new Error('未知参数：'+a);
  }
  if(!opts.out||path.extname(opts.out).toLowerCase()!=='.docx')throw new Error('请用 --out 指定新的 .docx 文件');
  opts.out=path.resolve(opts.out);
  const base=opts.out.slice(0,-5),planPath=base+'.排版方案.json',reportPath=base+'.排版核验.json',previewPath=base+'.预览';
  for(const p of [opts.out,planPath,reportPath,...opts.render?[previewPath]:[]])if(fs.existsSync(p))throw new Error('为保留已有文件，请更换输出名称：'+p);
  if(opts.render&&missingFonts.length)throw new Error('WPS 同字体渲染缺少字体：'+missingFonts.join('、')+'。请把合法取得的原字体或 WPS 实际别名字体安装到系统字体目录后重试；DOCX 可省略 --render 先生成，文件保留 WPS 原字体名。');
  fs.mkdirSync(path.dirname(opts.out),{recursive:true});
  const work=fs.mkdtempSync(path.join(os.tmpdir(),'wps body skill '));
  const sourceHash=hash(opts.input),engineHash=hash(runtime.bundle);
  try{
    const prepared=path.join(work,'prepared.docx');
    const prepareArgs=[path.join(DIR,'format-official.mjs'),opts.input,'--out',prepared];
    if(opts.roles)prepareArgs.push('--roles',path.resolve(opts.roles));
    const preparation=run(process.execPath,prepareArgs);
    const oldPlan=JSON.parse(fs.readFileSync(preparation.plan,'utf8'));
    const plan={...oldPlan,profile:'wps-official-body-measured',formatPreset:'wps-official-body-measured-12.1.28496',
      config:{bodySizePt:16,titleSizePt:22,lineHeightPt:28,titleLineHeightPt:36,bodyCharacterSpacingPt:-0.3,titleSpacerHeightPt:15,firstLineChars:2,
        pageSetup:{paper:'A4',orientation:'portrait',margins:{top:2098,bottom:1984,left:1587,right:1474,header:851,footer:1417,gutter:0},columns:{count:1}},
        docGrid:{type:'linesAndChars',linePitchTwips:579,charSpace:15}},
      fonts:finalFonts,requestedWpsFonts:FINAL_FONTS,preparationFonts:oldPlan.fonts,fontResolution,missingFonts,templateSource:ASSET.source,calibration:'measured-template-with-sample-comparison'};
    delete plan.ops; // Starter ops are preparation details, not the final WPS format.
    fs.writeFileSync(planPath,JSON.stringify(plan,null,2)+'\n',{flag:'wx'});
    if(opts['plan-only']){console.log(JSON.stringify({status:'ok',plan:planPath,counts:plan.counts,missingFonts,formatPreset:plan.formatPreset},null,2));return;}
    const measured=path.join(work,'wps-measured.docx'),candidate=path.join(work,'wps-body.docx');
    const applied=run(python,[path.join(DIR,'apply-wps-body.py'),prepared,'--plan',preparation.plan,'--out',measured]);
    const compatibility=run(python,[path.join(DIR,'apply-genoffice-compat.py'),measured,'--font-map',JSON.stringify(renderFontMap),'--out',candidate]);
    const before=cli(['docs','read',prepared,'--full']),after=cli(['docs','read',candidate,'--full','--sections']);
    const content=r=>JSON.stringify(r.detail.items.filter(b=>b.text||b.type==='table'||b.type==='image').map(b=>({type:b.type==='heading'?'paragraph':b.type,text:b.text,rows:b.rows,cells:b.cells})));
    if(content(before)!==content(after))throw new Error('WPS 版式覆盖后的原文/对象核验失败');
    const check=cli(['docs','check',candidate]);
    if(hash(opts.input)!==sourceHash||hash(runtime.bundle)!==engineHash)throw new Error('原文或引擎文件在处理过程中发生变化');
    let rendered;
    if(opts.render)rendered=cli(['render',candidate,'--out',previewPath,'--scale','2']);
    fs.renameSync(candidate,opts.out);
    const report={...applied,status:'ok',output:opts.out,sourceUnchanged:true,appFilesUnchanged:true,sourceHash,outputHash:hash(opts.out),fonts:finalFonts,requestedWpsFonts:FINAL_FONTS,fontResolution,compatibility,missingFonts,check:check.detail,render:rendered?.detail,visualParity:'not-verified'};
    fs.writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n',{flag:'wx'});
    console.log(JSON.stringify({status:'ok',output:opts.out,plan:planPath,report:reportPath,preview:opts.render?previewPath:undefined,missingFonts,visualParity:'not-verified'},null,2));
  }finally{fs.rmSync(work,{recursive:true,force:true});}
}
try{main();}catch(e){console.error(e.message);process.exitCode=1;}
