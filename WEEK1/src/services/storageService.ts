import type { AIConfig, Badge, MissionData } from '../types';

const AI_CONFIG_KEY = 'raid_outside_ai_config';
const BADGES_KEY = 'raid_outside_badges';
const COMPLETED_RAIDS_KEY = 'raid_outside_completed_raids';

export const DEFAULT_AI_CONFIG: AIConfig = {
  baseUrl: import.meta.env.VITE_OPENAI_BASE_URL || 'http://localhost:11434/v1',
  modelName: import.meta.env.VITE_OPENAI_MODEL_NAME || 'llama3.2',
  apiKey: import.meta.env.VITE_OPENAI_API_KEY || 'ollama',
  isEnabled: true,
};

export const storageService = {
  getAIConfig(): AIConfig {
    try {
      const saved = localStorage.getItem(AI_CONFIG_KEY);
      if (saved) {
        return { ...DEFAULT_AI_CONFIG, ...JSON.parse(saved) };
      }
    } catch (e) {
      console.error('Error reading AI config from localStorage', e);
    }
    return DEFAULT_AI_CONFIG;
  },

  saveAIConfig(config: AIConfig): void {
    try {
      localStorage.setItem(AI_CONFIG_KEY, JSON.stringify(config));
    } catch (e) {
      console.error('Error saving AI config to localStorage', e);
    }
  },

  getBadges(): Badge[] {
    try {
      const saved = localStorage.getItem(BADGES_KEY);
      if (saved) {
        return JSON.parse(saved);
      }
    } catch (e) {
      console.error('Error loading badges', e);
    }
    return [];
  },

  saveBadge(badge: Badge): Badge[] {
    const existing = this.getBadges();
    const updated = [badge, ...existing.filter(b => b.id !== badge.id)];
    try {
      localStorage.setItem(BADGES_KEY, JSON.stringify(updated));
    } catch (e) {
      console.error('Error saving badge', e);
    }
    return updated;
  },

  saveCompletedRaid(mission: MissionData): void {
    try {
      const existing = JSON.parse(localStorage.getItem(COMPLETED_RAIDS_KEY) || '[]');
      localStorage.setItem(COMPLETED_RAIDS_KEY, JSON.stringify([mission, ...existing]));
    } catch (e) {
      console.error('Error saving completed raid', e);
    }
  },

  generatePartyCode(): string {
    const prefixes = ['RAID', 'SCOUT', 'PATH', 'QUEST', 'LORE', 'WIND', 'OAK'];
    const prefix = prefixes[Math.floor(Math.random() * prefixes.length)];
    const num = Math.floor(100 + Math.random() * 900);
    return `${prefix}-${num}`;
  }
};
