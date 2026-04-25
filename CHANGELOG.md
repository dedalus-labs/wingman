# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0](https://github.com/dedalus-labs/wingman/compare/v0.4.3...v0.5.0) (2026-04-25)


### Features

* add BASE_URL env var for custom API endpoints ([#29](https://github.com/dedalus-labs/wingman/issues/29)) ([a9d74f5](https://github.com/dedalus-labs/wingman/commit/a9d74f5e94923bb7fb4233b08e948b2efd2e30e5))
* add install.sh for one-line uv-based installation ([100b02b](https://github.com/dedalus-labs/wingman/commit/100b02b90ef29ec654d441e6f329b9e0a831471f))
* add WINGMAN_BASE_URL env var for custom API endpoints ([4c5b6ba](https://github.com/dedalus-labs/wingman/commit/4c5b6ba70e6aa18adf2c8e3b2dea1ca79c601afb))
* **config:** add /base_url command with first-launch prompt ([2936bb5](https://github.com/dedalus-labs/wingman/commit/2936bb5dfea74dea9de37024fa5983b1dc0b39df))
* **release:** publish to pypi and update homebrew on release ([ab0b425](https://github.com/dedalus-labs/wingman/commit/ab0b4257731e86857ee3a7099954a3f965675642))
* **sessions:** add conversation forking with /fork command ([289f5bb](https://github.com/dedalus-labs/wingman/commit/289f5bb2b994503942716eaf0cb919a99601da10))
* **ui:** add ForkPickerModal for point-in-history forking ([2d31773](https://github.com/dedalus-labs/wingman/commit/2d3177324fc70e0896924be35cb93d2fcb734e69))
* **ui:** add inline branch markers for fork lineage ([66ebb5b](https://github.com/dedalus-labs/wingman/commit/66ebb5bd23631c5604d6acb70009b9531d0bfbce))
* **ui:** fork picker splits rewrite vs continue by role ([baf3820](https://github.com/dedalus-labs/wingman/commit/baf3820c750234ef15554044085537eafebd6b45))
* **ui:** show Loading models indicator during /v1/models fetch ([f6233ab](https://github.com/dedalus-labs/wingman/commit/f6233ab6344f877c9500b06f38575a7a44bca750))


### Bug Fixes

* allow Ctrl+D to exit when prompt is empty ([ee2b67c](https://github.com/dedalus-labs/wingman/commit/ee2b67cf73688d3036981d2f5a35c90cbd1a0fb6))
* **app:** harden status bar against base_url without scheme ([4b38314](https://github.com/dedalus-labs/wingman/commit/4b3831414bdf7967ded0b918838ab9d9102718ef))
* **app:** wrap /compact in [@work](https://github.com/work) so sync dispatch schedules it ([6feb308](https://github.com/dedalus-labs/wingman/commit/6feb3083995b0eba730009fa4248ff0649752b49))
* **commands:** use panel._show_welcome (private name) after /delete ([c021e01](https://github.com/dedalus-labs/wingman/commit/c021e01f29757c32ae7395bec74f3ab3d312e56b))
* **config:** auto-prepend https:// to bare base_url ([89cbc7f](https://github.com/dedalus-labs/wingman/commit/89cbc7f49c196bf9b87b8b1519bb4e95d3d7e3ec))
* correct vouch workflow inputs and add contributors ([567a7d0](https://github.com/dedalus-labs/wingman/commit/567a7d092b056b0259519f888c3ba410847359cd))
* **lint:** resolve all ruff violations and fix Ctrl+C tests ([#21](https://github.com/dedalus-labs/wingman/issues/21)) ([b6609f6](https://github.com/dedalus-labs/wingman/commit/b6609f652b948424db6d81427f1b2e2994487a75))
* **sessions:** rename_session rewires children's parent_session_id ([e35d649](https://github.com/dedalus-labs/wingman/commit/e35d6491e05226b57eb408e30f4bab0f73d995dd))
* **streaming:** wrap send_message in [@work](https://github.com/work) to restore streaming ([baf3754](https://github.com/dedalus-labs/wingman/commit/baf37545c909c54430346a1cbeabcace4abdc6e6))
* **tools:** decorate _show_diff_modal with [@work](https://github.com/work) for sync callers ([4b55033](https://github.com/dedalus-labs/wingman/commit/4b55033ac1cba22c8dd0bf543f4e55364aa58926))
* **ui:** keep slash command hint visible on exact match ([56efd73](https://github.com/dedalus-labs/wingman/commit/56efd73b56a4662e99600a0d64f0e5b441cca017))
* **ui:** keep slash command hint visible on exact match ([#28](https://github.com/dedalus-labs/wingman/issues/28)) ([a588fb8](https://github.com/dedalus-labs/wingman/commit/a588fb880ce9a4afb0ef4a1a4242f8268ca0da6e))
* **ui:** preserve typed text when attaching dragged image ([290522e](https://github.com/dedalus-labs/wingman/commit/290522e6deb620f0683e327473a3fc5c85b1c4de))
* **ui:** render image count indicator as styled text ([e151b5f](https://github.com/dedalus-labs/wingman/commit/e151b5f011f015a9337b969d0d7f7ef7f8200f38))
* **ui:** size quit-hint to content so image chips aren't clipped ([33af720](https://github.com/dedalus-labs/wingman/commit/33af720e7b0cfa9b354639d0520a0421f23ea40f))
* **ui:** style BaseUrlScreen to match APIKeyScreen layout ([fb4c03a](https://github.com/dedalus-labs/wingman/commit/fb4c03ab91138afc45ba5c7b4c8d3b55be1293c5))
* use BASE_URL as the canonical env var name ([be9fe2b](https://github.com/dedalus-labs/wingman/commit/be9fe2b2583f50e7b7fe3d2e3dd58dcbc735154c))


### Documentation

* add development workflow guide ([3fae11e](https://github.com/dedalus-labs/wingman/commit/3fae11e710fd30bf326402259ebe5d2365d8114b))

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
