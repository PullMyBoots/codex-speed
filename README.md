# codex-speed

Add a live `tokens/s` status line to Codex CLI. Measure text, tool arguments, and exposed raw reasoning while preserving the native status line.

## Quick install

Send this to your current Codex:

> Install https://github.com/PullMyBoots/codex-speed into my current Codex. Read the repository's AGENTS.md first, complete the installation and verification, and preserve my model settings and login information.

Codex will clone the repository, check dependencies, run the installer, and verify the result. Once it finishes, **restart Codex**.

Or install manually:

```bash
git clone https://github.com/PullMyBoots/codex-speed.git
cd codex-speed
bash install.sh
```

After installation, run `codex-speed`. You can also keep using `codex` if `~/.local/bin` comes before other Codex installations in your PATH.

**The first installation builds a modified CLI.** Stock Codex lacks the external status line and streaming metrics interfaces this customization needs. This repository contains scripts and source patches; it does not bundle Codex, Node, or Rust. Installation downloads upstream source, Rust, and build dependencies, may take tens of minutes, and can use more than 20 GiB of disk space. An existing installation with the required native metrics support is reused without compilation.

## Display and labels

```text
Decode (think): ~128.3 t/s | Out: 2,048
Decode (tool): ~119.6 t/s  | Out: 2,048
Decode: ~123.8 t/s        | Out: 2,048
Decode (last): ~122.1 t/s | Out: 2,048
```

These are examples of the same speed line at different stages:

| Label | Meaning |
|---|---|
| `Decode` | The model is generating ordinary response text. |
| `Decode (tool)` | The model is generating tool arguments, such as a command or code. Tool execution time is excluded. |
| `Decode (think)` | The model is streaming raw reasoning exposed by the server. Hidden reasoning cannot be measured. |
| `Decode (last)` | No new valid measurement is available, so the latest valid result is retained. This does not mean the model is still generating, and it is not limited to the final reply. |
| `Summary` | The model is generating a reasoning summary, measured separately from raw reasoning. |
| `Decode (stopped)` / `Summary (stopped)` | Generation was interrupted; the retained measurement is shown. |

For example, a tool call with exposed reasoning may go through: `think` (generating reasoning) → `tool` (generating command arguments) → `last` (waiting for the tool) → `Decode` (generating the answer) → `last` (generation finished). If no valid sample exists yet, the waiting state shows `—`.

`t/s` means tokens per second. `Out` is cumulative output token usage, separate from the live speed measurement.

- Text, tool arguments, and exposed raw reasoning use the same measurement approach.
- First-token waiting, tool execution, and gaps between requests are excluded. While waiting, the latest valid result is retained with the `last` label.
- With incoming data, metrics are published at most once every 100 ms using an approximately one-second window. The terminal may combine refreshes.
- Reasoning summaries have their own `Summary` label and do not represent the full reasoning stream.
- `~` marks an estimate based on client-side tokenization and stream arrival times. OpenAI's hidden reasoning cannot be observed in real time. Model tokenizer differences, special tokens, and network buffering affect accuracy. This is not a measurement of server hardware throughput.

## Installation notes

- Requires Python **3.9+**, Git, and C/C++ build tools. Node/npm is not required. The installer installs Rust in your user directory if needed.
- Tested on Linux x86_64. A source build path is provided for macOS but has not been tested on a Mac. On Windows, use WSL2; there is no native Windows installer.
- Source ports are included for **0.160.0, 0.160.1, 0.161.0, 0.162.0, 0.162.1, and 0.163.0**. See the [compatibility and verification matrix](docs/COMPATIBILITY.md) for what has actually been tested. There is no Codex version allowlist: source metadata orders the patch candidates, and applicability checks decide which patch to use. Other tags are attempted without automatically downgrading. There are no startup version probes, and future releases are not automatically guaranteed compatible.
- Your existing `~/.codex` or `CODEX_HOME` is used. No author API keys, routing, or personal settings are copied. Your model selection, login information, native `/statusline` choices, proxy settings, and shell startup files are preserved.
- The modified CLI is installed in `~/.local/share/codex-speed`, build caches in `~/.cache/codex-speed`, and launchers in `~/.local/bin`. Existing launchers with the same names are backed up first. Original npm/native Codex binaries are preserved.
- Ordinary terminal launches use a private backend to load the native metrics events. Explicit `--remote` connections are preserved, but the remote backend must also support those events.

For dependencies, networking, source selection, and troubleshooting, see the [installation guide](docs/INSTALL.md) (Chinese). Complete instructions for AI coding assistants are in [AGENTS.md](AGENTS.md) (Chinese).

## Uninstall

```bash
~/.local/bin/codex-speed-uninstall
```

This restores the previous launchers and preserves your Codex configuration. If a managed launcher has been edited manually, the uninstaller stops to protect your changes. Build caches are retained separately; you can delete `~/.cache/codex-speed` when no longer needed.

## Development and verification

```bash
python3 -m unittest discover -s tests -v
bash install.sh doctor
```

The native implementation and its tests are in `patches/codex.patch`, with release-specific ports beside it; the installer handles the full build process. The patch includes bridge code adapted from [cxstatusline](https://github.com/adrijshikhar/cxstatusline). This repository's lightweight renderer uses only the Python standard library. See the [compatibility matrix](docs/COMPATIBILITY.md) for current checks and [VALIDATION.md](docs/VALIDATION.md) (Chinese) for the initial release validation.
