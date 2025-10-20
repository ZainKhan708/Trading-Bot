# Trading-Bot

C++ starter kit for building algorithmic trading experiments. The project ships with a
modern CMake toolchain, reproducible development container, and continuous quality tooling to
jump-start development.

## Project layout

```
├── CMakeLists.txt         # Top-level build configuration
├── CMakePresets.json      # Configure, build, and test presets
├── cmake/Modules/         # Reusable CMake helper modules
├── include/trading_bot/   # Public library headers
├── src/                   # Library and executable sources
├── tests/                 # Catch2 unit tests
├── .githooks/             # Local git hooks (clang-format)
├── .devcontainer/         # VS Code / devcontainer configuration
└── Dockerfile             # Reproducible build environment
```

## Build

The repository is configured with CMake presets. The most common workflows are:

```bash
cmake --preset ninja-debug
cmake --build --preset ninja-debug
ctest --preset default
```

Additional presets enable sanitizers, coverage, or clang-tidy analysis:

- `asan`: AddressSanitizer build
- `ubsan`: UndefinedBehaviorSanitizer build
- `coverage`: Build with GCC/Clang coverage instrumentation
- `clang-tidy`: Runs clang-tidy during compilation

## Development container

Use VS Code Dev Containers or `devcontainer up` to open the project in the preconfigured
environment defined by `.devcontainer/devcontainer.json`. The container installs CMake,
Clang/LLVM tooling, and Ninja. After the container starts, git hooks are automatically wired
via `git config core.hooksPath .githooks`.

## Git hooks

Before committing, clang-format runs on staged C/C++ sources. If clang-format is not available
it prints a warning and continues. To enable the hook locally, run:

```bash
git config core.hooksPath .githooks
```

## Testing

Tests are powered by a lightweight Catch2-compatible harness and are executed through `ctest`.
A sample test covering the `compute_position_value` helper demonstrates the layout. Add new
tests under `tests/` and they will be picked up automatically.
