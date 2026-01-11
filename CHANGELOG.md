# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.3](https://github.com/dedalus-labs/wingman/compare/v0.4.2...v0.4.3) (2026-01-11)


### Bug Fixes

* remove redundant api key prefix validation ([25e3476](https://github.com/dedalus-labs/wingman/commit/25e34766d0f02b0a2a0509275c9aa15744bb6943))

## [0.4.2](https://github.com/dedalus-labs/wingman/compare/v0.4.1...v0.4.2) (2026-01-09)


### Bug Fixes

* filter servers by featured status ([28737d0](https://github.com/dedalus-labs/wingman/commit/28737d0f66423d87dacab5d280c34a0322ceec0c))
* filter servers by featured status ([#14](https://github.com/dedalus-labs/wingman/issues/14)) ([7e468f7](https://github.com/dedalus-labs/wingman/commit/7e468f79b1fc445de9f34f9002283639fc9352e7))

## [0.4.1](https://github.com/dedalus-labs/wingman/compare/v0.4.0...v0.4.1) (2026-01-09)


### Bug Fixes

* remote bulletin fetching logic ([bf621c1](https://github.com/dedalus-labs/wingman/commit/bf621c19468c0c4311ab332629a559e4956d4d44))

## [0.4.0](https://github.com/dedalus-labs/wingman/compare/v0.3.0...v0.4.0) (2026-01-09)


### Features

* add bulletin system for dynamic messaging ([a6de824](https://github.com/dedalus-labs/wingman/commit/a6de8248769198a01584b94d69a56710c5936c94))
* launch ([#12](https://github.com/dedalus-labs/wingman/issues/12)) ([d8125d2](https://github.com/dedalus-labs/wingman/commit/d8125d2052f7299fc786a21253cab8fde1f0a6e7))
* **lib:** orjson for faster JSON ([7ed5fe0](https://github.com/dedalus-labs/wingman/commit/7ed5fe05b184beea2bef4efbfbbfcdc9aa63aa44))
* MCP modal, model updates, backgrounding fixes, AGENTS.md fixes ([27fb934](https://github.com/dedalus-labs/wingman/commit/27fb93401c5504face8f7d4e379389c5915da0ff))
* **memory:** add delete confirmation step ([9ea5fbc](https://github.com/dedalus-labs/wingman/commit/9ea5fbce23c43fc8a4f91e6ae4cf21736745ca78))
* **memory:** redesign with JSON structure, ephemeral info ([a931c7d](https://github.com/dedalus-labs/wingman/commit/a931c7d75430f75023a73c3164771363153e2d04))
* tab to autocomplete, mcp remove ([7abf768](https://github.com/dedalus-labs/wingman/commit/7abf76818fe10d1e71969ed1cbc0da259f60aebb))
* **ui:** add command completion ([42c584a](https://github.com/dedalus-labs/wingman/commit/42c584ace34566c0d7d2417538c4fe81fde8e510))
* **ui:** add quit hint and /exit ([b4761e8](https://github.com/dedalus-labs/wingman/commit/b4761e8d7fed047d96a3f220a8f1136501e00606))
* **ui:** cycle tab completions ([ac4295d](https://github.com/dedalus-labs/wingman/commit/ac4295dab48ccb814f24b8f559e706980b106b19))
* **ui:** improve UX with double-tap quit, list scroll, and click-to-focus ([f9ab77c](https://github.com/dedalus-labs/wingman/commit/f9ab77cd3b1147b5ac466ccdd08729eff28cae80))


### Bug Fixes

* cancel gen behavior; tool approval focus; prefix paste; display on reenter; list / rem mcps ([29f4b92](https://github.com/dedalus-labs/wingman/commit/29f4b92e3bd182b56e94888c55f59f905a18ed9c))
* Gemini tool streaming; scrollbar/focus UI styling; image drag-drop; context limits; paste handling ([31ecfb6](https://github.com/dedalus-labs/wingman/commit/31ecfb69f88fea49f9e04108200c264dfb3fdb2f))
* **ui:** allow q to close modals ([805fd8d](https://github.com/dedalus-labs/wingman/commit/805fd8d577d253504ab5075c07d9c28eb456961b))
* **ui:** hide thinking spinner during tool approval ([ebb0a26](https://github.com/dedalus-labs/wingman/commit/ebb0a26b50dc4ec3a41a33c72192d97bd389194d))

## [0.3.0](https://github.com/dedalus-labs/wingman/compare/v0.2.2...v0.3.0) (2026-01-07)


### Features

* headless cli (-p flag); terminal-bench benchmarking support ([840276c](https://github.com/dedalus-labs/wingman/commit/840276ce911035a03cad5cdbf1884418728da9c1))
* pass tool outputs to context; remove max_steps limit; escape to cancel generation and clear input; collapse long pastes; update SelectionModal theme ([b8118aa](https://github.com/dedalus-labs/wingman/commit/b8118aaf63567fcac89b96a79b92257e8cbd671a))
* **tools:** fd/rg file ops, read_file pagination, escape fixes ([63144f9](https://github.com/dedalus-labs/wingman/commit/63144f9074d2c54f3c1598b88d4551323a3c49c4))


### Bug Fixes

* **ui:** spacing, edit rejection loop, system prompt updates ([082b853](https://github.com/dedalus-labs/wingman/commit/082b853b63175730dfe3029efff57e27158ad784))

## [0.2.2](https://github.com/dedalus-labs/wingman/compare/v0.2.1...v0.2.2) (2025-12-23)


### Bug Fixes

* remove failed message from history to prevent resending ([01480ee](https://github.com/dedalus-labs/wingman/commit/01480eec1ebc68a98615740e7fa951dc22777ae8))

## [0.2.1](https://github.com/dedalus-labs/wingman/compare/v0.2.0...v0.2.1) (2025-12-22)


### Bug Fixes

* **input:** preserve multi-line clipboard content on paste ([4f6c652](https://github.com/dedalus-labs/wingman/commit/4f6c652cd6288e0cdf649f1e97bdb4a9f01e9c7b))
* use plain text logo for universal terminal compatibility ([a279be5](https://github.com/dedalus-labs/wingman/commit/a279be5d76fded27def27b6333e86e6360486eb7))

## [0.2.0](https://github.com/dedalus-labs/wingman/compare/v0.1.0...v0.2.0) (2025-12-22)


### Features

* add tool approval prompts before command execution ([2eca942](https://github.com/dedalus-labs/wingman/commit/2eca942c938ac7d217b7ecb83863bdcf30424a9f))
* concurrent multi-panel isolation with per-session state partitioning ([dafd566](https://github.com/dedalus-labs/wingman/commit/dafd566a6dbf83e24c3266497cc88d94fc86a5b9))
* segment-based message serialization for stateful UI hydration; multimodal input pipeline with async image caching and platform-specific path normalization; PyPI distribution scaffolding with release-please CI/CD ([590e25f](https://github.com/dedalus-labs/wingman/commit/590e25f8612c84f2fb0a46248ad58bfd4658312b))
* **ui:** show command output preview in status widgets ([468c9b3](https://github.com/dedalus-labs/wingman/commit/468c9b33f9e1b422c7ab6b503147fcd0e2056b09))
* **ui:** streaming text via Static.update() with persistent bottom spinner ([4f4cbfd](https://github.com/dedalus-labs/wingman/commit/4f4cbfd8236f6acb416f1610cb28e8c87d070be6))


### Bug Fixes

* use timestamp-based widget IDs to prevent collisions ([b3914cf](https://github.com/dedalus-labs/wingman/commit/b3914cf893832ce647300b84d59507379444891b))


### Documentation

* update commands, remove keyboard shortcuts section ([236bd78](https://github.com/dedalus-labs/wingman/commit/236bd783cfdc727e75931268cf16b94c24de4b50))

## [0.1.0] - 2024-12-22

### Added

- Initial public release
- Multi-model support: OpenAI, Anthropic, Google, xAI, Mistral, DeepSeek
- Coding tools: file read/write, shell commands, grep with diff previews
- MCP (Model Context Protocol) server integration
- Split panel support for multiple conversations
- Automatic checkpoints with rollback capability
- Project memory persistence per directory
- Image attachment and analysis
- Context management with auto-compaction
- Session import/export (JSON and Markdown)
- Customizable keyboard shortcuts
