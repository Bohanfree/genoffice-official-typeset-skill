# 公文排版 Skill

**当前为 v1.1.0-beta.2 实测校准版**：WPS「公文主体」规则已提取，新增 GenOffice 0.12.29 适配；视觉差异与对照图见 [验收记录](docs/wps-calibration.md)。

给 **Claude Code、WorkBuddy** 使用的独立技能：把未排版文章或现有 Word 文档排成可编辑的中文公文，保留原文并附排版方案、核验结果和预览。

技能文件夹为 [`genoffice-official-typeset/`](genoffice-official-typeset/)。采用标准 `SKILL.md`，两个客户端使用同一个完整文件夹。

## 运行条件

**macOS + Node.js 18+ + Python 3 + GenOffice 0.11.919 或 0.12.29**。无需 npm 包、Python 第三方包或 API Key。日常排版无需启动 WPS；GenOffice 和字体由使用者自行安装。

这是依赖本地文档引擎的技能，适用于能执行本地命令的 Claude Code、WorkBuddy。Claude 网页远程环境无法直接调用本机 GenOffice。本次发行的引擎适配已在 macOS 验证。

## 安装

下载 [实测校准版发布包](https://github.com/Bohanfree/genoffice-official-typeset-skill/releases/tag/v1.1.0-beta.2)，解压后将整个 `genoffice-official-typeset` 文件夹放入对应客户端的 skills 目录，保留内部的 scripts、references、assets、examples。

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
node "$HOME/.claude/skills/genoffice-official-typeset/scripts/format-wps-body.mjs" --doctor
```

WorkBuddy：

```bash
mkdir -p "$HOME/.workbuddy/skills"
test ! -e "$HOME/.workbuddy/skills/genoffice-official-typeset" && cp -R genoffice-official-typeset "$HOME/.workbuddy/skills/"
node "$HOME/.workbuddy/skills/genoffice-official-typeset/scripts/format-wps-body.mjs" --doctor
```

重新开启客户端会话以加载技能。Claude Code 可输入 `/genoffice-official-typeset`，或直接描述排版任务；WorkBuddy 可在技能列表选择“genoffice-official-typeset”，再提供文件和排版要求。

Claude Code 的目录规则参见 [官方 Skills 文档](https://code.claude.com/docs/en/skills)。WorkBuddy 目录与本机现有用户技能目录核对过；本次验证覆盖独立脚本和打包，不包含两个客户端内的实际对话触发。

## 使用

把文件交给客户端并说：

> 用公文排版技能处理这篇通知，保留原文，另存 Word，并检查分页和落款。

独立命令也可使用，在仓库根目录运行：

```bash
node genoffice-official-typeset/scripts/format-wps-body.mjs --doctor
node genoffice-official-typeset/scripts/format-wps-body.mjs genoffice-official-typeset/examples/通知原文.txt --out ./output/通知.docx --render
```

成功后输出：

- `通知.docx`：可编辑文档。
- `通知.排版方案.json`：段落识别、字体、版式及操作计划。
- `通知.排版核验.json`：文字保留、原文与引擎文件未变等检查结果。
- `通知.预览/`：预览 PNG（使用 `--render` 时）。

`--plan-only` 仅生成方案；`--roles` 修正段落类型。已有输出会被保护，预排与正式排版请使用不同输出名。

## WPS 公文主体

推荐入口 `format-wps-body.mjs` 使用 **WPS Office 12.1.28496 实际执行「公文主体」后的规则**。提取版式后，再处理 GenOffice 的字体别名、样式继承与页码定位兼容问题。预览直接渲染最终交付的 DOCX。

| 项目 | 实测版式 |
|---|---|
| 页面 | A4；上2098、下1984、左1587、右1474 twips |
| 标题 | 22pt、居中、固定36pt行距；之后留15pt空段 |
| 正文 | 仿宋16pt、固定28pt行距、首行2字、字距−0.3pt |
| 层级标题 | 一级黑体、二级楷体、三级仿宋，均16pt |
| 附件 | 前留空段，悬挂缩进 |
| 落款与日期 | 使用模板实测的右对齐与缩进 |
| 页码 | 动态PAGE字段，奇右偶左，“— 1 —” |
| 原文 | 保留文字、空格、原有空段、表格和自动编号 |

脚本识别 WPS 此次实际使用的字族（包括汉仪书宋二KW、汉仪中黑KW、汉仪楷体简、仿宋_GB2312）。缺少所需字体时，`--render` 会停止并列明缺项，避免用替代字体完成同字体验收。字体由使用者合法安装，发布包不附字体。

[全部实测参数与字体映射](genoffice-official-typeset/references/wps-body-calibration.md) · [同文对照及当前验收结果](docs/wps-calibration.md) · [运行环境](genoffice-official-typeset/references/runtime.md)。

旧的简化排版入口 `format-official.mjs` 仍保留，支持 `--fonts`、`--profile` 自定义及备选字体。它与实测 WPS 模式是两个入口。[简化模式配置](genoffice-official-typeset/references/layout-and-calibration.md)。红头、签发人、版记、印章等按具体样稿另行适配。

## 示例效果

仓库中的虚构通知，使用 WPS 实际字族，在 GenOffice 渲染最终 DOCX：

![通知排版示例](docs/preview.png)

## 验证与开发

无运行时第三方包。共享识别引擎生成段落方案，Python 标准库覆盖实测版式并做 GenOffice 兼容处理。运行层检查安装位置、引擎版本与字体；桥接器仅在进程内补足接口，应用安装文件保持原样。

```bash
node tests/core.test.mjs
python3 tests/integration.py
python3 tests/wps_overlay.py
```

集成测试需要上述本机依赖与 Python 3，使用虚构样例，覆盖含空格的技能路径、逐字保留、DOCX 表格与编号、固定行距、禁止覆盖及版本不匹配的停止行为。所有测试产物位于系统临时目录。

设置 `OFFICIAL_TEST_ROOT` 可将集成测试临时目录放在指定磁盘，以检查保存到外置硬盘的行为。WPS 实测模式也覆盖原文保留、实际渲染、模板空段和动态奇偶页码。

## 授权与数据

自有技能说明与代码采用 MIT 许可证。GenOffice、WPS 与字体属于各自权利人，本仓库不分发其程序或资源，也无官方关联。

排版脚本不调用 AI API 或主动发送文档；客户端自身的文件上传和模型服务按其设置运行。方案与核验 JSON 可能包含原文和本地路径，分享时按原文同等方式处理。
