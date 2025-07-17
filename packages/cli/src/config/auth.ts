/**
 * @license
 * Copyright 2025 Dedalus Labs
 * SPDX-License-Identifier: Apache-2.0
 */

import { AuthType } from '@dedalus-labs/wingman-core';
import { loadEnvironment } from './settings.js';

export const validateAuthMethod = (authMethod: string): string | null => {
  loadEnvironment();
  if (
    authMethod === AuthType.LOGIN_WITH_GOOGLE ||
    authMethod === AuthType.CLOUD_SHELL
  ) {
    return null;
  }

  if (authMethod === AuthType.USE_DEDALUS) {
    if (!process.env.DEDALUS_API_KEY) {
      return 'DEDALUS_API_KEY environment variable not found. Add that to your environment and try again (no reload needed if using .env)!';
    }
    return null;
  }

  if (authMethod === AuthType.USE_DEDALUS_CLOUD) {
    const hasVertexProjectLocationConfig =
      !!process.env.DEDALUS_CLOUD_PROJECT && !!process.env.DEDALUS_CLOUD_LOCATION;
    const hasDedalusApiKey = !!process.env.DEDALUS_API_KEY;
    if (!hasVertexProjectLocationConfig && !hasDedalusApiKey) {
      return (
        'When using Dedalus Cloud, you must specify either:\n' +
        '• DEDALUS_CLOUD_PROJECT and DEDALUS_CLOUD_LOCATION environment variables.\n' +
        '• DEDALUS_API_KEY environment variable (if using express mode).\n' +
        'Update your environment and try again (no reload needed if using .env)!'
      );
    }
    return null;
  }

  return 'Invalid auth method selected.';
};
