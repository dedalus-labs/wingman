/**
 * @license
 * Copyright 2025 Dedalus Labs
 * SPDX-License-Identifier: Apache-2.0
 */

import {
  CountTokensResponse,
  GenerateContentResponse,
  GenerateContentParameters,
  CountTokensParameters,
  EmbedContentResponse,
  EmbedContentParameters,
  GoogleGenAI,
} from '@google/genai';
import { createCodeAssistContentGenerator } from '../code_assist/codeAssist.js';
import { DEFAULT_DEDALUS_MODEL } from '../config/models.js';
import { Config } from '../config/config.js';
import { getEffectiveModel } from './modelCheck.js';
import { UserTierId } from '../code_assist/types.js';

/**
 * Interface abstracting the core functionalities for generating content and counting tokens.
 */
export interface ContentGenerator {
  generateContent(
    request: GenerateContentParameters,
  ): Promise<GenerateContentResponse>;

  generateContentStream(
    request: GenerateContentParameters,
  ): Promise<AsyncGenerator<GenerateContentResponse>>;

  countTokens(request: CountTokensParameters): Promise<CountTokensResponse>;

  embedContent(request: EmbedContentParameters): Promise<EmbedContentResponse>;

  getTier?(): Promise<UserTierId | undefined>;
}

export enum AuthType {
  LOGIN_WITH_DEDALUS = 'oauth-personal',
  USE_DEDALUS = 'dedalus-api-key',
  USE_DEDALUS_CLOUD = 'dedalus-cloud',
  CLOUD_SHELL = 'cloud-shell',
}

export type ContentGeneratorConfig = {
  model: string;
  apiKey?: string;
  vertexai?: boolean;
  authType?: AuthType | undefined;
};

export function createContentGeneratorConfig(
  config: Config,
  authType: AuthType | undefined,
): ContentGeneratorConfig {
  const dedalusApiKey = process.env.DEDALUS_API_KEY || undefined;
  const dedalusApiKey2 = process.env.DEDALUS_API_KEY || undefined;
  const dedalusCloudProject = process.env.DEDALUS_CLOUD_PROJECT || undefined;
  const dedalusCloudLocation = process.env.DEDALUS_CLOUD_LOCATION || undefined;

  // Use runtime model from config if available, otherwise fallback to parameter or default
  const effectiveModel = config.getModel() || DEFAULT_DEDALUS_MODEL;

  const contentGeneratorConfig: ContentGeneratorConfig = {
    model: effectiveModel,
    authType,
  };

  // If we are using Dedalus auth or we are in Cloud Shell, there is nothing else to validate for now
  if (
    authType === AuthType.LOGIN_WITH_DEDALUS ||
    authType === AuthType.CLOUD_SHELL
  ) {
    return contentGeneratorConfig;
  }

  if (authType === AuthType.USE_DEDALUS && dedalusApiKey) {
    contentGeneratorConfig.apiKey = dedalusApiKey;
    contentGeneratorConfig.vertexai = false;
    getEffectiveModel(
      contentGeneratorConfig.apiKey,
      contentGeneratorConfig.model,
    ).then((newModel) => {
      if (newModel !== contentGeneratorConfig.model) {
        config.flashFallbackHandler?.(contentGeneratorConfig.model, newModel);
      }
    });

    return contentGeneratorConfig;
  }

  if (
    authType === AuthType.USE_DEDALUS_CLOUD &&
    (dedalusApiKey2 || (dedalusCloudProject && dedalusCloudLocation))
  ) {
    contentGeneratorConfig.apiKey = dedalusApiKey2;
    contentGeneratorConfig.vertexai = true;

    return contentGeneratorConfig;
  }

  return contentGeneratorConfig;
}

export async function createContentGenerator(
  config: ContentGeneratorConfig,
  gcConfig: Config,
  sessionId?: string,
): Promise<ContentGenerator> {
  const version = process.env.CLI_VERSION || process.version;
  const httpOptions = {
    headers: {
      'User-Agent': `DedalusWingman/${version} (${process.platform}; ${process.arch})`,
    },
  };
  if (
    config.authType === AuthType.LOGIN_WITH_DEDALUS ||
    config.authType === AuthType.CLOUD_SHELL
  ) {
    return createCodeAssistContentGenerator(
      httpOptions,
      config.authType,
      gcConfig,
      sessionId,
    );
  }

  if (
    config.authType === AuthType.USE_GEMINI ||
    config.authType === AuthType.USE_VERTEX_AI
  ) {
    const googleGenAI = new GoogleGenAI({
      apiKey: config.apiKey === '' ? undefined : config.apiKey,
      vertexai: config.vertexai,
      httpOptions,
    });

    return googleGenAI.models;
  }

  throw new Error(
    `Error creating contentGenerator: Unsupported authType: ${config.authType}`,
  );
}
