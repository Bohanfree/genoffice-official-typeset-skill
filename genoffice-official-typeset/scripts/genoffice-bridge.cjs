#!/usr/bin/env node
// Extend the installed CLI in this process only. The app bundle remains unchanged.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),Module=require('node:module');
const {resolveRuntime,VERIFIED_SHA256}=require('./runtime.cjs');
const CLI=resolveRuntime().bundle;
(async()=>{
  const {validateOfficialAttrs}=await import('./official-typeset-core.mjs');
  let source=fs.readFileSync(CLI,'utf8');
  if(crypto.createHash('sha256').update(source).digest('hex')!==VERIFIED_SHA256)throw new Error('GenOffice CLI 已更新。请先复核公文排版适配，再运行本技能。');
  const anchor='    register({\n      name: "setParagraphAttrs",';
  if(source.split(anchor).length!==2)throw new Error('GenOffice 排版接口不匹配');
  const registration=`register({
    name:"setOfficialParagraphFormat",
    signature:'{ op: "setOfficialParagraphFormat", target, attrs } // validated exact paragraph formatting (skill-local)',
    keys:["attrs"],target:"required",
    validate(op,where){return validateShape(op,this,where) ?? validateOfficialAttrs(op.attrs,where);},
    apply:runSetParagraphAttrs
  });\n`;
  source=validateOfficialAttrs.toString()+'\n'+source.replace(anchor,registration+anchor);
  // The shipped parser handles snapToGrid, but its PM-to-OOXML exporter omits the field.
  // Carry it through this one process so an existing Word document grid cannot override 28pt.
  const replaceOnce=(a,b)=>{if(source.split(a).length!==2)throw new Error('GenOffice 固定行距导出接口不匹配');source=source.replace(a,b);};
  replaceOnce('function nodeFormat(node) {\n  const format3 = {};','function nodeFormat(node) {\n  const format3 = {};\n  if (node.attrs?.snapToGrid === false) format3.snapToGrid = false;');
  replaceOnce('function formatPPrChildren(format3) {\n  if (!format3) return [];\n  const out = [];','function formatPPrChildren(format3) {\n  if (!format3) return [];\n  const out = [];\n  if (format3.snapToGrid === false) out.push({name:"w:snapToGrid",xml:\'<w:snapToGrid w:val="0"/>\'});');
  replaceOnce('  const managedTags = new Set(FORMAT_MANAGED_TAGS);','  const managedTags = new Set(FORMAT_MANAGED_TAGS);\n  if (format3?.snapToGrid === false || original2?.snapToGrid === false) managedTags.add("w:snapToGrid");');
  const cliModule=new Module(CLI,module);cliModule.filename=CLI;cliModule.paths=Module._nodeModulePaths(path.dirname(CLI));
  cliModule._compile(source,CLI);
  const result=await cliModule.exports.runCli(process.argv.slice(2));
  process.exitCode=result;
})().catch(e=>{process.stderr.write(e.message+'\n');process.exitCode=1;});
