import React from 'react';
import { Scroll, MapPin, Search, Target, Sparkles, Cpu, Play } from 'lucide-react';
import type { MissionData } from '../types';

interface MissionBriefingScreenProps {
  mission: MissionData;
  isAI: boolean;
  modelUsed?: string;
  errorMessage?: string;
  onBeginRaid: () => void;
}

export const MissionBriefingScreen: React.FC<MissionBriefingScreenProps> = ({
  mission,
  isAI,
  modelUsed,
  onBeginRaid,
}) => {
  return (
    <div className="space-y-6 py-2 animate-in fade-in duration-200">
      {/* AI Model Generation Source Badge */}
      <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-[#FAF5E8] border border-[#D4C3A3] text-xs">
        <div className="flex items-center gap-1.5 font-bold">
          <Cpu className={`w-4 h-4 ${isAI ? 'text-[#1B5E20]' : 'text-[#D97706]'}`} />
          <span>
            {isAI
              ? `Generated via Open-Weight AI (${modelUsed || 'Local LLM'})`
              : 'Hand-Crafted Explorer Lore'}
          </span>
        </div>
        {!isAI && (
          <span className="text-[10px] text-[#594A42] italic">
            Fallback Mode Active
          </span>
        )}
      </div>

      {/* Main Journal Scroll Briefing Card */}
      <div className="journal-card p-6 border-2 border-[#1E3F20] shadow-lg relative">
        {/* Top Scroll Header */}
        <div className="flex items-center justify-between border-b-2 border-[#D4C3A3] pb-4 mb-4">
          <div className="flex items-center gap-2">
            <Scroll className="w-6 h-6 text-[#D97706]" />
            <span className="text-xs font-black uppercase tracking-widest text-[#5C3D2E]">
              MISSION BRIEFING
            </span>
          </div>
          <div className="wax-seal w-8 h-8 rounded-full text-white flex items-center justify-center text-xs font-bold shadow-xs">
            ⚔️
          </div>
        </div>

        {/* Quest Title */}
        <h1 className="text-2xl sm:text-3xl font-black text-[#1E3F20] tracking-tight leading-snug mb-3">
          {mission.title}
        </h1>

        {/* Story Hook */}
        <div className="p-4 rounded-xl bg-[#FAF5E8] border-l-4 border-[#1E3F20] text-sm text-[#3E2723] italic leading-relaxed mb-6 font-medium">
          "{mission.story_hook}"
        </div>

        {/* Quest Details Grid */}
        <div className="space-y-4 mb-8">
          {/* 1. Destination Suggestion */}
          <div className="p-3.5 rounded-xl bg-white border border-[#D4C3A3] space-y-1 shadow-xs">
            <div className="flex items-center gap-1.5 text-xs font-black uppercase tracking-wider text-[#991B1B]">
              <MapPin className="w-4 h-4 text-[#991B1B]" />
              <span>Target Destination</span>
            </div>
            <p className="text-sm font-bold text-[#1E3F20]">
              {mission.destination_suggestion}
            </p>
          </div>

          {/* 2. Clue */}
          <div className="p-3.5 rounded-xl bg-white border border-[#D4C3A3] space-y-1 shadow-xs">
            <div className="flex items-center gap-1.5 text-xs font-black uppercase tracking-wider text-[#D97706]">
              <Search className="w-4 h-4 text-[#D97706]" />
              <span>Observation Clue</span>
            </div>
            <p className="text-sm font-semibold text-[#3E2723]">
              {mission.clue}
            </p>
          </div>

          {/* 3. Objective */}
          <div className="p-3.5 rounded-xl bg-[#F6EFE0] border-2 border-[#1E3F20] space-y-1 shadow-xs">
            <div className="flex items-center gap-1.5 text-xs font-black uppercase tracking-wider text-[#1E3F20]">
              <Target className="w-4 h-4 text-[#1E3F20]" />
              <span>Squad Objective</span>
            </div>
            <p className="text-sm font-black text-[#1E3F20]">
              {mission.objective}
            </p>
          </div>
        </div>

        {/* Target Collectible Badge Preview */}
        <div className="p-3 bg-[#EADCB9]/70 rounded-xl border border-[#C4B188] flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-[#D97706]" />
            <span className="text-xs font-bold text-[#3E2723]">Reward Badge upon completion:</span>
          </div>
          <span className="text-xs font-black text-[#1E3F20] bg-white px-2.5 py-1 rounded-md border border-[#D4C3A3]">
            🏆 {mission.badge_name}
          </span>
        </div>

        {/* Primary CTA */}
        <button
          onClick={onBeginRaid}
          className="w-full py-4 rounded-xl rpg-button-primary text-base flex items-center justify-center gap-2 cursor-pointer shadow-md"
        >
          <Play className="w-5 h-5 text-[#FEF3C7] fill-current" />
          <span>WE'RE EN ROUTE - BEGIN RAID!</span>
        </button>
      </div>
    </div>
  );
};
