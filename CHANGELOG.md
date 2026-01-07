# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
