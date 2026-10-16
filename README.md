# codex-speed

给 Codex CLI 加上实时 `tokens/s` 状态栏。原生状态栏保留，工具调用、正文和可见原始思考都能测速。

## 最简单的安装方式

把下面这句话发给你正在使用的 Codex：

> 帮我把 https://github.com/PullMyBoots/codex-speed 安装到当前 Codex。请先读仓库的 AGENTS.md，按说明完成安装和验证，保留我的模型配置与登录信息。

Codex 会负责下载仓库、检查依赖、运行安装脚本并验证。你最后只需要**重启 Codex**。

也可以自己运行：

```bash
git clone https://github.com/PullMyBoots/codex-speed.git
cd codex-speed
bash install.sh
```

安装完成后运行 `codex-speed`；若 `~/.local/bin` 在 PATH 前面，也可继续运行 `codex`。

**首次安装需要编译修改后的 CLI，并非只写一行配置。** 原版 Codex 没有我们需要的外接状态栏与逐段测速接口。仓库只有脚本和源码补丁，不捆绑 Codex、Node 或 Rust；安装时会下载上游源码、Rust 和构建依赖，可能耗时几十分钟，占用 20 GiB 以上磁盘空间。有原生测速接口的已安装版本会直接复用，跳过编译。

## 显示效果

```text
Decode (think): ~128.3 t/s | Out: 2,048
Decode (tool): ~119.6 t/s  | Out: 2,048
Decode: ~123.8 t/s        | Out: 2,048
Decode (last): ~122.1 t/s | Out: 2,048
```

- 同一测速口径覆盖正文、工具参数和服务端流出的原始思考。
- 等待首 token、工具执行、请求间隔不计时；等待时保留最近一次有效值并标记 `last`。
- 有数据时最多每 100 ms 发布一次，使用约 1 秒窗口；终端可能合并刷新。
- 思考摘要单独显示为 `Summary`，不冒充完整推理速度。
- `~` 是客户端分词与网络时间估算。官方隐藏推理无法实时观测；不同模型 tokenizer、特殊 token、网络缓冲均影响准确性。它不是服务端硬件计时。

## 安装说明

- Python **3.9+**、Git、C/C++ 构建工具。无需 Node/npm。Rust 缺失时由脚本安装到用户目录。
- 已验证 Linux x86_64。macOS 提供源码构建路径，尚未实机验证；Windows 请用 WSL2，未提供原生 Windows 安装器。
- 不设 Codex 版本白名单，不按版本范围拒绝安装；补丁基于 **0.163.0**。其他源码标签会实际尝试应用补丁，冲突时给出错误，不自动降级。没有启动时版本探测。
- 继续使用你的 `~/.codex` 或 `CODEX_HOME`。不复制作者的 API key、路由或个人配置，不修改模型选择、登录信息、原生 `/statusline` 选择、代理或 shell 启动文件。
- 修改版 CLI 放在 `~/.local/share/codex-speed`，构建缓存放在 `~/.cache/codex-speed`，启动入口放在 `~/.local/bin`。已有同名入口先备份，原来的 npm/native Codex 二进制保留。
- 普通终端启动使用独立后端，以载入本包原生事件；显式 `--remote` 保留，但远端后端也需支持测速事件。

依赖安装、网络、源码选择和常见问题见 [详细安装说明](docs/INSTALL.md)。给 AI 编码助手的完整执行步骤见 [AGENTS.md](AGENTS.md)。

## 卸载

```bash
~/.local/bin/codex-speed-uninstall
```

恢复安装前的命令入口，保留 Codex 配置。启动脚本若被手动修改，卸载器会停止，避免覆盖你的改动。构建缓存单独保留，可在确认不再需要后删除 `~/.cache/codex-speed`。

## 维护与验证

```bash
python3 -m unittest discover -s tests -v
bash install.sh doctor
```

原生实现及测试在 `patches/codex.patch`，完整构建方法由安装器实现。补丁使用了 [cxstatusline](https://github.com/adrijshikhar/cxstatusline) 的桥接代码；本仓库的轻量渲染器只依赖 Python 标准库。首次发布的验证范围见 [VALIDATION.md](docs/VALIDATION.md)。
