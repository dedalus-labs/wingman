/**
 * @license
 * Copyright 2025 Dedalus Labs
 * SPDX-License-Identifier: Apache-2.0
 */

import { getPackageJson } from './package.js';

export async function getCliVersion(): Promise<string> {
  const pkgJson = await getPackageJson();
  return process.env.CLI_VERSION || pkgJson?.version || 'unknown';
}
