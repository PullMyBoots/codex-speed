# 给负责安装本项目的 Codex / AI 编码助手

用户说“把这个仓库安装到当前 Codex”时，请完成安装与验证，不要只把 README 或命令转述给用户。用户授权安装本项目的范围包括下载源码、安装用户目录中的 Rust 工具链、构建补丁与创建可恢复的启动入口；系统级依赖按所在环境的权限规则处理。

## 正常安装流程

1. 把本仓库 clone 到用户持久目录（例如 `~/.local/share/codex-speed-src`），并读 README.md 与 docs/INSTALL.md。不要把仓库放进用户无关的项目目录。
2. 运行 `bash install.sh doctor`。确认 Python 3.9+、Git、C/C++ 编译工具、make、pkg-config 与 OpenSSL 开发库。缺少系统依赖时按系统包管理器补齐；无法执行时明确报告缺少的依赖。
3. 在仓库目录运行 `bash install.sh`。有原生测速接口时自动复用；否则自动选择已安装 Codex 的源码版本、应用补丁、准备 Rust 和经校验的 V8、构建 CLI、创建启动入口。首次安装有大量下载和编译，持续执行到结束；构建日志出现警告不等于失败。
4. 安装器不执行 `codex --version` 来检查兼容性。版本来自原生包的 codex-package.json，仅用于选择源码标签。没有版本白名单或上限下限。补丁冲突是实际代码问题，不能解释为版本政策拒绝；不要偷偷切回 0.163.0。
5. 自动定位失败时，找到现有包目录并传入 `--codex-package PATH`。npm 安装通常位于 `npm root -g` 下的 `@openai/codex/node_modules/@openai/codex-*/vendor/*`，目录应含 codex-package.json、codex-path、codex-resources。可用 `--upstream-version VERSION` 明确选源码。
6. 构建/补丁失败时先解决实际报错并重试。源码是 0.163.0 以外的标签且补丁冲突时，可按仓库意图调整补丁并验证；不得移除真实测速改用会话平均耗时凑数。不得在失败时宣称安装完成。
7. 验证 `~/.local/bin/codex-speed --help` 成功，以及隔离样例能被轻量渲染器渲染：
   ```bash
   printf '%s\n' '{"stream_metrics":{"phase":"streaming","stream_kind":"tool","output_tps":42.5}}' | python3 render.py
   ```
   应显示 `Decode (tool): ~42.5 t/s`。确认安装状态存在、原启动入口已备份、模型/账户配置没有变化。若可使用本地模拟服务或伪终端，按 tests/test_terminal.py 验证 UI；不要为了安装验收调用付费模型。
8. 最后告诉用户安装位置、实际生效的启动命令和卸载命令，提醒重启现有 Codex。若 PATH 中别的 `codex` 在前，优先给 `codex-speed` 完整路径，不改写用户已有的自定义代理/启动脚本。

## 约束

- 不读取或输出用户 auth.json / API key；不要上传配置、日志、模型路由或会话。
- 不改 `~/.codex/config.toml`、CODEX_HOME、模型、reasoning effort、服务商、API base URL 或原生 statusline 配置。
- 不覆盖 npm/native 包原二进制。安装器的 ~/.local/bin 入口先备份；卸载可恢复。
- 不添加 Codex 兼容版本门槛、启动版本检测、自动降级、全局代理设置或后台常驻服务。
- 网络直连优先。若需要代理，用安装器 `--proxy URL`（只影响本次构建/下载），遵守用户已有网络偏好，不持久开启代理。
- 不提交 target、Cargo 缓存、二进制、大型安装包或个人安装状态。
- --from-build 用于复用已构建、包含原生测速接口的完整 package 布局；不是绕过原版 CLI 缺少接口的开关。

开发验证：`python3 -m unittest discover -s tests -v`。改原生补丁时，还应验证补丁可应用到目标上游并运行受影响的原生采样测试。无需为纯文档改动重复完整编译。
