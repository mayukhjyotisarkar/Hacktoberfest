import React, { useState } from 'react';
import { Users, Copy, Check, Play, UserPlus, ArrowLeft, Sparkles, MapPin, Clock, Footprints } from 'lucide-react';
import type { Party } from '../types';

interface PartyLobbyScreenProps {
  party: Party;
  onStartRaid: () => void;
  onAddMember: (name: string) => void;
  onBack: () => void;
}

export const PartyLobbyScreen: React.FC<PartyLobbyScreenProps> = ({
  party,
  onStartRaid,
  onAddMember,
  onBack,
}) => {
  const [copied, setCopied] = useState(false);
  const [newMemberName, setNewMemberName] = useState('');
  const [isAdding, setIsAdding] = useState(false);

  const inviteLink = `${window.location.origin}?party=${party.code}`;

  const handleCopy = () => {
    navigator.clipboard.writeText(inviteLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const handleAddMemberSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (newMemberName.trim()) {
      onAddMember(newMemberName.trim());
      setNewMemberName('');
      setIsAdding(false);
    }
  };

  return (
    <div className="space-y-6 py-2 animate-in fade-in duration-150">
      {/* Top Navigation */}
      <button
        onClick={onBack}
        className="inline-flex items-center gap-1.5 text-xs font-bold text-[#594A42] hover:text-[#1E3F20] transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Configuration</span>
      </button>

      {/* Main Party Card */}
      <div className="journal-card p-6 border-2 border-[#D4C3A3] space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between border-b-2 border-[#D4C3A3] pb-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-[#1E3F20] text-[#FEF3C7] flex items-center justify-center border-2 border-[#D97706] shadow-xs">
              <Users className="w-7 h-7" />
            </div>
            <div>
              <h2 className="text-2xl font-black text-[#1E3F20]">PARTY LOBBY</h2>
              <p className="text-xs text-[#594A42] font-semibold">
                Hosted by <span className="text-[#1E3F20] font-bold">{party.hostName}</span>
              </p>
            </div>
          </div>
        </div>

        {/* Short Join Code & Invite Link Box */}
        <div className="p-4 rounded-xl bg-[#FAF5E8] border border-[#D4C3A3] space-y-3">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
            <div>
              <span className="text-[10px] font-black uppercase tracking-widest text-[#5C3D2E]">
                PARTY JOIN CODE
              </span>
              <div className="text-3xl font-black tracking-wider text-[#1E3F20] font-mono">
                {party.code}
              </div>
            </div>

            <button
              onClick={handleCopy}
              className="w-full sm:w-auto px-4 py-2.5 rounded-lg rpg-button-secondary text-xs flex items-center justify-center gap-1.5 cursor-pointer shadow-xs"
            >
              {copied ? (
                <>
                  <Check className="w-4 h-4 text-[#1E3F20]" />
                  <span>Invite Link Copied!</span>
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4" />
                  <span>Copy Invite Link</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Selected Raid Summary Pill */}
        {party.raidConfig && (
          <div className="p-3 bg-[#EADCB9]/60 rounded-lg border border-[#C4B188] flex flex-wrap items-center justify-between gap-2 text-xs text-[#3E2723] font-semibold">
            <span className="flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5 text-[#D97706]" />
              <span className="capitalize">{party.raidConfig.vibe} Vibe</span>
            </span>
            <span className="flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-[#1E3F20]" />
              <span>{party.raidConfig.duration} Mins</span>
            </span>
            <span className="flex items-center gap-1">
              <Footprints className="w-3.5 h-3.5 text-[#5C3D2E]" />
              <span className="capitalize">{party.raidConfig.effort}</span>
            </span>
            <span className="flex items-center gap-1 truncate max-w-[150px]">
              <MapPin className="w-3.5 h-3.5 text-[#991B1B]" />
              <span className="truncate">{party.raidConfig.landmark}</span>
            </span>
          </div>
        )}

        {/* Squad Roster */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-black uppercase tracking-widest text-[#5C3D2E]">
              SQUAD MEMBERS ({party.members.length})
            </h3>

            <button
              onClick={() => setIsAdding(!isAdding)}
              className="text-xs font-bold text-[#1E3F20] hover:underline flex items-center gap-1"
            >
              <UserPlus className="w-3.5 h-3.5" />
              <span>Add Friend (Simulate)</span>
            </button>
          </div>

          {/* Add member form */}
          {isAdding && (
            <form onSubmit={handleAddMemberSubmit} className="mb-3 flex gap-2">
              <input
                type="text"
                value={newMemberName}
                onChange={(e) => setNewMemberName(e.target.value)}
                placeholder="Friend's Name"
                className="flex-1 px-3 py-1.5 text-xs rounded-lg bg-white border border-[#C4B188]"
                autoFocus
              />
              <button
                type="submit"
                className="px-3 py-1.5 rounded-lg rpg-button-primary text-xs font-bold"
              >
                Add
              </button>
            </form>
          )}

          <div className="space-y-2">
            {party.members.map((m) => (
              <div
                key={m.id}
                className="p-3 rounded-lg bg-white border border-[#D4C3A3] flex items-center justify-between shadow-xs"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-[#1E3F20] text-[#FEF3C7] font-bold text-xs flex items-center justify-center border border-[#D97706]">
                    {m.avatar}
                  </div>
                  <div>
                    <div className="font-extrabold text-sm text-[#1E3F20] flex items-center gap-1.5">
                      <span>{m.name}</span>
                      {m.isHost && (
                        <span className="text-[10px] font-black bg-[#D97706] text-white px-1.5 py-0.2 rounded-full">
                          HOST
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1 text-xs font-bold text-[#1B5E20]">
                  <Check className="w-4 h-4 text-[#81C784]" />
                  <span>Ready</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Primary Start Button */}
        <div className="pt-2">
          <button
            onClick={onStartRaid}
            className="w-full py-4 rounded-xl rpg-button-primary text-base flex items-center justify-center gap-2 cursor-pointer shadow-md"
          >
            <Play className="w-5 h-5 text-[#FEF3C7] fill-current" />
            <span>
              {party.members.length === 1 ? 'START SOLO (DEMO MODE)' : 'LAUNCH RAID WITH SQUAD'}
            </span>
          </button>
          <p className="text-center text-[11px] text-[#594A42] mt-2">
            💡 You can launch immediately as a solo explorer for testing and demo purposes!
          </p>
        </div>
      </div>
    </div>
  );
};
