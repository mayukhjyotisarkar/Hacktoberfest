import React, { useState } from 'react';
import { ShieldCheck, X } from 'lucide-react';

export const SafetyBanner: React.FC = () => {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  return (
    <div className="bg-[#FEF3C7] border-b-2 border-[#F59E0B] text-[#92400E] px-4 py-2 text-xs font-semibold shadow-xs">
      <div className="max-w-3xl mx-auto flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 shrink-0 text-[#D97706]" />
          <span>
            <strong className="font-bold">Explorer Safety Notice:</strong> Always stop in a safe, public space before looking at your phone. Stay observant of traffic & surroundings!
          </span>
        </div>
        <button
          onClick={() => setDismissed(true)}
          className="text-[#92400E] hover:text-[#78350F] p-1 rounded-md hover:bg-[#FDE68A]"
          title="Dismiss safety notice"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
