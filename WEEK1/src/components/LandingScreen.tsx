import React from 'react';
import { Compass, Users, Sparkles, MapPin, ShieldCheck, Flame, Search, Feather, TreePine } from 'lucide-react';
import type { Vibe } from '../types';

interface LandingScreenProps {
  onStartRaid: () => void;
  onJoinParty: () => void;
}

const VIBE_PREVIEWS: { vibe: Vibe; title: string; desc: string; icon: React.ReactNode; color: string }[] = [
  {
    vibe: 'mystery',
    title: 'Mystery & Ciphers',
    desc: 'Uncover hidden street markings and architectural codes.',
    icon: <Search className="w-5 h-5 text-purple-700" />,
    color: 'bg-purple-100 border-purple-300 text-purple-900',
  },
  {
    vibe: 'nature',
    title: 'Urban Wilderness',
    desc: 'Track ancient trees, green canopies, and sky patterns.',
    icon: <TreePine className="w-5 h-5 text-emerald-700" />,
    color: 'bg-emerald-100 border-emerald-300 text-emerald-900',
  },
  {
    vibe: 'silly',
    title: 'Silly Operations',
    desc: 'Perform synchronized pigeon secret-agent poses.',
    icon: <Feather className="w-5 h-5 text-amber-700" />,
    color: 'bg-amber-100 border-amber-300 text-amber-900',
  },
  {
    vibe: 'fantasy',
    title: 'Tabletop RPG Lore',
    desc: 'Awaken stone portals and cosmic beacons nearby.',
    icon: <Sparkles className="w-5 h-5 text-cyan-700" />,
    color: 'bg-cyan-100 border-cyan-300 text-cyan-900',
  },
];

export const LandingScreen: React.FC<LandingScreenProps> = ({
  onStartRaid,
  onJoinParty,
}) => {
  return (
    <div className="space-y-8 py-4 animate-in fade-in duration-200">
      {/* Hero Box */}
      <div className="journal-card p-6 sm:p-8 text-center relative overflow-hidden border-2 border-[#D4C3A3] shadow-md">
        {/* Background Decorative Motif */}
        <div className="absolute -top-12 -right-12 w-40 h-40 bg-[#D97706]/10 rounded-full blur-2xl pointer-events-none" />
        <div className="absolute -bottom-12 -left-12 w-40 h-40 bg-[#1E3F20]/10 rounded-full blur-2xl pointer-events-none" />

        {/* Quest Badge Tag */}
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#EADCB9] text-[#5C3D2E] text-xs font-black uppercase tracking-wider mb-4 border border-[#C4B188]">
          <Flame className="w-4 h-4 text-[#D97706]" />
          <span>REAL-WORLD CO-OP MICRO-ADVENTURES</span>
        </div>

        {/* One-sentence explanation requested by user */}
        <h1 className="text-2xl sm:text-4xl font-black text-[#1E3F20] tracking-tight leading-tight max-w-xl mx-auto mb-3">
          Turn a quick walk with friends into a tabletop RPG expedition.
        </h1>

        <p className="text-sm sm:text-base text-[#594A42] max-w-lg mx-auto font-medium mb-8 leading-relaxed">
          Step away from your desk, head to a nearby park or landmark, solve real-world observation clues together, and unlock collectible badges!
        </p>

        {/* Primary CTA Buttons */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 max-w-md mx-auto">
          <button
            onClick={onStartRaid}
            className="w-full sm:w-auto flex-1 py-4 px-6 rounded-xl rpg-button-primary text-base flex items-center justify-center gap-2 cursor-pointer shadow-md"
          >
            <Compass className="w-5 h-5 text-[#FEF3C7]" />
            <span>START A RAID</span>
          </button>

          <button
            onClick={onJoinParty}
            className="w-full sm:w-auto flex-1 py-4 px-6 rounded-xl rpg-button-secondary text-base flex items-center justify-center gap-2 cursor-pointer shadow-xs"
          >
            <Users className="w-5 h-5 text-[#5C3D2E]" />
            <span>JOIN A PARTY</span>
          </button>
        </div>
      </div>

      {/* Vibe Selection Preview */}
      <div>
        <h2 className="text-xs font-black uppercase tracking-widest text-[#5C3D2E] text-center mb-3">
          CHOOSABLE MISSION VIBES
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {VIBE_PREVIEWS.map((v) => (
            <div
              key={v.vibe}
              className={`p-4 rounded-xl border ${v.color} flex items-start gap-3 shadow-xs transition-transform hover:-translate-y-0.5`}
            >
              <div className="p-2.5 rounded-lg bg-white/80 shadow-xs border border-black/5 shrink-0">
                {v.icon}
              </div>
              <div>
                <h3 className="font-bold text-sm mb-0.5">{v.title}</h3>
                <p className="text-xs opacity-90 leading-normal">{v.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Features & Safety Highlights */}
      <div className="journal-card p-5 bg-[#FAF5E8] border border-[#D4C3A3] grid grid-cols-1 sm:grid-cols-3 gap-4 text-center">
        <div className="space-y-1">
          <div className="w-8 h-8 rounded-full bg-[#1E3F20]/10 text-[#1E3F20] flex items-center justify-center mx-auto">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <h4 className="font-bold text-xs text-[#1E3F20]">Account-Free & Private</h4>
          <p className="text-[11px] text-[#594A42]">No signups required. No GPS background tracking.</p>
        </div>

        <div className="space-y-1">
          <div className="w-8 h-8 rounded-full bg-[#D97706]/10 text-[#D97706] flex items-center justify-center mx-auto">
            <MapPin className="w-5 h-5" />
          </div>
          <h4 className="font-bold text-xs text-[#1E3F20]">Low-Risk Observations</h4>
          <p className="text-[11px] text-[#594A42]">100% safe public spot clues. No touching or climbing.</p>
        </div>

        <div className="space-y-1">
          <div className="w-8 h-8 rounded-full bg-[#5C3D2E]/10 text-[#5C3D2E] flex items-center justify-center mx-auto">
            <Sparkles className="w-5 h-5" />
          </div>
          <h4 className="font-bold text-xs text-[#1E3F20]">Open-Source AI Powered</h4>
          <p className="text-[11px] text-[#594A42]">Generates custom lore using your local Ollama or fallback lore.</p>
        </div>
      </div>
    </div>
  );
};
