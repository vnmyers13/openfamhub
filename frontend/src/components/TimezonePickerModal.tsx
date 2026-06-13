import { useState } from 'react';

interface TimezoneOption {
  value: string;
  label: string;
}

const TIMEZONE_OPTIONS: TimezoneOption[] = [
  { value: 'America/New_York', label: 'Eastern Time (UTC-5)' },
  { value: 'America/Chicago', label: 'Central Time (UTC-6)' },
  { value: 'America/Denver', label: 'Mountain Time (UTC-7)' },
  { value: 'America/Los_Angeles', label: 'Pacific Time (UTC-8)' },
  { value: 'America/Anchorage', label: 'Alaska Time (UTC-9)' },
  { value: 'Pacific/Honolulu', label: 'Hawaii Time (UTC-10)' },
  { value: 'UTC', label: 'UTC' },
];

interface TimezonePickerModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentTimezone: string;
  onSave: (timezone: string) => void;
  saving?: boolean;
}

export default function TimezonePickerModal({
  isOpen,
  onClose,
  currentTimezone,
  onSave,
  saving = false,
}: TimezonePickerModalProps) {
  const [selected, setSelected] = useState(currentTimezone);

  if (!isOpen) return null;

  const handleSave = () => {
    onSave(selected);
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 rounded-xl p-6 w-full max-w-md border border-slate-700">
        <h3 className="text-xl font-bold text-white mb-4">Wall Display Timezone</h3>

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Timezone</label>
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              className="w-full p-3 rounded-lg bg-white/5 border border-white/20 focus:border-white/50 focus:outline-none text-white"
            >
              {TIMEZONE_OPTIONS.map((tz) => (
                <option key={tz.value} value={tz.value}>
                  {tz.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex gap-3 justify-end">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-white/5 border border-white/20 text-gray-400 hover:text-white transition"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
