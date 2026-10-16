# Compatibility and verification

The maintenance target starts at **Codex 0.160.0**. This is a target for ongoing porting and testing, not a promise that every future release will work unchanged. Alpha releases are not covered by the stable-release matrix below.

## Source ports

| Codex release | Source patch | Clean upstream application and lock metadata |
|---|---|---|
| 0.160.0 | `patches/codex-0.160.0.patch` | Passed |
| 0.160.1 | `patches/codex-0.160.1.patch` | Passed |
| 0.161.0 | `patches/codex-0.161.0.patch` | Passed |
| 0.162.0 | `patches/codex-0.162.0.patch` | Passed |
| 0.162.1 | `patches/codex-0.162.1.patch` | Passed |
| 0.163.0 | `patches/codex.patch` | Passed |

Each patch has been checked against the clean official Git tag using an isolated Git index. The patched lockfile's `codex-core` version is checked against the actual source release. Patch application alone does **not** prove compilation, correct runtime behavior, or support for another operating system.

The 0.160 and 0.161 ports preserve the older composer method layout; they do not copy unrelated later-version footer methods into older source. The 0.160 ports also retain their original handling of MCP login notifications. All ports carry the same decode tracker and preserve the distinction between raw reasoning and summaries.

The 0.161.0 and 0.162.x ports raise the compiler's crate recursion limit to 256 to accommodate nested async tool-handler layout queries. This addresses a compile-time depth overflow and does not change tool execution or sampling behavior.

## Build and native runtime verification

Validation environment: Linux x86_64, Rust 1.95.0. A full release build of both `codex` and `codex-code-mode-host` passed for **0.160.0**. The original **0.163.0** package was also fully built and passed the checks described in [VALIDATION.md](VALIDATION.md).

| Codex release | CLI compilation verification | Full CLI + host release build | Installer + native PTY test |
|---|---|---|---|
| 0.160.0 | Passed through full build | Passed | Passed |
| 0.160.1 | `cargo check` passed | Not run | Not run |
| 0.161.0 | `cargo check` passed | Not run | Not run |
| 0.162.0 | `cargo check` passed | Not run | Not run |
| 0.162.1 | `cargo check` passed | Not run | Not run |
| 0.163.0 | Passed through full build | Passed | Passed |

The intermediate ports are checked with:

```bash
cargo +1.95.0 check --release --locked -j 32 -p codex-cli
```

This checks the CLI and its dependencies, including the native TUI and app-server. It does not link runnable binaries or run native tests for those intermediate releases. Each port also runs upstream `just fmt`.

The 0.160.0 package passed the actual installer, launcher, native TUI, and uninstall test with a local synthetic Responses SSE server. The test observed all four streams (text, tool arguments, raw reasoning, and summary), retained the last valid speed during buffered requests, and kept the native status line on a separate row at both 83 and 120 columns. A synthetic 40 tokens/s text stream measured **39.41 tokens/s**, with 37 valid live samples overall and a 100 ms publication interval. Waiting, tool execution, and summary time were excluded from decode timing. These numbers validate the measurement behavior; they are not a real model benchmark.

All eight tests in the unchanged decode tracker also passed when compiled directly against the release dependencies. This targeted check does not represent the complete upstream Rust test suite. No paid model calls were made.

macOS, native Windows, and WSL2 have not been independently validated. The current installer supports Linux/macOS source builds and Windows through WSL2; it does not provide a native Windows installation path. Adding older source ports does not remove the cost of the first source build or create prebuilt release downloads.

## Selection and updates

The installer reads source metadata to prefer a patch with matching dependency lock versions, then checks actual applicability. There is no minimum/maximum Codex version rejection and no startup `codex --version` probe. Unknown source tags still try the available patches; real conflicts are reported and no automatic downgrade is performed.

The CI source matrix checks the six stable tags above on every push and pull request. It does not compile Rust or establish native platform support. New release support requires source checks plus appropriate build and runtime verification before being marked as tested.

## Local checks

```bash
python3 -m unittest discover -s tests -v
python3 install.py --check-source /path/to/clean/codex/source
```

The Python suite includes real Git application/retry/conflict checks and verifies that unknown source releases are not rejected by a version allowlist. The opt-in native test accepts any patched package's own version metadata:

```bash
python3 -m pip install -r tests/requirements.txt
CODEX_SPEED_TEST_PACKAGE=/path/to/patched/package \
  python3 -m unittest discover -s tests -p test_terminal.py -v
```

The synthetic server runs locally; installation validation does not call a paid model API.
