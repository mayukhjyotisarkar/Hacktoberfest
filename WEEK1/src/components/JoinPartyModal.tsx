import React, { useState } from 'react';
import { X, Users, ArrowRight } from 'lucide-react';

interface JoinPartyModalProps {
  isOpen: boolean;
  onClose: () => void;
  onJoin: (code: string, name: string) => void;
}

export const JoinPartyModal: React.FC<JoinPartyModalProps> = ({
  isOpen,
  onClose,
  onJoin,
}) => {
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim()) {
      setError('Please enter a party join code.');
      return;
    }
    if (!name.trim()) {
      setError('Please enter your explorer name.');
      return;
    }
    setError('');
    onJoin(code.trim().toUpperCase(), name.trim());
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="journal-card max-w-md w-full p-6 relative animate-in fade-in zoom-in duration-150">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg bg-[#EADCB9] text-[#3E2723] hover:bg-[#DFCDA5]"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-[#1E3F20] text-[#FEF3C7] flex items-center justify-center border border-[#D97706]">
            <Users className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-extrabold text-[#1E3F20]">JOIN A SQUAD</h2>
            <p className="text-xs text-[#594A42]">Enter the party code shared by your host</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-[#3E2723] mb-1">
              Your Explorer Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Alex, Sam, or Scout-1"
              className="w-full px-3 py-2.5 rounded-lg bg-white border border-[#C4B188] text-sm text-[#2C221E] focus:outline-hidden focus:border-[#1E3F20]"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-[#3E2723] mb-1">
              Party Join Code
            </label>
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              placeholder="e.g. RAID-794"
              className="w-full px-3 py-2.5 rounded-lg bg-white border border-[#C4B188] text-sm text-[#2C221E] font-mono font-bold tracking-wider text-center uppercase focus:outline-hidden focus:border-[#1E3F20]"
              required
            />
          </div>

          {error && (
            <p className="text-xs text-[#991B1B] font-bold bg-[#FEE2E2] p-2 rounded-md">
              {error}
            </p>
          )}

          <button
            type="submit"
            className="w-full py-3 rounded-lg rpg-button-primary text-sm flex items-center justify-center gap-2 mt-2"
          >
            <span>Enter Party Lobby</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
};
