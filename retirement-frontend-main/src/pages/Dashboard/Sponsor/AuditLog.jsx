import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '../../../context/AuthContext.jsx';
import { apiClient } from '../../../lib/apiClient.js';
import { AUDIT_UPDATED_EVENT } from '../../../lib/events.js';
import FilterSelect from '../../../components/ui/FilterSelect.jsx';
import AuditTable from '../../../components/sponsor/AuditTable.jsx';
import LoadingState from '../../../components/ui/LoadingState.jsx';
import { titleCase } from '../../../lib/format.js';

const RESULT_OPTIONS = [
  { value: 'all', label: 'All Results' },
  { value: 'approved', label: 'Approved' },
  { value: 'denied', label: 'Denied' },
];

export default function AuditLog() {
  const { principal } = useAuth();
  const [entries, setEntries] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [resultFilter, setResultFilter] = useState('all');
  const [actionFilter, setActionFilter] = useState('all');
  const [sortKey, setSortKey] = useState('timestamp');
  const [sortDir, setSortDir] = useState('desc');

  const load = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setIsLoading(true);
    try {
      const res = await apiClient.getAuditLog();
      const raw = res.records || res.entries || [];
      setEntries(raw.map((r) => ({
        id:               r.audit_id || r.id,
        timestamp:        r.timestamp,
        participant_id:   r.participant_id,
        participant_name: r.participant_name || r.participant_id,
        plan_id:          r.plan_id,
        action:         r.action,
        result:         r.authorized != null
          ? (r.authorized ? 'approved' : 'denied')
          : (r.result || '—'),
        autonomy:       r.autonomy_level || r.autonomy || '—',
        citation:       r.erisa_citation || '—',
        note:           r.denial_reason || r.denial_code || '—',
      })));
    } catch {
      // leave existing state on error
    } finally {
      if (!silent) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    function onAuditUpdated() {
      load({ silent: true });
    }
    window.addEventListener(AUDIT_UPDATED_EVENT, onAuditUpdated);
    return () => window.removeEventListener(AUDIT_UPDATED_EVENT, onAuditUpdated);
  }, [load]);

  const planScoped = useMemo(
    () => entries.filter((e) => !principal?.planId || e.plan_id === principal.planId),
    [entries, principal?.planId],
  );

  const actionOptions = useMemo(() => {
    const unique = Array.from(new Set(planScoped.map((e) => e.action)));
    return [{ value: 'all', label: 'All Actions' }, ...unique.map((a) => ({ value: a, label: titleCase(a) }))];
  }, [planScoped]);

  const filtered = useMemo(
    () =>
      planScoped.filter(
        (e) =>
          (resultFilter === 'all' || e.result === resultFilter) &&
          (actionFilter === 'all' || e.action === actionFilter),
      ),
    [planScoped, resultFilter, actionFilter],
  );

  const sorted = useMemo(() => {
    const copy = [...filtered];
    copy.sort((a, b) => {
      const av = a[sortKey] ?? '';
      const bv = b[sortKey] ?? '';
      if (sortKey === 'timestamp') {
        const diff = new Date(av).getTime() - new Date(bv).getTime();
        return sortDir === 'asc' ? diff : -diff;
      }
      const cmp = String(av).localeCompare(String(bv));
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return copy;
  }, [filtered, sortKey, sortDir]);

  function handleSort(key) {
    if (key === sortKey) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  }

  if (isLoading) {
    return <LoadingState label="Loading audit log…" />;
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-text-muted max-w-2xl">
        Every compliance decision made on this plan, with the citation behind it.
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <FilterSelect label="Result" value={resultFilter} onChange={setResultFilter} options={RESULT_OPTIONS} />
        <FilterSelect label="Action" value={actionFilter} onChange={setActionFilter} options={actionOptions} />
        <span className="text-xs text-text-faint sm:ml-auto">
          {sorted.length} of {planScoped.length} entries · ERISA §107 six-year retention
        </span>
      </div>

      <div className="card p-4 sm:p-6">
        <AuditTable entries={sorted} sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
      </div>
    </div>
  );
}
