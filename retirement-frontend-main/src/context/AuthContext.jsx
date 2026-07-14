import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { apiClient } from '../lib/apiClient.js';
import { getItem, setItem, removeItem, STORAGE_KEYS } from '../lib/storage.js';

const AuthContext = createContext(null);

function isExpired(session) {
  if (!session?.expiresAt) return true;
  return Date.now() >= session.expiresAt;
}

export function AuthProvider({ children }) {
  const [session, setSession] = useState(() => {
    const stored = getItem(STORAGE_KEYS.SESSION);
    return stored && !isExpired(stored) ? stored : null;
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Clear a stale/expired session on mount and, thereafter, on an interval —
  // this is what makes "session handling" real rather than login-only.
  useEffect(() => {
    if (!session) return undefined;
    const remaining = session.expiresAt - Date.now();
    if (remaining <= 0) {
      setSession(null);
      removeItem(STORAGE_KEYS.SESSION);
      return undefined;
    }
    const timer = setTimeout(() => {
      setSession(null);
      removeItem(STORAGE_KEYS.SESSION);
    }, remaining);
    return () => clearTimeout(timer);
  }, [session]);

  const login = useCallback(async ({ principalType, participantId, planId }) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiClient.login({
        principal_type: principalType,
        participant_id: participantId || null,
        plan_id: planId || null,
      });
      const nextSession = {
        sessionToken: res.session_token,
        expiresAt: Date.now() + res.expires_in * 1000,
        principal: {
          principalType,
          participantId: participantId || null,
          planId: planId || null,
        },
      };
      setSession(nextSession);
      setItem(STORAGE_KEYS.SESSION, nextSession);
      return nextSession;
    } catch (err) {
      setError(err.message || 'Login failed');
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    setSession(null);
    removeItem(STORAGE_KEYS.SESSION);
  }, []);

  const value = useMemo(
    () => ({
      session,
      principal: session?.principal || null,
      isAuthenticated: Boolean(session) && !isExpired(session),
      isLoading,
      error,
      login,
      logout,
    }),
    [session, isLoading, error, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
