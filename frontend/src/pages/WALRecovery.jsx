import React, { useEffect, useState } from 'react';
import { 
  FileText, 
  ShieldCheck, 
  AlertTriangle, 
  RotateCcw, 
  Skull, 
  HardDrive, 
  CheckCircle2, 
  Clock,
  Sparkles,
  RefreshCw
} from 'lucide-react';
import api from '../services/api';

export default function WALRecovery({ isCrashed, onSimulateCrash, onRecover }) {
  const [walData, setWalData] = useState({ total: 0, records: [] });
  const [integrity, setIntegrity] = useState(null);
  const [recoveryStats, setRecoveryStats] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchWal = async () => {
    try {
      const [recordsRes, integRes, recovRes] = await Promise.all([
        api.getWalRecords({ limit: 40, offset: 0 }),
        api.getWalIntegrity(),
        api.getRecoveryStats()
      ]);
      setWalData(recordsRes.data);
      setIntegrity(integRes.data);
      setRecoveryStats(recovRes.data.last_recovery);
    } catch (err) {
      console.error("Failed to load WAL:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWal();
    const interval = setInterval(fetchWal, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleManualCheckpoint = async () => {
    try {
      await api.createCheckpoint();
      fetchWal();
    } catch (err) {
      console.error("Failed to create checkpoint:", err);
    }
  };

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Custom Write-Ahead Log (WAL) & Crash Recovery</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Durable append-only disk logging with CRC32 checksums and ARIES Analysis/Redo/Undo crash recovery.
          </p>
        </div>

        {/* Action buttons */}
        <div className="flex items-center space-x-2">
          <button
            onClick={handleManualCheckpoint}
            disabled={isCrashed}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-medium shadow-2xs"
          >
            <HardDrive className="w-3.5 h-3.5 text-teal-600" />
            <span>Create Checkpoint</span>
          </button>

          {isCrashed ? (
            <button
              onClick={onRecover}
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-medium shadow-sm animate-pulse"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Restart & Recover</span>
            </button>
          ) : (
            <button
              onClick={onSimulateCrash}
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-medium shadow-sm"
            >
              <Skull className="w-3.5 h-3.5" />
              <span>Simulate Server Crash</span>
            </button>
          )}
        </div>
      </div>

      {/* Recovery Banner / Alert */}
      {isCrashed ? (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl flex items-center justify-between text-xs">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-red-100 rounded-lg text-red-600">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <div className="font-bold text-red-900">Coordinator is currently in Crashed State!</div>
              <div className="text-red-700 mt-0.5">
                In-flight uncommitted transactions have vanished. Click "Restart & Recover" to execute ARIES redo of committed WAL records.
              </div>
            </div>
          </div>
          <button
            onClick={onRecover}
            className="px-4 py-2 bg-red-600 text-white font-bold rounded-lg hover:bg-red-700 shadow-sm"
          >
            Recover Now
          </button>
        </div>
      ) : recoveryStats && Object.keys(recoveryStats).length > 0 && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-xs space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2 text-emerald-900 font-bold">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>Latest ARIES Recovery Report ({recoveryStats.status})</span>
            </div>
            <span className="text-emerald-700 font-mono font-semibold">
              Execution Time: {recoveryStats.recovery_duration_ms} ms
            </span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 pt-1">
            <div className="bg-white/80 p-2 rounded-lg border border-emerald-100">
              <span className="text-[10px] text-slate-500 block">Baseline Checkpoint LSN</span>
              <strong className="text-slate-800 font-mono">LSN {recoveryStats.checkpoint_lsn}</strong>
            </div>
            <div className="bg-white/80 p-2 rounded-lg border border-emerald-100">
              <span className="text-[10px] text-slate-500 block">Committed Txns Redone</span>
              <strong className="text-emerald-700 font-mono">{recoveryStats.committed_txns_recovered} Txns</strong>
            </div>
            <div className="bg-white/80 p-2 rounded-lg border border-emerald-100">
              <span className="text-[10px] text-slate-500 block">Incomplete Txns Undone</span>
              <strong className="text-amber-700 font-mono">{recoveryStats.incomplete_txns_discarded} Txns</strong>
            </div>
            <div className="bg-white/80 p-2 rounded-lg border border-emerald-100">
              <span className="text-[10px] text-slate-500 block">Restored Model Version</span>
              <strong className="text-blue-700 font-mono">{recoveryStats.recovered_version_id}</strong>
            </div>
          </div>
        </div>
      )}

      {/* Integrity & Summary Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs flex items-center justify-between">
          <div>
            <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">WAL Total Records</span>
            <div className="text-xl font-bold font-mono text-slate-900 mt-0.5">{walData.total}</div>
          </div>
          <FileText className="w-6 h-6 text-slate-300" />
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs flex items-center justify-between">
          <div>
            <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">CRC32 Checksum Audit</span>
            <div className="text-sm font-bold font-mono text-emerald-600 mt-1 flex items-center space-x-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-500" />
              <span>{integrity?.status || 'HEALTHY'}</span>
            </div>
          </div>
          <span className="text-[11px] text-slate-400 font-mono">
            {integrity?.total_records_checked || 0} Checked
          </span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs flex items-center justify-between">
          <div>
            <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">Fsync Disk Durability</span>
            <div className="text-sm font-bold text-slate-800 mt-1 flex items-center space-x-1.5">
              <HardDrive className="w-4 h-4 text-teal-600" />
              <span>Forced Disk Sync</span>
            </div>
          </div>
          <span className="px-2 py-0.5 bg-teal-50 text-teal-700 border border-teal-200 rounded text-[10px] font-bold">
            ACID Guaranteed
          </span>
        </div>
      </div>

      {/* WAL Records Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-800">Append-Only Persistent Log Stream</h3>
          <span className="text-xs text-slate-400 font-mono">Order: Descending LSN</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[10px]">
              <tr>
                <th className="px-4 py-3">LSN</th>
                <th className="px-4 py-3">Record Type</th>
                <th className="px-4 py-3">Txn ID</th>
                <th className="px-4 py-3">Client</th>
                <th className="px-4 py-3">Base / Ref</th>
                <th className="px-4 py-3">CRC32 Checksum</th>
                <th className="px-4 py-3">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono">
              {walData.records.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-slate-400">
                    No WAL records generated yet.
                  </td>
                </tr>
              ) : (
                walData.records.map((r) => {
                  let badgeColor = 'bg-slate-100 text-slate-700';
                  if (r.record_type === 'BEGIN') badgeColor = 'bg-blue-50 text-blue-700 border border-blue-200';
                  if (r.record_type === 'UPDATE') badgeColor = 'bg-purple-50 text-purple-700 border border-purple-200';
                  if (r.record_type === 'COMMIT') badgeColor = 'bg-emerald-50 text-emerald-700 border border-emerald-200';
                  if (r.record_type === 'ABORT') badgeColor = 'bg-red-50 text-red-700 border border-red-200';
                  if (r.record_type === 'CHECKPOINT') badgeColor = 'bg-teal-50 text-teal-800 border border-teal-200';
                  if (r.record_type === 'COMPENSATION') badgeColor = 'bg-amber-50 text-amber-800 border border-amber-200';

                  return (
                    <tr key={r.log_id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="px-4 py-2.5 font-bold text-slate-900">#{r.lsn}</td>
                      <td className="px-4 py-2.5">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${badgeColor}`}>
                          {r.record_type}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-slate-700">{r.transaction_id || '—'}</td>
                      <td className="px-4 py-2.5 text-slate-500 uppercase">{r.client_id || 'SYSTEM'}</td>
                      <td className="px-4 py-2.5 text-slate-500 truncate max-w-xs">{r.data_reference || r.base_version || '—'}</td>
                      <td className="px-4 py-2.5 text-teal-600 font-bold">{r.checksum}</td>
                      <td className="px-4 py-2.5 text-slate-400 text-[11px]">
                        {r.timestamp ? new Date(r.timestamp).toLocaleTimeString() : '—'}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
