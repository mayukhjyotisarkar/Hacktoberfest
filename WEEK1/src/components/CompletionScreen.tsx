import React, { useEffect, useState } from 'react';
import confetti from 'canvas-confetti';
import { Award, Sparkles, Share2, RefreshCw, BookOpen, Check, PartyPopper } from 'lucide-react';
import type { MissionData } from '../types';

interface CompletionScreenProps {
  mission: MissionData;
  onRunItBack: () => void;
  onOpenJournal: () => void;
}

export const CompletionScreen: React.FC<CompletionScreenProps> = ({
  mission,
  onRunItBack,
  onOpenJournal,
}) => {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    confetti({
      particleCount: 80,
      spread: 70,
      origin: { y: 0.6 }
    });
  }, []);

  const handleShare = () => {
    const text = `🏆 Squad Victory in Raid Outside!\nQuest: "${mission.title}"\nBadge Unlocked: [ ${mission.badge_name} ]\nExplore with your friends at: ${window.location.origin}`;

    if (navigator.share) {
      navigator.share({
        title: 'Raid Outside - Victory!',
        text: text,
      }).catch(() => {});
    } else {
      navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 3000);
    }
  };

  return (
    <div className="space-y-6 py-2 animate-in zoom-in-95 duration-250">
      {/* Victory Banner Card */}
      <div className="journal-card p-6 sm:p-8 border-2 border-[#D97706] text-center relative overflow-hidden shadow-xl space-y-6">
        {/* Decorative Badge Seal */}
        <div className="w-20 h-20 rounded-full wax-seal text-white flex items-center justify-center mx-auto shadow-xl ring-4 ring-[#FEF3C7] animate-bounce">
          <Award className="w-10 h-10" />
        </div>

        <div>
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#FEF3C7] text-[#D97706] text-xs font-black uppercase tracking-wider mb-2 border border-[#FDE68A]">
            <PartyPopper className="w-4 h-4" />
            <span>RAID COMPLETED!</span>
          </div>

          <h1 className="text-3xl sm:text-4xl font-black text-[#1E3F20] tracking-tight">
            VICTORY ACHIEVED!
          </h1>
          <p className="text-sm font-bold text-[#D97706] mt-1">"{mission.title}"</p>
        </div>

        {/* Satisfying Story Ending */}
        <div className="p-4 rounded-xl bg-[#FAF5E8] border border-[#D4C3A3] text-sm text-[#3E2723] italic leading-relaxed font-medium">
          "{mission.story_ending}"
        </div>

        {/* Awarded Badge Display */}
        <div className="p-4 rounded-2xl bg-[#FFFDF9] border-2 border-[#1E3F20] shadow-md space-y-2 max-w-sm mx-auto">
          <span className="text-[10px] font-black uppercase tracking-widest text-[#5C3D2E]">
            NEW COLLECTIBLE UNLOCKED
          </span>
          <div className="flex items-center justify-center gap-2">
            <Sparkles className="w-5 h-5 text-[#D97706]" />
            <h3 className="text-xl font-black text-[#1E3F20]">
              {mission.badge_name}
            </h3>
            <Sparkles className="w-5 h-5 text-[#D97706]" />
          </div>
          <p className="text-xs text-[#594A42] font-semibold">
            Saved to your Field Journal!
          </p>
        </div>

        {/* Action Buttons */}
        <div className="space-y-3 max-w-md mx-auto pt-2">
          <div className="flex flex-col sm:flex-row gap-3">
            <button
              onClick={handleShare}
              className="flex-1 py-3.5 px-4 rounded-xl rpg-button-primary text-sm flex items-center justify-center gap-2 cursor-pointer shadow-md"
            >
              {copied ? (
                <>
                  <Check className="w-4 h-4 text-[#FEF3C7]" />
                  <span>Result Copied!</span>
                </>
              ) : (
                <>
                  <Share2 className="w-4 h-4 text-[#FEF3C7]" />
                  <span>SHARE THE RESULT</span>
                </>
              )}
            </button>

            <button
              onClick={onRunItBack}
              className="flex-1 py-3.5 px-4 rounded-xl rpg-button-secondary text-sm flex items-center justify-center gap-2 cursor-pointer shadow-xs"
            >
              <RefreshCw className="w-4 h-4 text-[#5C3D2E]" />
              <span>RUN IT BACK</span>
            </button>
          </div>

          <button
            onClick={onOpenJournal}
            className="w-full py-2.5 px-4 rounded-xl bg-[#EADCB9]/80 text-[#3E2723] text-xs font-bold hover:bg-[#EADCB9] border border-[#C4B188] flex items-center justify-center gap-1.5"
          >
            <BookOpen className="w-4 h-4 text-[#D97706]" />
            <span>View All Badges in Journal</span>
          </button>
        </div>
      </div>
    </div>
  );
};
