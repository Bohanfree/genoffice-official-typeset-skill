# 运行环境与排错

## 依赖

- macOS；已在 GenOffice 0.11.919、Node.js 22 上运行回归。脚本使用 Node.js 18+ 内置模块，无 npm 依赖。
- 用户自行安装的 GenOffice 0.11.919。技能不附带 GenOffice、WPS 或字体。
- WPS 实测模式所需字族见 [字体映射](wps-body-calibration.md)。字体由用户合法安装。
- 字体检测优先 CoreText/Swift，未配置 Swift 时回退到系统 `system_profiler`。
- Python 3 用于 WPS 实测模式的 OOXML 处理，仅使用标准库，无需安装第三方包。

执行 `node "<技能目录>/scripts/format-wps-body.mjs" --doctor` 检查路径、CLI 校验值、字体和替代结果。此命令不会创建文档或修改应用。

## 非默认安装位置

自动寻找 `/Applications/GenOffice.app` 和 `~/Applications/GenOffice.app`。也可在当前命令环境中设置：

```bash
GENOFFICE_APP="/其他位置/GenOffice.app" node "<技能目录>/scripts/format-wps-body.mjs" --doctor
```

精确覆盖可同时设置 `GENOFFICE_RUNTIME`（Electron 可执行文件）与 `GENOFFICE_CLI`（`genoffice.cjs` 完整路径）。路径支持空格。技能不写入 shell 配置。

## 兼容性校验

桥接器运行用户安装的引擎，在单独进程内注册经过校验的段落操作并补足固定行距导出。应用文件保持原样。

本版本要求 CLI SHA-256：

```
db833cd5f39362a15e983d248b53155cc63eb82ee69f798827bdd4eaa60a86c0
```

升级后校验失败应重新核对接口、文档导出与保真测试，再更新适配。不要只修改校验值。

## 常见问题

- **找不到 node**：安装 Node.js，并让客户端的命令执行环境能找到 `node`。
- **未找到 GenOffice**：检查安装位置，或设置 `GENOFFICE_APP`。
- **CLI 不匹配**：当前安装包与适配版本不同，需更新桥接器兼容性。
- **缺少字体**：实测模式安装 doctor 列出的实际字族；用户接受备选字体时，使用简化入口 `format-official.mjs --fonts`。
- **已有输出**：更换输出名称；预排方案也占用同一输出基名。
- **客户端没有本地命令能力**：在本机 Claude Code / WorkBuddy 中运行本技能。Claude 网页的远程运行环境无法直接使用本机安装的 GenOffice。
- **Windows / Linux**：本次发布只提供 macOS 已验证适配。
