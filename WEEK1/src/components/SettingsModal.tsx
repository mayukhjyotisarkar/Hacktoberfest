import React, { useState } from 'react';
import { X, Cpu, CheckCircle2, AlertTriangle, HelpCircle } from 'lucide-react';
import type { AIConfig } from '../types';
import { testAIConnection } from '../services/aiService';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  config: AIConfig;
  onSave: (newConfig: AIConfig) => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  config,
  onSave,
}) => {
  const [formData, setFormData] = useState<AIConfig>(config);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  if (!isOpen) return null;

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    const result = await testAIConnection(formData);
    setTestResult(result);
    setTesting(false);
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(formData);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="journal-card max-w-lg w-full p-6 relative max-h-[90vh] overflow-y-auto animate-in fade-in zoom-in duration-150">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg bg-[#EADCB9] text-[#3E2723] hover:bg-[#DFCDA5]"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-[#1E3F20] text-[#FEF3C7] flex items-center justify-center border border-[#D97706]">
            <Cpu className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-[#1E3F20]">Open-Source AI Setup</h2>
            <p className="text-xs text-[#594A42]">Configure local open-weight model endpoints</p>
          </div>
        </div>

        <form onSubmit={handleSave} className="space-y-4">
          {/* Enable Toggle */}
          <div className="flex items-center justify-between p-3 rounded-lg bg-[#F6EFE0] border border-[#D4C3A3]">
            <div>
              <span className="font-bold text-sm text-[#2C221E]">Use Local Open-Weight AI</span>
              <p className="text-xs text-[#594A42]">Generates custom quest lore locally with zero data tracking</p>
            </div>
            <input
              type="checkbox"
              checked={formData.isEnabled}
              onChange={(e) => setFormData({ ...formData, isEnabled: e.target.checked })}
              className="w-5 h-5 accent-[#1E3F20] cursor-pointer"
            />
          </div>

          {/* Base URL */}
          <div>
            <label className="block text-xs font-bold text-[#3E2723] mb-1">
              OpenAI-Compatible Base Endpoint URL
            </label>
            <input
              type="text"
              value={formData.baseUrl}
              onChange={(e) => setFormData({ ...formData, baseUrl: e.target.value })}
              placeholder="e.g. http://localhost:11434/v1"
              className="w-full px-3 py-2 rounded-lg bg-white border border-[#C4B188] text-sm text-[#2C221E] font-mono focus:outline-hidden focus:border-[#1E3F20]"
              required
            />
            <p className="text-[11px] text-[#594A42] mt-1">
              Default for Ollama: <code className="bg-[#EADCB9] px-1 rounded">http://localhost:11434/v1</code> | LM Studio: <code className="bg-[#EADCB9] px-1 rounded">http://localhost:1234/v1</code>
            </p>
          </div>

          {/* Model Name */}
          <div>
            <label className="block text-xs font-bold text-[#3E2723] mb-1">
              Model Identifier
            </label>
            <input
              type="text"
              value={formData.modelName}
              onChange={(e) => setFormData({ ...formData, modelName: e.target.value })}
              placeholder="e.g. llama3.2, mistral, or qwen2.5"
              className="w-full px-3 py-2 rounded-lg bg-white border border-[#C4B188] text-sm text-[#2C221E] font-mono focus:outline-hidden focus:border-[#1E3F20]"
              required
            />
          </div>

          {/* API Key */}
          <div>
            <label className="block text-xs font-bold text-[#3E2723] mb-1">
              API Key (Optional for Local Models)
            </label>
            <input
              type="password"
              value={formData.apiKey}
              onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
              placeholder="ollama or dummy-key"
              className="w-full px-3 py-2 rounded-lg bg-white border border-[#C4B188] text-sm text-[#2C221E] font-mono focus:outline-hidden focus:border-[#1E3F20]"
            />
          </div>

          {/* Test connection output */}
          {testResult && (
            <div
              className={`p-3 rounded-lg text-xs font-semibold flex items-start gap-2 ${
                testResult.success
                  ? 'bg-[#E8F5E9] text-[#1B5E20] border border-[#A5D6A7]'
                  : 'bg-[#FFEBEE] text-[#C62828] border border-[#EF9A9A]'
              }`}
            >
              {testResult.success ? (
                <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
              ) : (
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              )}
              <div>{testResult.message}</div>
            </div>
          )}

          {/* Setup Guide Box */}
          <div className="p-3 bg-[#FAF5E8] border border-[#D4C3A3] rounded-lg text-xs space-y-1.5 text-[#594A42]">
            <div className="font-bold text-[#3E2723] flex items-center gap-1.5">
              <HelpCircle className="w-4 h-4 text-[#D97706]" /> Quick Setup Guide for Ollama:
            </div>
            <ol className="list-decimal list-inside space-y-1 pl-1">
              <li>Install <strong className="font-semibold text-[#1E3F20]">Ollama</strong> (<code className="bg-[#EADCB9] px-1">ollama.com</code>)</li>
              <li>Run command: <code className="bg-[#EADCB9] px-1 font-mono">ollama run llama3.2</code></li>
              <li>Set endpoint: <code className="bg-[#EADCB9] px-1 font-mono">http://localhost:11434/v1</code></li>
              <li>If model is offline, the app automatically uses hand-written explorer missions!</li>
            </ol>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={handleTest}
              disabled={testing}
              className="flex-1 py-2 px-3 rounded-lg rpg-button-secondary text-xs flex items-center justify-center gap-1"
            >
              {testing ? 'Pinging Endpoint...' : 'Test Connection'}
            </button>
            <button
              type="submit"
              className="flex-1 py-2 px-3 rounded-lg rpg-button-primary text-xs flex items-center justify-center gap-1"
            >
              Save AI Settings
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
