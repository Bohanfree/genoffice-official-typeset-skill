# 版式来源与校准

## 来源层次

2026-10-22 通过 REA 分析本机 WPS Office 12.1.28496。公文 AI 排版模块为 `kwpsaitypeset.framework`，静态证据显示其包含段落结构识别、模板选择、批量字体和段落设置、落款及版记处理。预置 AI 模板为编码文件，尚未取得对应模板参数。

本技能的基础参数取自另一个可读的 WPS 空白文档生成配置：

WPS 安装资源中的 `office6/addons/kwpsblankgenerate/theme/doc-config/doc-configs/official/general.json`（本技能仅记录所需参数，不分发 WPS 代码或资源）。

已读取的参数：正文仿宋_GB2312 16pt、28pt 固定行距、首行2字；页面 A4，上2097、下1984、左1587、右1474 twips（约37/35/28/26mm）；西文 Times New Roman；标题22pt。此处与 WPS AI 公文模板的具体对应关系待样稿校准。

以下为本技能的实现选择：短首段识别为标题；一级用黑体、二级用楷体、三级用仿宋；标题居中、段后28pt；落款和日期右对齐、右缩进2字。标题与后段保持同页，署名与日期保持同页。标题与正文使用独立 Word 样式，避免通用标题样式的默认加粗干扰。文本不重写、不删除已有空段。

## 段落类型

`--roles` 为 JSON 对象，键是 `docs read` 中 0 起始索引，值为以下一种：

```json
{"0":"title","1":"addressee","5":"heading1","12":"body","27":"signature","28":"date"}
```

可用值：`title`、`body`、`heading1`、`heading2`、`heading3`、`addressee`、`attachment`、`signature`、`date`、`blank`、`skip`。

只填写需要覆盖自动识别的段落。表格、图片等只允许 `skip`。标题自动识别仅选短首段；多段标题、副标题、正文中短编号句、附件正文起始、无机关后缀的署名应根据内容指定。原生自动编号列表保留结构，标题识别不把它们转换成普通标题。

## 字体

```json
{"title":"方正小标宋简体","body":"仿宋_GB2312","heading1":"黑体","heading2":"楷体_GB2312","latin":"Times New Roman"}
```

默认从已安装字体中依次选择，替代结果写进方案和核验文件：

| 用途 | 首选 | 本机可用备选 |
|---|---|---|
| 标题 | 方正小标宋简体 | 华文中宋、STZhongsong、Songti SC |
| 正文 | 仿宋_GB2312 | 仿宋、FangSong、STFangsong |
| 一级标题 | 黑体 | SimHei、Heiti SC |
| 二级标题 | 楷体_GB2312 | 楷体、KaiTi、STKaiti、Kaiti SC |
| 西文 | Times New Roman | Times |

字体应由用户正常安装。对照 WPS 时同时核对字体实际字形和名称，替代字体会改变断行与分页。

## 可校准参数

`--profile` 支持这些字段，未提供的字段沿用默认：

```json
{
  "bodySizePt":16,
  "titleSizePt":22,
  "lineHeightPt":28,
  "titleAfterPt":28,
  "firstLineChars":2,
  "signatureRightChars":2,
  "pageSetup":{
    "paper":"A4","orientation":"portrait",
    "margins":{"top":2097,"bottom":1984,"left":1587,"right":1474,"gutter":0},
    "columns":{"count":1}
  }
}
```

`pageSetup` 给完整对象，长度为 twips（1pt=20twips）或 GenOffice 支持的单位字符串。其他字段用数值。行高需容纳标题和正文字号。

## WPS 同文对照

1. 保留用户同一篇原文和 WPS 排版样稿，确定 WPS 版本、选用模板及实际字体。用 GenOffice 读取段落、样式与各节页面设置，并渲染两份用于比较。
2. 先对齐字体和字号，再对齐纸张、页边距、行距、段间距、缩进；每轮只修改相应的字体或版式配置。
3. 按页比较每段起止行、标题换行、每页末行、总页数和落款位置。两种排版引擎存在字距或分页差异时，记录具体页段，按样稿微调。
4. 红头、版记、签发人、联合署名等作为独立区域处理，依据实际样稿填写内容和位置。原稿未提供的要素保持缺省。
5. 保存最终配置及对照图，只有完成逐页检查后才说明该样稿的复刻程度；新模板再做一次样稿对照。

## 兼容性

桥接器核对安装的 CLI SHA-256 `db833cd5f39362a15e983d248b53155cc63eb82ee69f798827bdd4eaa60a86c0` 后，在内存中加载 GenOffice 原有引擎。只额外注册经过字段校验的 `setOfficialParagraphFormat`，并补足 `snapToGrid=false` 的导出；固定行距通过底层原生 `lineRule=exact`、`lineRawTwips` 写入。

应用更新后的校验失败需重新检查接口并更新桥接器。不要修改安装软件来绕过此检查，也不要直接把校验值换成新值而省略兼容性验证。
