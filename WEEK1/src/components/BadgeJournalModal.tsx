import React from 'react';
import { X, Award, Compass, Calendar, MapPin, Sparkles } from 'lucide-react';
import type { Badge, Vibe } from '../types';

interface BadgeJournalModalProps {
  isOpen: boolean;
  onClose: () => void;
  badges: Badge[];
}

const VIBE_COLOR_MAP: Record<Vibe, { bg: string; text: string; border: string }> = {
  mystery: { bg: 'bg-[#EDE7F6]', text: 'text-[#4A148C]', border: 'border-[#B388FF]' },
  nature: { bg: 'bg-[#E8F5E9]', text: 'text-[#1B5E20]', border: 'border-[#81C784]' },
  silly: { bg: 'bg-[#FFF8E1]', text: 'text-[#F57F17]', border: 'border-[#FFE082]' },
  fantasy: { bg: 'bg-[#E0F7FA]', text: 'text-[#006064]', border: 'border-[#80DEEA]' },
};

export const BadgeJournalModal: React.FC<BadgeJournalModalProps> = ({
  isOpen,
  onClose,
  badges,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="journal-card max-w-2xl w-full p-6 relative max-h-[90vh] flex flex-col animate-in fade-in zoom-in duration-150">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg bg-[#EADCB9] text-[#3E2723] hover:bg-[#DFCDA5]"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Title */}
        <div className="flex items-center gap-3 mb-6 shrink-0 border-b-2 border-[#D4C3A3] pb-4">
          <div className="w-12 h-12 rounded-xl bg-[#D97706] text-white flex items-center justify-center border-2 border-[#9A3412] shadow-md">
            <Award className="w-7 h-7" />
          </div>
          <div>
            <h2 className="text-2xl font-black text-[#1E3F20] tracking-tight">
              FIELD JOURNAL & BADGES
            </h2>
            <p className="text-xs text-[#594A42] font-semibold">
              {badges.length} Mini-Adventure Badges Earned
            </p>
          </div>
        </div>

        {/* Badge Grid or Empty state */}
        <div className="overflow-y-auto flex-1 pr-1 space-y-4">
          {badges.length === 0 ? (
            <div className="text-center py-12 px-4 journal-card bg-[#FAF5E8] border-dashed">
              <Compass className="w-12 h-12 text-[#D4C3A3] mx-auto mb-3 animate-spin" style={{ animationDuration: '12s' }} />
              <h3 className="font-extrabold text-lg text-[#3E2723]">Your Journal is Empty</h3>
              <p className="text-xs text-[#594A42] max-w-sm mx-auto mt-1">
                Complete your first real-world raid with your squad to unlock handcrafted collectible badges!
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {badges.map((b) => {
                const vibeStyle = VIBE_COLOR_MAP[b.vibe] || VIBE_COLOR_MAP.nature;
                return (
                  <div
                    key={b.id}
                    className="journal-card p-4 relative group hover:border-[#1E3F20] transition-all flex flex-col justify-between"
                  >
                    {/* Badge Wax Seal Icon */}
                    <div className="flex items-start justify-between gap-2 mb-3">
                      <div className="w-12 h-12 rounded-full wax-seal text-[#FEF3C7] flex items-center justify-center shrink-0">
                        <Sparkles className="w-6 h-6" />
                      </div>
                      <span
                        className={`text-[10px] font-black uppercase px-2 py-0.5 rounded-full border ${vibeStyle.bg} ${vibeStyle.text} ${vibeStyle.border}`}
                      >
                        {b.vibe}
                      </span>
                    </div>

                    <div>
                      <h4 className="font-black text-base text-[#1E3F20] leading-snug">
                        {b.name}
                      </h4>
                      <p className="text-xs font-bold text-[#D97706] mb-2">{b.title}</p>
                      <p className="text-xs text-[#594A42] line-clamp-3 italic mb-3">
                        "{b.storyEnding}"
                      </p>
                    </div>

                    {/* Metadata Footer */}
                    <div className="pt-2 border-t border-[#EADCB9] flex items-center justify-between text-[11px] text-[#594A42] font-medium">
                      <span className="flex items-center gap-1 truncate max-w-[140px]">
                        <MapPin className="w-3 h-3 text-[#1E3F20] shrink-0" />
                        <span className="truncate">{b.locationName}</span>
                      </span>
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3 text-[#D97706] shrink-0" />
                        <span>{new Date(b.dateUnlocked).toLocaleDateString()}</span>
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
