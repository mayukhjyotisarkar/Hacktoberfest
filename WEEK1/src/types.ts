export type Vibe = 'mystery' | 'nature' | 'silly' | 'fantasy';
export type Duration = 15 | 30 | 45;
export type Effort = 'easy' | 'adventurous';

export interface MissionRequest {
  vibe: Vibe;
  duration: Duration;
  effort: Effort;
  landmark: string;
  osmFeatures?: string[];
  isOSMPlaceMatched?: boolean;
}

export interface MissionData {
  title: string;
  story_hook: string;
  destination_suggestion: string;
  clue: string;
  objective: string;
  story_ending: string;
  badge_name: string;
  // Extended fields for local app tracking
  id?: string;
  vibe?: Vibe;
  landmark?: string;
  osmFeatures?: string[];
  isOSMPlaceMatched?: boolean;
  createdAt?: string;
}

export interface SquadMember {
  id: string;
  name: string;
  avatar: string;
  isHost: boolean;
  ready: boolean;
}

export interface Party {
  code: string;
  hostName: string;
  members: SquadMember[];
  raidConfig?: MissionRequest;
  mission?: MissionData;
  currentStep: number;
  status: 'lobby' | 'briefing' | 'active' | 'completed';
}

export interface AIConfig {
  baseUrl: string;
  modelName: string;
  apiKey: string;
  isEnabled: boolean;
}

export interface Badge {
  id: string;
  name: string;
  vibe: Vibe;
  title: string;
  dateUnlocked: string;
  locationName: string;
  storyEnding: string;
}
