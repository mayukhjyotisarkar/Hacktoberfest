import { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { SafetyBanner } from './components/SafetyBanner';
import { LandingScreen } from './components/LandingScreen';
import { CreateRaidScreen } from './components/CreateRaidScreen';
import { PartyLobbyScreen } from './components/PartyLobbyScreen';
import { MissionBriefingScreen } from './components/MissionBriefingScreen';
import { ActiveRaidScreen } from './components/ActiveRaidScreen';
import { CompletionScreen } from './components/CompletionScreen';
import { SettingsModal } from './components/SettingsModal';
import { BadgeJournalModal } from './components/BadgeJournalModal';
import { JoinPartyModal } from './components/JoinPartyModal';

import type { AIConfig, Badge, MissionData, MissionRequest, Party, SquadMember } from './types';
import { storageService } from './services/storageService';
import { generateMission } from './services/aiService';
import { Compass } from 'lucide-react';

type Screen = 'landing' | 'create' | 'lobby' | 'briefing' | 'active' | 'completion';

export function App() {
  const [screen, setScreen] = useState<Screen>('landing');
  const [aiConfig, setAiConfig] = useState<AIConfig>(() => storageService.getAIConfig());
  const [badges, setBadges] = useState<Badge[]>(() => storageService.getBadges());

  // Party state
  const [party, setParty] = useState<Party>(() => ({
    code: storageService.generatePartyCode(),
    hostName: 'Explorer (You)',
    members: [
      { id: '1', name: 'Explorer (You)', avatar: '🛡️', isHost: true, ready: true }
    ],
    currentStep: 0,
    status: 'lobby'
  }));

  // Mission generation state
  const [mission, setMission] = useState<MissionData | null>(null);
  const [isAI, setIsAI] = useState<boolean>(false);
  const [modelUsed, setModelUsed] = useState<string | undefined>();
  const [loading, setLoading] = useState<boolean>(false);
  const [genError, setGenError] = useState<string | undefined>();

  // Modals state
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isJournalOpen, setIsJournalOpen] = useState(false);
  const [isJoinPartyOpen, setIsJoinPartyOpen] = useState(false);

  // Check for deep-linked party query param
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const partyParam = params.get('party');
    if (partyParam) {
      setParty(prev => ({ ...prev, code: partyParam.toUpperCase() }));
      setIsJoinPartyOpen(true);
    }
  }, []);

  const handleSaveAIConfig = (newConfig: AIConfig) => {
    setAiConfig(newConfig);
    storageService.saveAIConfig(newConfig);
  };

  const handleStartRaidFromLanding = () => {
    setScreen('create');
  };

  const handleJoinPartyFromLanding = () => {
    setIsJoinPartyOpen(true);
  };

  const handleJoinParty = (code: string, name: string) => {
    const newMember: SquadMember = {
      id: `member-${Date.now()}`,
      name: name,
      avatar: '🗡️',
      isHost: false,
      ready: true
    };

    setParty(prev => ({
      ...prev,
      code: code,
      members: [...prev.members.filter(m => !m.isHost), newMember]
    }));

    setScreen('lobby');
  };

  const handleCreateSubmit = async (request: MissionRequest) => {
    setParty(prev => ({ ...prev, raidConfig: request }));
    setScreen('lobby');
  };

  const handleAddMemberToLobby = (memberName: string) => {
    const avatars = ['🏹', '🧙‍♂️', '🧝', '🛡️', '⚔️'];
    const randomAvatar = avatars[Math.floor(Math.random() * avatars.length)];

    const newMember: SquadMember = {
      id: `member-${Date.now()}`,
      name: memberName,
      avatar: randomAvatar,
      isHost: false,
      ready: true
    };

    setParty(prev => ({
      ...prev,
      members: [...prev.members, newMember]
    }));
  };

  const handleLaunchRaidFromLobby = async () => {
    if (!party.raidConfig) return;

    setLoading(true);
    setGenError(undefined);

    const result = await generateMission(party.raidConfig, aiConfig);

    setMission(result.mission);
    setIsAI(result.isAI);
    setModelUsed(result.modelUsed);
    setGenError(result.errorMessage);

    setLoading(false);
    setScreen('briefing');
  };

  const handleBeginRaid = () => {
    setScreen('active');
  };

  const handleCompleteRaid = () => {
    if (!mission) return;

    const newBadge: Badge = {
      id: `badge-${Date.now()}`,
      name: mission.badge_name,
      vibe: party.raidConfig?.vibe || 'nature',
      title: mission.title,
      dateUnlocked: new Date().toISOString(),
      locationName: party.raidConfig?.landmark || 'Public Landmark',
      storyEnding: mission.story_ending
    };

    const updatedBadges = storageService.saveBadge(newBadge);
    setBadges(updatedBadges);
    storageService.saveCompletedRaid(mission);

    setScreen('completion');
  };

  const handleRunItBack = () => {
    setParty({
      code: storageService.generatePartyCode(),
      hostName: 'Explorer (You)',
      members: [
        { id: '1', name: 'Explorer (You)', avatar: '🛡️', isHost: true, ready: true }
      ],
      currentStep: 0,
      status: 'lobby'
    });
    setMission(null);
    setScreen('create');
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#F6EFE0] text-[#2C221E] selection:bg-[#1E3F20] selection:text-[#FEF3C7]">
      {/* Header Bar */}
      <Header
        aiConfig={aiConfig}
        badgeCount={badges.length}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenJournal={() => setIsJournalOpen(true)}
        onResetToHome={() => setScreen('landing')}
      />

      {/* Safety Banner */}
      <SafetyBanner />

      {/* Main Content Area */}
      <main className="flex-1 max-w-2xl w-full mx-auto px-4 py-6">
        {loading ? (
          <div className="py-20 text-center space-y-4 journal-card p-8">
            <Compass className="w-16 h-16 text-[#1E3F20] mx-auto animate-spin" style={{ animationDuration: '3s' }} />
            <div className="space-y-1">
              <h2 className="text-xl font-black text-[#1E3F20]">
                CONSULTING THE MAPS & LORE...
              </h2>
              <p className="text-xs text-[#594A42] font-semibold">
                {aiConfig.isEnabled
                  ? `Prompting local open model (${aiConfig.modelName}) for quest instructions...`
                  : 'Retrieving hand-crafted explorer lore...'}
              </p>
            </div>
          </div>
        ) : (
          <>
            {screen === 'landing' && (
              <LandingScreen
                onStartRaid={handleStartRaidFromLanding}
                onJoinParty={handleJoinPartyFromLanding}
              />
            )}

            {screen === 'create' && (
              <CreateRaidScreen
                onBack={() => setScreen('landing')}
                onSubmit={handleCreateSubmit}
              />
            )}

            {screen === 'lobby' && (
              <PartyLobbyScreen
                party={party}
                onStartRaid={handleLaunchRaidFromLobby}
                onAddMember={handleAddMemberToLobby}
                onBack={() => setScreen('create')}
              />
            )}

            {screen === 'briefing' && mission && (
              <MissionBriefingScreen
                mission={mission}
                isAI={isAI}
                modelUsed={modelUsed}
                errorMessage={genError}
                onBeginRaid={handleBeginRaid}
              />
            )}

            {screen === 'active' && mission && (
              <ActiveRaidScreen
                mission={mission}
                onCompleteRaid={handleCompleteRaid}
              />
            )}

            {screen === 'completion' && mission && (
              <CompletionScreen
                mission={mission}
                onRunItBack={handleRunItBack}
                onOpenJournal={() => setIsJournalOpen(true)}
              />
            )}
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-[#D4C3A3] bg-[#EADCB9]/40 py-4 px-4 text-center text-xs text-[#594A42]">
        <div className="max-w-2xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2 font-medium">
          <span>⚔️ <strong>Raid Outside</strong> — Co-op mini-adventures for desk-bound friends</span>
          <span className="text-[11px] opacity-80">Privacy First • Open-Source AI • No Location Tracking</span>
        </div>
      </footer>

      {/* Modals */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        config={aiConfig}
        onSave={handleSaveAIConfig}
      />

      <BadgeJournalModal
        isOpen={isJournalOpen}
        onClose={() => setIsJournalOpen(false)}
        badges={badges}
      />

      <JoinPartyModal
        isOpen={isJoinPartyOpen}
        onClose={() => setIsJoinPartyOpen(false)}
        onJoin={handleJoinParty}
      />
    </div>
  );
}

export default App;
