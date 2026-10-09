import type { AIConfig, MissionData, MissionRequest } from '../types';
import { getFallbackMission } from './fallbackMissions';

export interface GenerationResult {
  mission: MissionData;
  isAI: boolean;
  modelUsed?: string;
  errorMessage?: string;
}

export function validateMissionSchema(data: unknown): data is MissionData {
  if (!data || typeof data !== 'object') return false;

  const obj = data as Record<string, unknown>;

  const requiredKeys: (keyof MissionData)[] = [
    'title',
    'story_hook',
    'destination_suggestion',
    'clue',
    'objective',
    'story_ending',
    'badge_name'
  ];

  for (const key of requiredKeys) {
    if (typeof obj[key] !== 'string' || (obj[key] as string).trim() === '') {
      console.warn(`Mission schema validation failed: missing or invalid field "${key}"`, obj);
      return false;
    }
  }

  return true;
}

export async function generateMission(
  request: MissionRequest,
  config: AIConfig
): Promise<GenerationResult> {
  if (!config.isEnabled) {
    return {
      mission: getFallbackMission(request),
      isAI: false,
      errorMessage: 'Local AI is disabled in settings. Using hand-crafted explorer lore.'
    };
  }

  const confirmedFeaturesStr = request.osmFeatures && request.osmFeatures.length > 0
    ? request.osmFeatures.join(', ')
    : 'public walkway, seating area, greenery or trees, signpost';

  const prompt = `You are the Master Storyteller for "Raid Outside", a tabletop-RPG inspired co-op micro-adventure app.
Generate a safe, observational real-world quest based on the following user inputs:
- Vibe: ${request.vibe}
- Duration: ${request.duration} minutes
- Walking Effort: ${request.effort}
- User's nearby public place: ${request.landmark}
- CONFIRMED PHYSICAL FEATURES AT THIS LOCATION FROM OPENSTREETMAP: [ ${confirmedFeaturesStr} ]

CRITICAL INSTRUCTIONS ON PHYSICAL FEATURES:
- ONLY reference physical features that ACTUALLY EXIST at this location from the confirmed OpenStreetMap list above (${confirmedFeaturesStr}).
- Do NOT invent objects that do not exist (e.g. do NOT mention fountains, arches, pillars, or statues unless explicitly listed in confirmed OpenStreetMap features).

IMPORTANT SAFETY RULES:
- Do NOT direct users onto private property, dangerous roads, construction sites, or restricted areas.
- Keep objectives 100% observational (notice colors, shapes, patterns, public plaques, signs, trees, or fun squad poses).
- Never instruct players to touch wildlife, pick flowers, climb structures, or collect items.

Return ONLY a JSON object with EXACTLY these fields (no markdown formatting, no code blocks):
{
  "title": "A short epic quest name (3-6 words)",
  "story_hook": "An intriguing 2-sentence narrative introduction connecting the vibe to the location",
  "destination_suggestion": "A safe suggestion of where to walk near ${request.landmark} focusing on ${confirmedFeaturesStr}",
  "clue": "A playful riddle about observing one of the confirmed physical features (${confirmedFeaturesStr})",
  "objective": "A simple, fun observation task for the squad focusing strictly on confirmed features (${confirmedFeaturesStr})",
  "story_ending": "A satisfying 2-sentence conclusion revealing what the squad achieved",
  "badge_name": "A cool collectible badge title (2-3 words)"
}`;

  const cleanBaseUrl = config.baseUrl.replace(/\/+$/, '');
  const endpoint = cleanBaseUrl.endsWith('/chat/completions')
    ? cleanBaseUrl
    : `${cleanBaseUrl}/chat/completions`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 12000); // 12-second timeout for local open models

  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${config.apiKey || 'ollama'}`
      },
      signal: controller.signal,
      body: JSON.stringify({
        model: config.modelName || 'llama3.2',
        messages: [
          {
            role: 'system',
            content: 'You output pure structured JSON only. Strictly respect the confirmed physical location features.'
          },
          {
            role: 'user',
            content: prompt
          }
        ],
        temperature: 0.7,
        max_tokens: 600,
        response_format: { type: 'json_object' }
      })
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new Error(`Local AI endpoint returned HTTP status ${response.status}`);
    }

    const data = await response.json();
    const rawContent = data.choices?.[0]?.message?.content;

    if (!rawContent) {
      throw new Error('Local AI response was empty');
    }

    let jsonString = rawContent.trim();
    if (jsonString.startsWith('```')) {
      jsonString = jsonString.replace(/^```(json)?/, '').replace(/```$/, '').trim();
    }

    const parsedJson = JSON.parse(jsonString);

    if (validateMissionSchema(parsedJson)) {
      return {
        mission: {
          ...parsedJson,
          vibe: request.vibe,
          landmark: request.landmark,
          osmFeatures: request.osmFeatures,
          isOSMConfirmed: request.isOSMConfirmed,
          id: `ai-mission-${Date.now()}`,
          createdAt: new Date().toISOString()
        },
        isAI: true,
        modelUsed: config.modelName
      };
    } else {
      throw new Error('Local AI response did not conform to the required JSON schema');
    }

  } catch (error: unknown) {
    clearTimeout(timeoutId);
    const errMessage = error instanceof Error ? error.message : 'Connection error';
    console.warn('AI Mission Generation fallback triggered:', errMessage);

    return {
      mission: getFallbackMission(request),
      isAI: false,
      errorMessage: `Model fallback active (${errMessage}). Serving hand-crafted explorer mission.`
    };
  }
}

export async function testAIConnection(config: AIConfig): Promise<{ success: boolean; message: string }> {
  const cleanBaseUrl = config.baseUrl.replace(/\/+$/, '');
  const endpoint = cleanBaseUrl.endsWith('/models')
    ? cleanBaseUrl
    : cleanBaseUrl.endsWith('/chat/completions')
      ? cleanBaseUrl.replace('/chat/completions', '/models')
      : `${cleanBaseUrl}/models`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 4000);

  try {
    const res = await fetch(endpoint, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${config.apiKey || 'ollama'}`
      },
      signal: controller.signal
    });

    clearTimeout(timeoutId);

    if (res.ok) {
      return { success: true, message: 'Successfully connected to local open AI endpoint!' };
    } else {
      return { success: false, message: `Endpoint reachable but status code was ${res.status}` };
    }
  } catch (e: unknown) {
    clearTimeout(timeoutId);
    const msg = e instanceof Error ? e.message : 'Failed to connect';
    return { success: false, message: `Could not connect to ${cleanBaseUrl}: ${msg}` };
  }
}
