import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  getHealth, getSnapshot, getCampaigns, getPlatformSummary,
  getActionHistory, getConfig, getPendingActions
} from '../services/api';

const DataContext = createContext(null);

export function DataProvider({ children }) {
  const [health, setHealth] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [campaigns, setCampaigns] = useState([]);
  const [platformData, setPlatformData] = useState(null);
  const [actions, setActions] = useState([]);
  const [pending, setPending] = useState([]);
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    try {
      const [h, s, c, p, a, cfg, pend] = await Promise.all([
        getHealth().catch(() => null),
        getSnapshot().catch(() => null),
        getCampaigns().catch(() => []),
        getPlatformSummary().catch(() => null),
        getActionHistory(50).catch(() => []),
        getConfig().catch(() => null),
        getPendingActions().catch(() => []),
      ]);
      setHealth(h);
      setSnapshot(s);
      setCampaigns(Array.isArray(c) ? c : (c?.campaigns || []));
      setPlatformData(p);
      setActions(Array.isArray(a) ? a : (a?.actions || []));
      setConfig(cfg);
      setPending(Array.isArray(pend) ? pend : []);
    } catch (err) {
      console.error('Fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 60000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  return (
    <DataContext.Provider value={{
      health, snapshot, campaigns, platformData, actions,
      pending, config, loading, refetch: fetchAll
    }}>
      {children}
    </DataContext.Provider>
  );
}

export function useData() {
  const ctx = useContext(DataContext);
  if (!ctx) throw new Error('useData must be inside DataProvider');
  return ctx;
}
