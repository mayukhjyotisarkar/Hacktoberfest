import React, { useState } from 'react';
import { MapPin, Search, Target, CheckCircle2, ShieldAlert } from 'lucide-react';
import type { MissionData } from '../types';

interface ActiveRaidScreenProps {
  mission: MissionData;
  onCompleteRaid: () => void;
}

export const ActiveRaidScreen: React.FC<ActiveRaidScreenProps> = ({
  mission,
  onCompleteRaid,
}) => {
  const [currentStep, setCurrentStep] = useState<number>(0);

  const steps = [
    {
      title: "1. Head to Destination",
      icon: <MapPin className="w-8 h-8 text-[#991B1B]" />,
      heading: "Walk to the Target Area",
      body: mission.destination_suggestion,
      instruction: "Keep your eyes up while walking! Put your phone down or carry it safely until you reach the location.",
      buttonText: "WE HAVE ARRIVED SAFELY",
    },
    {
      title: "2. Search for Observation Clue",
      icon: <Search className="w-8 h-8 text-[#D97706]" />,
      heading: "Look for the Landmark Clue",
      body: mission.clue,
      instruction: "Observe your surroundings quietly with your squad. Look at high or low architectural/nature details.",
      buttonText: "WE FOUND THE CLUE SPOT",
    },
    {
      title: "3. Squad Objective",
      icon: <Target className="w-8 h-8 text-[#1E3F20]" />,
      heading: "Complete the Observation Objective",
      body: mission.objective,
      instruction: "Execute the objective together as a squad! Once everyone verifies, hit the final victory button below.",
      buttonText: "OBJECTIVE COMPLETED! WE FOUND IT!",
    },
  ];

  const activeStep = steps[currentStep];

  const handleNextStep = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
      onCompleteRaid();
    }
  };

  return (
    <div className="space-y-6 py-2 animate-in fade-in duration-200">
      {/* Progress Bar Header */}
      <div className="journal-card p-4 border border-[#D4C3A3] space-y-2">
        <div className="flex items-center justify-between text-xs font-black uppercase tracking-wider text-[#5C3D2E]">
          <span>RAID PROGRESS</span>
          <span>STEP {currentStep + 1} OF {steps.length}</span>
        </div>
        <div className="w-full bg-[#EADCB9] h-3 rounded-full overflow-hidden border border-[#C4B188]">
          <div
            className="bg-[#1E3F20] h-full transition-all duration-300 rounded-full"
            style={{ width: `${((currentStep + 1) / steps.length) * 100}%` }}
          />
        </div>
      </div>

      {/* Safety Notice while on foot */}
      <div className="p-3 bg-[#FEF3C7] border-l-4 border-[#D97706] text-[#92400E] text-xs font-bold rounded-r-lg flex items-start gap-2 shadow-xs">
        <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5 text-[#D97706]" />
        <div>
          <strong>Eyes Up Outdoors:</strong> Always stop in a safe, non-traffic area before reading screen or tapping buttons!
        </div>
      </div>

      {/* Active Step Content Card */}
      <div className="journal-card-active p-6 border-2 border-[#1E3F20] space-y-6 text-center">
        {/* Step Icon */}
        <div className="w-16 h-16 rounded-2xl bg-[#FAF5E8] border-2 border-[#D4C3A3] flex items-center justify-center mx-auto shadow-sm">
          {activeStep.icon}
        </div>

        {/* Step Header */}
        <div>
          <span className="text-xs font-extrabold uppercase tracking-widest text-[#D97706]">
            {activeStep.title}
          </span>
          <h2 className="text-2xl sm:text-3xl font-black text-[#1E3F20] mt-1">
            {activeStep.heading}
          </h2>
        </div>

        {/* Large Readable Text Box for Outdoor Sunlight */}
        <div className="p-5 rounded-2xl bg-[#FAF5E8] border border-[#D4C3A3] text-base sm:text-lg font-extrabold text-[#1A1412] leading-relaxed shadow-inner">
          "{activeStep.body}"
        </div>

        {/* Tactical Guidance */}
        <p className="text-xs text-[#594A42] font-semibold italic max-w-md mx-auto">
          {activeStep.instruction}
        </p>

        {/* Large Tap Action Button (Min 48px height outdoor target) */}
        <button
          onClick={handleNextStep}
          className="w-full py-5 rounded-2xl rpg-button-primary text-lg sm:text-xl font-black tracking-wide flex items-center justify-center gap-3 cursor-pointer shadow-lg active:scale-98 transition-all"
        >
          <CheckCircle2 className="w-6 h-6 text-[#FEF3C7]" />
          <span>{activeStep.buttonText}</span>
        </button>
      </div>
    </div>
  );
};
