import React, { useState, useEffect } from 'react';
import { Compass, Clock, Footprints, MapPin, Sparkles, Search, Feather, TreePine, ArrowLeft, AlertCircle, Globe, CheckCircle2, Loader2 } from 'lucide-react';
import type { Duration, Effort, MissionRequest, Vibe } from '../types';
import { fetchOSMFeatures } from '../services/osmService';
import type { LocationFeatureResult } from '../services/osmService';

interface CreateRaidScreenProps {
  onBack: () => void;
  onSubmit: (request: MissionRequest) => void;
}

const VIBE_OPTIONS: { vibe: Vibe; title: string; desc: string; icon: React.ReactNode }[] = [
  {
    vibe: 'mystery',
    title: 'Mystery',
    desc: 'Uncover hidden street codes & ciphers',
    icon: <Search className="w-5 h-5 text-purple-700" />,
  },
  {
    vibe: 'nature',
    title: 'Nature',
    desc: 'Explore urban flora, trees & horizons',
    icon: <TreePine className="w-5 h-5 text-emerald-700" />,
  },
  {
    vibe: 'silly',
    title: 'Silly',
    desc: 'Hilarious squad challenges & pigeon secret ops',
    icon: <Feather className="w-5 h-5 text-amber-700" />,
  },
  {
    vibe: 'fantasy',
    title: 'Fantasy',
    desc: 'Awaken ancient stone portals & stargazers',
    icon: <Sparkles className="w-5 h-5 text-cyan-700" />,
  },
];

const TIME_OPTIONS: Duration[] = [15, 30, 45];

export const CreateRaidScreen: React.FC<CreateRaidScreenProps> = ({
  onBack,
  onSubmit,
}) => {
  const [vibe, setVibe] = useState<Vibe>('nature');
  const [duration, setDuration] = useState<Duration>(15);
  const [effort, setEffort] = useState<Effort>('easy');
  const [landmark, setLandmark] = useState('');
  const [error, setError] = useState('');

  // OSM feature state
  const [osmResult, setOsmResult] = useState<LocationFeatureResult | null>(null);
  const [isSearchingOSM, setIsSearchingOSM] = useState(false);

  // Debounced search to OpenStreetMap
  useEffect(() => {
    if (!landmark.trim() || landmark.trim().length < 3) {
      setOsmResult(null);
      setIsSearchingOSM(false);
      return;
    }

    setIsSearchingOSM(true);
    const timer = setTimeout(async () => {
      const res = await fetchOSMFeatures(landmark.trim());
      setOsmResult(res);
      setIsSearchingOSM(false);
    }, 700);

    return () => clearTimeout(timer);
  }, [landmark]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!landmark.trim()) {
      setError('Please provide a nearby public place or landmark (e.g., "City Park", "Library Fountain").');
      return;
    }
    setError('');
    onSubmit({
      vibe,
      duration,
      effort,
      landmark: landmark.trim(),
      osmFeatures: osmResult?.features,
      isOSMPlaceMatched: osmResult?.isOSMPlaceMatched
    });
  };

  return (
    <div className="space-y-6 py-2 animate-in fade-in duration-150">
      {/* Top Navigation */}
      <button
        onClick={onBack}
        className="inline-flex items-center gap-1.5 text-xs font-bold text-[#594A42] hover:text-[#1E3F20] transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Landing</span>
      </button>

      {/* Screen Card */}
      <div className="journal-card p-6 border-2 border-[#D4C3A3]">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-[#1E3F20] text-[#FEF3C7] flex items-center justify-center border border-[#D97706]">
            <Compass className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-2xl font-black text-[#1E3F20]">CREATE A RAID</h2>
            <p className="text-xs text-[#594A42] font-semibold">Customize your squad's mini-expedition</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* 1. Choose Vibe */}
          <div>
            <label className="block text-xs font-black uppercase tracking-wider text-[#5C3D2E] mb-2">
              1. Choose Mission Vibe
            </label>
            <div className="grid grid-cols-2 gap-2.5">
              {VIBE_OPTIONS.map((opt) => (
                <button
                  key={opt.vibe}
                  type="button"
                  onClick={() => setVibe(opt.vibe)}
                  className={`p-3 rounded-xl border text-left transition-all cursor-pointer flex flex-col justify-between ${
                    vibe === opt.vibe
                      ? 'bg-[#FAF5E8] border-[#1E3F20] ring-2 ring-[#1E3F20]/20 shadow-xs'
                      : 'bg-white border-[#D4C3A3] hover:border-[#5C3D2E]'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-extrabold text-sm text-[#1E3F20]">{opt.title}</span>
                    {opt.icon}
                  </div>
                  <span className="text-[11px] text-[#594A42] leading-tight">{opt.desc}</span>
                </button>
              ))}
            </div>
          </div>

          {/* 2. Time Available */}
          <div>
            <label className="block text-xs font-black uppercase tracking-wider text-[#5C3D2E] mb-2 flex items-center gap-1">
              <Clock className="w-4 h-4 text-[#D97706]" />
              <span>2. Time Available</span>
            </label>
            <div className="grid grid-cols-3 gap-2">
              {TIME_OPTIONS.map((time) => (
                <button
                  key={time}
                  type="button"
                  onClick={() => setDuration(time)}
                  className={`py-2.5 px-3 rounded-xl border font-extrabold text-sm transition-all cursor-pointer ${
                    duration === time
                      ? 'bg-[#1E3F20] text-[#FEF3C7] border-[#142E16] shadow-xs'
                      : 'bg-white text-[#3E2723] border-[#D4C3A3] hover:border-[#5C3D2E]'
                  }`}
                >
                  {time} Mins
                </button>
              ))}
            </div>
          </div>

          {/* 3. Walking Effort */}
          <div>
            <label className="block text-xs font-black uppercase tracking-wider text-[#5C3D2E] mb-2 flex items-center gap-1">
              <Footprints className="w-4 h-4 text-[#D97706]" />
              <span>3. Walking Effort</span>
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setEffort('easy')}
                className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                  effort === 'easy'
                    ? 'bg-[#1E3F20] text-[#FEF3C7] border-[#142E16] shadow-xs'
                    : 'bg-white text-[#3E2723] border-[#D4C3A3] hover:border-[#5C3D2E]'
                }`}
              >
                <div className="font-extrabold text-sm">Gentle Stroll (Easy)</div>
                <div className={`text-[11px] ${effort === 'easy' ? 'text-[#FEF3C7]/80' : 'text-[#594A42]'}`}>
                  Short distance, relaxed pacing
                </div>
              </button>

              <button
                type="button"
                onClick={() => setEffort('adventurous')}
                className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                  effort === 'adventurous'
                    ? 'bg-[#1E3F20] text-[#FEF3C7] border-[#142E16] shadow-xs'
                    : 'bg-white text-[#3E2723] border-[#D4C3A3] hover:border-[#5C3D2E]'
                }`}
              >
                <div className="font-extrabold text-sm">Brisk Explorer (Adventurous)</div>
                <div className={`text-[11px] ${effort === 'adventurous' ? 'text-[#FEF3C7]/80' : 'text-[#594A42]'}`}>
                  Further walk, active search
                </div>
              </button>
            </div>
          </div>

          {/* 4. Landmark Input with OpenStreetMap Feature Lookup */}
          <div>
            <label className="block text-xs font-black uppercase tracking-wider text-[#5C3D2E] mb-1 flex items-center justify-between">
              <span className="flex items-center gap-1">
                <MapPin className="w-4 h-4 text-[#D97706]" />
                <span>4. Nearby Public Place or Landmark</span>
              </span>
              <span className="text-[10px] text-[#1E3F20] font-bold flex items-center gap-1">
                <Globe className="w-3 h-3 text-[#1B5E20]" />
                <span>OpenStreetMap Verified</span>
              </span>
            </label>

            <div className="relative">
              <input
                type="text"
                value={landmark}
                onChange={(e) => setLandmark(e.target.value)}
                placeholder="e.g. Central Park Fountain, Washington Square, Campus Library"
                className="w-full px-3.5 py-3 rounded-xl bg-white border-2 border-[#C4B188] text-sm text-[#2C221E] font-medium focus:outline-hidden focus:border-[#1E3F20]"
              />

              {isSearchingOSM && (
                <div className="absolute right-3 top-3.5 flex items-center gap-1 text-xs text-[#594A42]">
                  <Loader2 className="w-4 h-4 animate-spin text-[#D97706]" />
                </div>
              )}
            </div>

            {/* OSM place match; broad classification is not on-site verification. */}
            {osmResult && (
              <div className="mt-2 p-2.5 rounded-lg bg-[#E8F5E9] border border-[#81C784] text-xs space-y-1 animate-in fade-in">
                <div className="flex items-center justify-between font-bold text-[#1B5E20]">
                  <span className="flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#2E7D32]" />
                    <span>OpenStreetMap place lookup:</span>
                  </span>
                  {osmResult.isOSMPlaceMatched && (
                    <span className="bg-[#2E7D32] text-white text-[9px] font-black px-1.5 py-0.2 rounded-full">
                      OSM MATCH
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap gap-1 pt-0.5">
                  {osmResult.features.map((feat, idx) => (
                    <span
                      key={idx}
                      className="bg-white border border-[#A5D6A7] text-[#1B5E20] font-semibold text-[11px] px-2 py-0.5 rounded-md"
                    >
                      {feat}
                    </span>
                  ))}
                  {osmResult.features.length === 0 && (
                    <span className="text-[#594A42]">No mapped place classification available.</span>
                  )}
                </div>
                <p className="text-[10px] text-[#594A42]">Map data does not verify which features are physically present or accessible.</p>
              </div>
            )}

            <p className="text-[11px] text-[#594A42] mt-1">
              OpenStreetMap can match the place name, but it cannot verify on-site features. Check your surroundings and stay in public areas.
            </p>
          </div>

          {error && (
            <div className="p-3 rounded-lg bg-[#FEE2E2] border border-[#FCA5A5] text-[#991B1B] text-xs font-bold flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            className="w-full py-4 rounded-xl rpg-button-primary text-base flex items-center justify-center gap-2 cursor-pointer shadow-md"
          >
            <Sparkles className="w-5 h-5 text-[#FEF3C7]" />
            <span>FORM SQUAD PARTY</span>
          </button>
        </form>
      </div>
    </div>
  );
};
