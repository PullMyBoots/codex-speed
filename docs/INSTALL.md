# 安装与排错

普通用户只需把仓库链接交给 Codex，并要求“按 AGENTS.md 安装到当前 Codex”。以下内容供自动安装助手和手动安装者参考。

## 一条安装命令

仓库 clone 完成后：

```bash
bash install.sh
```

过程：定位现有 Codex 原生包 → 复用已有测速接口，或下载对应上游源码 → 实际应用补丁 → 准备 Rust 与经 SHA256 校验的 V8 → 构建 CLI 与 code-mode-host → 复制必要运行资源 → 备份命令入口并切换。模型、登录和原生状态栏选择沿用现有配置。

下载与编译发生在本机缓存中，不是仓库内隐藏了大型二进制。默认首次构建并不快：预留几十分钟、20 GiB 以上空间与可靠网络。当前原生补丁在 0.163.0 上验证；没有版本白名单，其他版本遇到代码冲突需要适配。

## 系统依赖

Python 3.9+、Git、C/C++ 工具链、make、pkg-config、OpenSSL 开发库；Rust 由脚本按上游 rust-toolchain.toml 安装，保存在 ~/.cargo / ~/.rustup，不修改 shell 启动文件。不需要 Node、npm、just、Bazel 或 cargo-nextest。

Ubuntu 24.04 / Debian 开发环境示例：

```bash
sudo apt-get update
sudo apt-get install -y python3 git build-essential pkg-config libssl-dev ca-certificates
```

macOS 需要 Xcode Command Line Tools、Python 3.9+、pkg-config 与 OpenSSL；例如通过 Homebrew 安装 `python pkg-config openssl@3`。macOS 尚未实机验收，遇到 Rust OpenSSL 探测问题可对本次安装设置 PKG_CONFIG_PATH 指向 Homebrew openssl@3 的 pkgconfig 目录。Windows 使用 WSL2 并按 Linux 步骤安装。

安装助手应先运行 `bash install.sh doctor`，必要时补齐依赖。不能使用系统包管理器时，应报告具体缺少的依赖，不反复要求用户逐条猜命令。

## 找不到当前 Codex 包

```bash
bash install.sh doctor
bash install.sh --codex-package /path/to/native/package
```

目录需包含 `codex-package.json`、`codex-path/`、`codex-resources/`。npm 版一般在：

```text
$(npm root -g)/@openai/codex/node_modules/@openai/codex-<platform>/vendor/<target>/
```

codex-package.json 中的版本仅用于选择源码标签，不用于兼容范围判定。安装程序不执行现有 Codex 的 --version。若自定义入口隐藏了真实包，安装助手应定位真实原生目录并显式传参。即使指定 --upstream-version，也需要现有包提供运行资源。

## 网络慢或 GitHub 无法连接

直连是默认方式。可只为本次构建与下载指定代理：

```bash
bash install.sh --proxy http://127.0.0.1:7890
```

不改变用户全局代理，不修改 API 服务商配置；安装阶段不请求用户的模型 API。已有 CARGO_HOME、CARGO_TARGET_DIR 的处理：保留 CARGO_HOME，构建 target 统一位于本安装缓存的 target/，避免污染当前项目。

## 更新与重试

```bash
git pull --ff-only
bash install.sh
```

已有测速 CLI 会复用。需要显式为另一个上游源码标签构建时：

```bash
bash install.sh --upstream-version 0.163.0 --codex-package /path/to/installed/package
```

这只是来源选择，非“允许版本列表”。不会自动换成旧版本绕过补丁冲突。构建失败后，Rust/Cargo/V8 缓存保留以便重试；未完成构建前不替换启动入口。日志中 `warning:` 不等于构建失败，最终应看退出状态与 `Installed` 提示。

## 已有构建，跳过重复编译

```bash
bash install.sh --from-build /path/to/patched/package
```

仅适用于已有原生测速接口的完整 package 布局，通常有 `bin/codex`、`bin/codex-code-mode-host`、codex-package.json 与运行资源。脚本检查实际能力标记，不检查 Codex 兼容版本。不能用这个参数给原版 Codex 凭空补出接口。

## 启动与 PATH

```bash
~/.local/bin/codex-speed
```

安装器还会提供 ~/.local/bin/codex，已有同名文件或符号链接先备份。若系统中的别的 codex 排在 PATH 前面，使用 codex-speed 或其完整路径即可；不会自动修改 shell 配置。原来的 npm/native 安装文件不会改动。

可选：

```bash
bash install.sh --no-codex-link
bash install.sh --prefix /custom/data --bin-dir /custom/bin
bash install.sh --jobs 2
```

`--no-codex-link` 仅创建 codex-speed 与卸载入口。更低 jobs 可降低内存使用。自定义路径支持空格和单引号。

## 验证

```bash
~/.local/bin/codex-speed --help
printf '%s\n' '{"stream_metrics":{"phase":"streaming","stream_kind":"tool","output_tps":42.5}}' | python3 render.py
```

第二条应输出 `Decode (tool): ~42.5 t/s`。真实 UI 验证应使用本地模拟流，避免为了验收请求付费模型。

首 token 后不足 100 ms 或单个缓冲 chunk 无法测速；没有历史值时显示 `—`。网络停顿仍会影响同一流区间的客户端计时，不能将其解释为精确 GPU decode 时间。官方隐藏推理不可观测，思考摘要显示 `Summary`。

## 卸载

```bash
~/.local/bin/codex-speed-uninstall
```

恢复原始命令入口，删除该安装器管理的运行目录。用户 Codex 配置和构建缓存保留。若入口已被手动修改，卸载会在删除前停止并指出具体文件；先保存改动，再恢复该受管入口或手动处理。
