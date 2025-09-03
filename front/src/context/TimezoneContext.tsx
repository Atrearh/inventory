import React, { createContext, useState, useEffect, useContext, ReactNode } from 'react';
import { apiInstance } from '../api/api';

interface TimezoneContextType {
  timezone: string;
  setTimezone: (tz: string) => void;
  isLoading: boolean;
}

const TimezoneContext = createContext<TimezoneContextType | undefined>(undefined);

export const TimezoneProvider = ({ children }: { children: ReactNode }) => {
  const [timezone, setTimezoneState] = useState<string>(
    Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  );
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchTimezone = async () => {
      try {
        const response = await apiInstance.get('/settings');
        if (response.data.timezone) {
          setTimezoneState(response.data.timezone);
        }
      } catch (error) {
        console.error('Failed to fetch timezone setting, using local timezone', error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchTimezone();
  }, []);

  const setTimezone = (tz: string) => {
    setTimezoneState(tz);
  };

  return (
    <TimezoneContext.Provider value={{ timezone, setTimezone, isLoading }}>
      {children}
    </TimezoneContext.Provider>
  );
};

export const useTimezone = () => {
  const context = useContext(TimezoneContext);
  if (context === undefined) {
    throw new Error('useTimezone must be used within a TimezoneProvider');
  }
  return context;
};