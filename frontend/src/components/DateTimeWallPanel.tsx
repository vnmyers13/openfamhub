import { useState, useEffect, useCallback, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { settingsAPI } from '../api/client';
import { useAuthStore } from '../stores/auth';
import TimezonePickerModal from './TimezonePickerModal';

export default function DateTimeWallPanel() {
  const currentUser = useAuthStore((s) => s.user);
  const isAdmin = currentUser?.role === 'admin';
  const [showTimezoneModal, setShowTimezoneModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [currentTime, setCurrentTime] = useState<Date>(new Date());
  const intervalRef = useRef<number | null>(null);

  const { data: timezoneData, isLoading } = useQuery({
    queryKey: ['wall-timezone'],
    queryFn: () => settingsAPI.getTimezone(),
    staleTime: Infinity,
  });

  const timezone = timezoneData?.timezone || 'UTC';

  // Update clock every second
  const updateClock = useCallback(() => {
    setCurrentTime(new Date());
  }, []);

  useEffect(() => {
    intervalRef.current = window.setInterval(updateClock, 1000);
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [updateClock]);

  // Format date/time using Intl.DateTimeFormat
  const formatDateTime = useCallback((date: Date, tz: string) => {
    const dateOptions: Intl.DateTimeFormatOptions = {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      timeZone: tz,
    };

    const timeOptions: Intl.DateTimeFormatOptions = {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
      timeZone: tz,
    };

    const tzOptions: Intl.DateTimeFormatOptions = {
      timeZoneName: 'short',
      timeZone: tz,
    };

    const dateStr = new Intl.DateTimeFormat('en-US', dateOptions).format(date);
    const timeStr = new Intl.DateTimeFormat('en-US', timeOptions).format(date);
    const tzAbbr = new Intl.DateTimeFormat('en-US', tzOptions).format(date);

    return { dateStr, timeStr, timezone: tzAbbr };
  }, []);

  const { dateStr, timeStr, timezone: tzAbbr } = formatDateTime(currentTime, timezone);

  const handleSaveTimezone = async (newTimezone: string) => {
    setSaving(true);
    try {
      await settingsAPI.updateTimezone(newTimezone);
      setShowTimezoneModal(false);
    } catch {
      alert('Failed to update timezone');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-slate-800/50 backdrop-blur rounded-xl p-4 border border-slate-700 h-full flex flex-col justify-center relative">
      {isLoading ? (
        <div className="text-slate-400 text-xl">Loading...</div>
      ) : (
        <>
          <div className="text-xl font-semibold text-white">{dateStr}</div>
          <div className="text-3xl font-bold text-white mt-1">
            {timeStr} <span className="text-slate-400 text-lg">{tzAbbr}</span>
          </div>
          {isAdmin && (
            <button
              onClick={() => setShowTimezoneModal(true)}
              className="absolute top-2 right-2 text-slate-500 hover:text-white transition text-lg"
              title="Edit timezone"
            >
              ⚙
            </button>
          )}
        </>
      )}

      <TimezonePickerModal
        isOpen={showTimezoneModal}
        onClose={() => setShowTimezoneModal(false)}
        currentTimezone={timezone}
        onSave={handleSaveTimezone}
        saving={saving}
      />
    </div>
  );
}
