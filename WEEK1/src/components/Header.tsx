import React from 'react';
import { Compass, BookOpen, Settings, Cpu } from 'lucide-react';
import type { AIConfig } from '../types';

interface HeaderProps {
  aiConfig: AIConfig;
  badgeCount: number;
  onOpenSettings: () => void;
  onOpenJournal: () => void;
  onResetToHome: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  aiConfig,
  badgeCount,
  onOpenSettings,
  onOpenJournal,
  onResetToHome,
}) => {
  return (
    <header className="sticky top-0 z-30 bg-[#F6EFE0]/95 backdrop-blur-xs border-b-2 border-[#D4C3A3] px-4 py-3 shadow-xs">
      <div className="max-w-3xl mx-auto flex items-center justify-between gap-2">
        {/* Logo & Brand */}
        <button
          onClick={onResetToHome}
          className="flex items-center gap-2 text-left group cursor-pointer focus:outline-hidden"
          title="Return to Raid Outside Home"
        >
          <div className="w-10 h-10 rounded-xl bg-[#1E3F20] text-[#FEF3C7] flex items-center justify-center border-2 border-[#D97706] shadow-xs group-hover:scale-105 transition-transform">
            <Compass className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <div className="font-extrabold text-xl tracking-tight text-[#1E3F20] flex items-center gap-1">
              RAID OUTSIDE
            </div>
            <p className="text-xs text-[#594A42] font-semibold hidden sm:block">
              Co-op Mini-Adventures
            </p>
          </div>
        </button>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          {/* AI Connection Indicator */}
          <button
            onClick={onOpenSettings}
            className={`flex items-center gap-1.5 text-xs font-bold px-2.5 py-1.5 rounded-lg border transition-all ${
              aiConfig.isEnabled
                ? 'bg-[#E8F5E9] text-[#1B5E20] border-[#81C784] hover:bg-[#C8E6C9]'
                : 'bg-[#FFF3E0] text-[#E65100] border-[#FFB74D] hover:bg-[#FFE0B2]'
            }`}
            title="Configure Local AI Endpoint"
          >
            <Cpu className="w-3.5 h-3.5" />
            <span className="hidden md:inline">
              {aiConfig.isEnabled ? 'Local AI Active' : 'Offline Lore'}
            </span>
          </button>

          {/* Badge Journal */}
          <button
            onClick={onOpenJournal}
            className="flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-lg bg-[#EADCB9] text-[#3E2723] border border-[#C4B188] hover:bg-[#DFCDA5] transition-all shadow-xs"
            title="View Collectible Badge Journal"
          >
            <BookOpen className="w-4 h-4 text-[#D97706]" />
            <span>Journal</span>
            {badgeCount > 0 && (
              <span className="ml-0.5 bg-[#D97706] text-white text-[10px] font-black px-1.5 py-0.5 rounded-full">
                {badgeCount}
              </span>
            )}
          </button>

          {/* Settings button */}
          <button
            onClick={onOpenSettings}
            className="p-2 rounded-lg bg-[#EADCB9] text-[#3E2723] border border-[#C4B188] hover:bg-[#DFCDA5] transition-all shadow-xs"
            title="Open Settings"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
};
