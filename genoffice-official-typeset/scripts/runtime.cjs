// Locate a user-owned installation. No application code is bundled or modified.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const {spawnSync} = require('node:child_process');
const VERIFIED_SHA256 = 'db833cd5f39362a15e983d248b53155cc63eb82ee69f798827bdd4eaa60a86c0';

function resolveRuntime(env = process.env) {
  if (process.platform !== 'darwin') throw new Error('本版本支持 macOS；Windows / Linux 适配尚未验证。');
  const app = env.GENOFFICE_APP || ['/Applications/GenOffice.app', path.join(os.homedir(), 'Applications/GenOffice.app')].find(p => fs.existsSync(p));
  const runtime = env.GENOFFICE_RUNTIME || (app && path.join(app, 'Contents/MacOS/GenOffice'));
  const bundle = env.GENOFFICE_CLI || (app && path.join(app, 'Contents/Resources/cli/genoffice.cjs'));
  if (!runtime || !bundle || !fs.existsSync(runtime) || !fs.existsSync(bundle)) {
    throw new Error('未找到 GenOffice。请安装 0.11.919，或用 GENOFFICE_APP 指定 .app 路径；也可同时指定 GENOFFICE_RUNTIME 和 GENOFFICE_CLI。');
  }
  const sha256 = crypto.createHash('sha256').update(fs.readFileSync(bundle)).digest('hex');
  if (sha256 !== VERIFIED_SHA256) throw new Error('GenOffice CLI 版本与已验证的 0.11.919 不匹配。请先复核桥接器兼容性；不要仅替换校验值。');
  return {runtime: path.resolve(runtime), bundle: path.resolve(bundle), sha256};
}

function inventory() {
  // CoreText provides the same family names used by the local rendering engine.
  const swift = spawnSync('/usr/bin/swift', ['-e', 'import CoreText; import Foundation; let a = CTFontManagerCopyAvailableFontFamilyNames() as! [String]; print(String(data:try! JSONSerialization.data(withJSONObject:a),encoding:.utf8)!)'], {encoding:'utf8', maxBuffer:8*1024*1024, timeout:60000});
  if (swift.status === 0) {
    try { return new Set(JSON.parse(swift.stdout)); } catch {}
  }
  // A standard macOS fallback when Swift / Command Line Tools is unavailable.
  const profiler = spawnSync('/usr/sbin/system_profiler', ['SPFontsDataType', '-json'], {encoding:'utf8', maxBuffer:32*1024*1024, timeout:60000});
  if (profiler.status === 0) {
    try {
      const families = new Set();
      const walk = v => {
        if (!v || typeof v !== 'object') return;
        if (v.enabled === 'no' || v.valid === 'no') return;
        if (typeof v.family === 'string') families.add(v.family);
        for (const child of Object.values(v)) if (typeof child === 'object') walk(child);
      };
      walk(JSON.parse(profiler.stdout));
      if (families.size) return families;
    } catch {}
  }
  throw new Error('读取本机字体失败。请检查 macOS 字体册或 Command Line Tools 后重试。');
}

module.exports = {resolveRuntime, inventory, VERIFIED_SHA256};
