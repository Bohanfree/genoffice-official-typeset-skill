# 公文排版 Skill

给 **Claude Code、WorkBuddy** 使用的独立技能：把未排版文章或现有 Word 文档排成可编辑的中文公文，保留原文并附排版方案、核验结果和预览。

技能文件夹为 [`genoffice-official-typeset/`](genoffice-official-typeset/)。采用标准 `SKILL.md`，两个客户端使用同一个完整文件夹。

## 运行条件

**macOS + Node.js 18+ + GenOffice 0.11.919**。无需 npm 包、API Key 或 WPS。GenOffice 和字体由使用者自行安装。

这是依赖本地文档引擎的技能，适用于能执行本地命令的 Claude Code、WorkBuddy。Claude 网页远程环境无法直接调用本机 GenOffice。本次发行的引擎适配已在 macOS 验证。

## 安装

下载 [最新发布包](https://github.com/Bohanfree/genoffice-official-typeset-skill/releases/latest)，解压后将整个 `genoffice-official-typeset` 文件夹放入对应客户端的 skills 目录，保留内部的 scripts、references、examples。

| 客户端 | 安装位置 |
|---|---|
| Claude Code | `~/.claude/skills/genoffice-official-typeset/` |
| WorkBuddy | `~/.workbuddy/skills/genoffice-official-typeset/` |

也可以克隆仓库后安装。以下命令在目标已存在时停止，防止覆盖已有技能：

```bash
git clone https://github.com/Bohanfree/genoffice-official-typeset-skill.git
cd genoffice-official-typeset-skill
```

Claude Code：

```bash
mkdir -p "$HOME/.claude/skills"
test ! -e "$HOME/.claude/skills/genoffice-official-typeset" && cp -R genoffice-official-typeset "$HOME/.claude/skills/"
node "$HOME/.claude/skills/genoffice-official-typeset/scripts/format-official.mjs" --doctor
```

WorkBuddy：

```bash
mkdir -p "$HOME/.workbuddy/skills"
test ! -e "$HOME/.workbuddy/skills/genoffice-official-typeset" && cp -R genoffice-official-typeset "$HOME/.workbuddy/skills/"
node "$HOME/.workbuddy/skills/genoffice-official-typeset/scripts/format-official.mjs" --doctor
```

重新开启客户端会话以加载技能。Claude Code 可输入 `/genoffice-official-typeset`，或直接描述排版任务；WorkBuddy 可在技能列表选择“genoffice-official-typeset”，再提供文件和排版要求。

Claude Code 的目录规则参见 [官方 Skills 文档](https://code.claude.com/docs/en/skills)。WorkBuddy 目录与本机现有用户技能目录核对过；本次验证覆盖独立脚本和打包，不包含两个客户端内的实际对话触发。

## 使用

把文件交给客户端并说：

> 用公文排版技能处理这篇通知，保留原文，另存 Word，并检查分页和落款。

独立命令也可使用，在仓库根目录运行：

```bash
node genoffice-official-typeset/scripts/format-official.mjs --doctor
node genoffice-official-typeset/scripts/format-official.mjs genoffice-official-typeset/examples/通知原文.txt --out ./output/通知.docx --render
```

成功后输出：

- `通知.docx`：可编辑文档。
- `通知.排版方案.json`：段落识别、字体、版式及操作计划。
- `通知.排版核验.json`：文字保留、原文与引擎文件未变等检查结果。
- `通知.预览/`：预览 PNG（使用 `--render` 时）。

`--plan-only` 仅生成方案；`--roles` 修正段落类型，`--fonts` 指定已安装字体，`--profile` 调整版式。已有输出会被保护，预排与正式排版请使用不同输出名。[详细配置](genoffice-official-typeset/references/layout-and-calibration.md) · [依赖与排错](genoffice-official-typeset/references/runtime.md)。

## 默认版式

| 项目 | 设置 |
|---|---|
| 页面 | A4；上37、下35、左28、右26mm（约值） |
| 标题 | 22pt、居中 |
| 正文 | 16pt、仿宋、固定行距28pt、首行2字 |
| 层级标题 | 一级黑体、二级楷体、三级仿宋 |
| 落款与日期 | 右对齐、右缩进2字 |
| 保真 | 保留文字、空段、重复空格、表格和原有自动编号 |

字体缺失时从本机已安装备选字体中选择，并在结果中记录。指定但未安装的字体会报错。

基础参数参考 WPS 可读的公文生成配置，属于“公文主体模板”。完全复刻特定 WPS 模板需要同文样稿和相同字体逐页校准。红头、版记、签发人、印章等按用户真实样稿另作布局。

## 示例效果

仓库自带虚构通知示例的实际渲染如下。本次使用本机备选字体 Songti SC、STFangsong、Heiti SC、STKaiti；西文为 Times New Roman。

![通知排版示例](docs/preview.png)

## 验证与开发

无运行时第三方包。规则模块为原始共享引擎，提取后保留版式逻辑；独立运行层增加安装位置发现、字体检测回退和环境自检。桥接器仅在进程内补足引擎接口，不改应用安装文件。

```bash
node tests/core.test.mjs
python3 tests/integration.py
```

集成测试需要上述本机依赖与 Python 3，使用虚构样例，覆盖含空格的技能路径、逐字保留、DOCX 表格与编号、固定行距、禁止覆盖及版本不匹配的停止行为。所有测试产物位于系统临时目录。

## 授权与数据

自有技能说明与代码采用 MIT 许可证。GenOffice、WPS 与字体属于各自权利人，本仓库不分发其程序或资源，也无官方关联。

排版脚本不调用 AI API 或主动发送文档；客户端自身的文件上传和模型服务按其设置运行。方案与核验 JSON 可能包含原文和本地路径，分享时按原文同等方式处理。
