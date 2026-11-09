import React, { useEffect, useState } from 'react';
import { 
  Sliders, 
  RotateCcw, 
  Trash2, 
  Sparkles, 
  HardDrive, 
  ListOrdered, 
  ShieldAlert, 
  CheckCircle2, 
  AlertTriangle,
  Layers,
  ArrowRight
} from 'lucide-react';
import api from '../services/api';

export default function OptimizationCenter() {
  const [activeTab, setActiveTab] = useState('staleness');

  // Feature 1: Staleness State
  const [stalenessConfig, setStalenessConfig] = useState({ base_threshold: 3, max_allowance: 6, cosine_threshold: 0.25 });
  const [stalenessMsg, setStalenessMsg] = useState('');

  // Feature 2: Priority Queue State
  const [queueData, setQueueData] = useState({ queue_depth: 0, queue: [] });

  // Feature 3: Selective Rollback State
  const [rollbackTxnId, setRollbackTxnId] = useState('');
  const [rollbackReason, setRollbackReason] = useState('Poisoned gradient detected from malicious bank contribution');
  const [rollbackResult, setRollbackResult] = useState(null);
  const [rollbackLoading, setRollbackLoading] = useState(false);

  // Feature 4: Garbage Collection State
  const [gcStats, setGcStats] = useState(null);
  const [gcLoading, setGcLoading] = useState(false);

  // Feature 5: Conflict Prediction State
  const [predictClient, setPredictClient] = useState('bank_c');
  const [predictStaleness, setPredictStaleness] = useState(3);
  const [predictNorm, setPredictNorm] = useState(0.25);
  const [predictionResult, setPredictionResult] = useState(null);

  // Feature 6: Differential Storage State
  const [diffMetrics, setDiffMetrics] = useState(null);

  const fetchOptimizationData = async () => {
    try {
      const [stRes, qRes, diffRes, gcRes] = await Promise.all([
        api.getStalenessConfig(),
        api.getSchedulerQueueStatus(),
        api.getDifferentialMetrics(),
        api.getGcStats()
      ]);
      setStalenessConfig(stRes.data);
      setQueueData(qRes.data);
      setDiffMetrics(diffRes.data);
      if (gcRes.data && Object.keys(gcRes.data).length > 0) {
        setGcStats(gcRes.data);
      }
    } catch (err) {
      console.error("Failed to fetch optimization data:", err);
    }
  };

  useEffect(() => {
    fetchOptimizationData();
    const interval = setInterval(fetchOptimizationData, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleUpdateStaleness = async () => {
    try {
      await api.updateStalenessConfig(stalenessConfig);
      setStalenessMsg('Configuration saved successfully!');
      setTimeout(() => setStalenessMsg(''), 3000);
    } catch (err) {
      console.error(err);
    }
  };

  const handleRunGc = async () => {
    setGcLoading(true);
    try {
      const res = await api.runGarbageCollection(2);
      setGcStats(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setGcLoading(false);
    }
  };

  const handleTestPrediction = async () => {
    try {
      const res = await api.testConflictPrediction({
        client_id: predictClient,
        staleness: parseInt(predictStaleness),
        delta_norm: parseFloat(predictNorm)
      });
      setPredictionResult(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const handleExecuteRollback = async () => {
    if (!rollbackTxnId.trim()) return;
    setRollbackLoading(true);
    try {
      const res = await api.triggerSelectiveRollback({
        target_transaction_id: rollbackTxnId.trim(),
        reason: rollbackReason
      });
      setRollbackResult(res.data);
    } catch (err) {
      alert(`Rollback failed: ${err.response?.data?.detail || err.message}`);
    } finally {
      setRollbackLoading(false);
    }
  };

  const tabs = [
    { id: 'staleness', label: '1. Adaptive Staleness', icon: Sliders },
    { id: 'scheduler', label: '2. Priority Scheduling', icon: ListOrdered },
    { id: 'rollback', label: '3. Selective Rollback', icon: RotateCcw },
    { id: 'gc', label: '4. Adaptive Vacuum (GC)', icon: Trash2 },
    { id: 'predictor', label: '5. Conflict Prediction', icon: Sparkles },
    { id: 'differential', label: '6. Differential Storage', icon: HardDrive },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900">Optimization Center & Novelty Engines</h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Interactive evaluation panels for the 6 core DBMS novelty mechanisms designed for Asynchronous FL.
        </p>
      </div>

      {/* Tabs Navigation */}
      <div className="flex border-b border-slate-200 space-x-1 overflow-x-auto pb-px">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center space-x-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all whitespace-nowrap ${
                isActive
                  ? 'border-teal-500 text-teal-700 bg-teal-50/50 rounded-t-lg'
                  : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-teal-600' : 'text-slate-400'}`} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* TAB 1: ADAPTIVE STALENESS */}
      {activeTab === 'staleness' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-6 shadow-2xs">
          <div>
            <h3 className="text-base font-bold text-slate-900">Adaptive Staleness Management</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-3xl">
              Calculates transaction staleness \(S = V_{'\text{current}'} - V_{'\text{base}'}\). Fresh updates (\(S \le \tau_{'\text{base}'}\)) are accepted directly with learning-rate attenuation. In the adaptive margin (\(\tau_{'\text{base}'} &lt; S \le \tau_{'\max'}\)), cosine similarity with recent gradient trajectory determines whether the older update is still useful rather than blindly discarding it.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-2">
            <div className="space-y-2">
              <label className="text-xs font-bold text-slate-700 flex justify-between">
                <span>Base Threshold (\(\tau_{'\text{base}'}\)):</span>
                <span className="font-mono text-teal-600 font-bold">{stalenessConfig.base_threshold}</span>
              </label>
              <input
                type="range"
                min="1"
                max="8"
                value={stalenessConfig.base_threshold}
                onChange={(e) => setStalenessConfig({ ...stalenessConfig, base_threshold: parseInt(e.target.value) })}
                className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-teal-600"
              />
              <span className="text-[11px] text-slate-400">Updates within this staleness are unconditionally accepted.</span>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-bold text-slate-700 flex justify-between">
                <span>Max Allowance (\(\tau_{'\max'}\)):</span>
                <span className="font-mono text-teal-600 font-bold">{stalenessConfig.max_allowance}</span>
              </label>
              <input
                type="range"
                min="3"
                max="12"
                value={stalenessConfig.max_allowance}
                onChange={(e) => setStalenessConfig({ ...stalenessConfig, max_allowance: parseInt(e.target.value) })}
                className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-teal-600"
              />
              <span className="text-[11px] text-slate-400">Updates beyond this bound are rejected unconditionally.</span>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-bold text-slate-700 flex justify-between">
                <span>Cosine Utility Threshold (\(\theta_{'\text{cos}'}\)):</span>
                <span className="font-mono text-teal-600 font-bold">{stalenessConfig.cosine_threshold}</span>
              </label>
              <input
                type="range"
                min="0.05"
                max="0.80"
                step="0.05"
                value={stalenessConfig.cosine_threshold}
                onChange={(e) => setStalenessConfig({ ...stalenessConfig, cosine_threshold: parseFloat(e.target.value) })}
                className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-teal-600"
              />
              <span className="text-[11px] text-slate-400">Minimum cosine similarity required in the adaptive margin.</span>
            </div>
          </div>

          <div className="flex items-center space-x-3 pt-2">
            <button
              onClick={handleUpdateStaleness}
              className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg text-xs font-bold shadow-xs transition-all"
            >
              Save Staleness Configuration
            </button>
            {stalenessMsg && (
              <span className="text-xs text-emerald-600 font-semibold animate-fade-in flex items-center space-x-1">
                <CheckCircle2 className="w-4 h-4" />
                <span>{stalenessMsg}</span>
              </span>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: PRIORITY SCHEDULING */}
      {activeTab === 'scheduler' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-6 shadow-2xs">
          <div>
            <h3 className="text-base font-bold text-slate-900">Priority Transaction Scheduler & Starvation Prevention</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-3xl">
              Transactions are scheduled using dynamic aging: 
              \(P = w_{'\text{wait}'} \cdot t_{'\text{wait}'} - w_{'\text{stale}'} \cdot S + w_{'\text{fail}'} \cdot \text{failures} + \text{aging} \cdot t_{'\text{wait}'}^{1.1}\).
              Slower clients (such as Bank E) gain priority over time, completely eliminating starvation.
            </p>
          </div>

          <div className="border border-slate-200 rounded-xl overflow-hidden">
            <div className="p-3 bg-slate-50 border-b border-slate-200 flex justify-between items-center text-xs">
              <span className="font-bold text-slate-700">Active Priority Queue ({queueData.queue_depth} Queued)</span>
              <span className="text-slate-400 font-mono">Real-Time Evaluation</span>
            </div>

            {queueData.queue.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-xs">
                Scheduler queue is currently empty. All incoming transactions have been dequeued and processed.
              </div>
            ) : (
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 font-semibold uppercase text-[10px]">
                  <tr>
                    <th className="px-4 py-2.5">Txn ID</th>
                    <th className="px-4 py-2.5">Client</th>
                    <th className="px-4 py-2.5">Staleness</th>
                    <th className="px-4 py-2.5">Prior Failures</th>
                    <th className="px-4 py-2.5">Wait Time</th>
                    <th className="px-4 py-2.5">Dynamic Priority Score</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-mono">
                  {queueData.queue.map((item, idx) => (
                    <tr key={item.transaction_id} className={idx === 0 ? 'bg-teal-50/40' : ''}>
                      <td className="px-4 py-2.5 font-bold text-slate-800">{item.transaction_id}</td>
                      <td className="px-4 py-2.5 uppercase text-slate-600">{item.client_id}</td>
                      <td className="px-4 py-2.5 text-amber-700">Δ {item.staleness}</td>
                      <td className="px-4 py-2.5 text-slate-600">{item.failure_count}</td>
                      <td className="px-4 py-2.5 text-slate-600">{item.waiting_time_seconds}s</td>
                      <td className="px-4 py-2.5">
                        <span className="px-2 py-0.5 bg-teal-100 text-teal-800 font-bold rounded">
                          {item.priority_score}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: SELECTIVE ROLLBACK */}
      {activeTab === 'rollback' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-6 shadow-2xs">
          <div>
            <h3 className="text-base font-bold text-slate-900">Selective Rollback of Malicious / Poisoned Updates</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-3xl">
              When adversarial poisoning is detected (e.g. Bank C), the DBMS engine does NOT delete immutable WAL records. Instead, it replays historical transactions from checkpoint while skipping the poisoned contribution, generating a new corrected model version and appending a COMPENSATION record.
            </p>
          </div>

          <div className="max-w-xl space-y-3 p-4 bg-slate-50 rounded-xl border border-slate-200">
            <div>
              <label className="text-xs font-bold text-slate-700 block mb-1">Target Transaction ID to Rollback:</label>
              <input
                type="text"
                placeholder="e.g. tx_0a1b2c3d4e"
                value={rollbackTxnId}
                onChange={(e) => setRollbackTxnId(e.target.value)}
                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs font-mono text-slate-800 focus:outline-teal-500"
              />
            </div>

            <div>
              <label className="text-xs font-bold text-slate-700 block mb-1">Audit Reason / Detection Signature:</label>
              <input
                type="text"
                value={rollbackReason}
                onChange={(e) => setRollbackReason(e.target.value)}
                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs text-slate-800 focus:outline-teal-500"
              />
            </div>

            <button
              onClick={handleExecuteRollback}
              disabled={rollbackLoading || !rollbackTxnId.trim()}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white rounded-lg text-xs font-bold transition-all shadow-xs"
            >
              {rollbackLoading ? 'Reconstructing Model...' : 'Execute Deterministic Selective Rollback'}
            </button>
          </div>

          {rollbackResult && (
            <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl space-y-2 text-xs">
              <div className="font-bold text-emerald-900 flex items-center space-x-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Selective Rollback Succeeded ({rollbackResult.status})</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 pt-1 font-mono">
                <div className="bg-white p-2 rounded border border-emerald-100">
                  <span className="text-[10px] text-slate-500 block">Restored Model Version</span>
                  <strong className="text-blue-700">{rollbackResult.reconstructed_version_id}</strong>
                </div>
                <div className="bg-white p-2 rounded border border-emerald-100">
                  <span className="text-[10px] text-slate-500 block">Valid Txns Replayed</span>
                  <strong className="text-emerald-700">{rollbackResult.replayed_transactions_count}</strong>
                </div>
                <div className="bg-white p-2 rounded border border-emerald-100">
                  <span className="text-[10px] text-slate-500 block">Poisoned Txns Purged</span>
                  <strong className="text-red-700">{rollbackResult.skipped_transactions?.length}</strong>
                </div>
                <div className="bg-white p-2 rounded border border-emerald-100">
                  <span className="text-[10px] text-slate-500 block">WAL Compensation LSN</span>
                  <strong className="text-slate-800">LSN {rollbackResult.wal_compensation_lsn}</strong>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 4: ADAPTIVE GARBAGE COLLECTION */}
      {activeTab === 'gc' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-6 shadow-2xs">
          <div>
            <h3 className="text-base font-bold text-slate-900">Snapshot-Aware MVCC Garbage Collection</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-3xl">
              Identifies active client snapshots and preserves pinned model versions. Old unreferenced versions outside the active horizon are vacuumed to reclaim disk storage while preserving audit metadata and checkpoint baselines.
            </p>
          </div>

          <div className="flex items-center space-x-4">
            <button
              onClick={handleRunGc}
              disabled={gcLoading}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-xs font-bold transition-all shadow-xs"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>{gcLoading ? 'Vacuuming...' : 'Run Adaptive Garbage Collection Now'}</span>
            </button>
          </div>

          {gcStats && (
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-3 text-xs">
              <div className="font-bold text-slate-800">Garbage Collection Execution Audit</div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 font-mono">
                <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                  <span className="text-[10px] text-slate-500 block">Disk Before GC</span>
                  <strong>{(gcStats.storage_before_bytes / 1024).toFixed(1)} KB</strong>
                </div>
                <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                  <span className="text-[10px] text-slate-500 block">Disk After GC</span>
                  <strong>{(gcStats.storage_after_bytes / 1024).toFixed(1)} KB</strong>
                </div>
                <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                  <span className="text-[10px] text-slate-500 block">Storage Reclaimed</span>
                  <strong className="text-emerald-600">{(gcStats.bytes_reclaimed / 1024).toFixed(1)} KB</strong>
                </div>
                <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                  <span className="text-[10px] text-slate-500 block">Versions Pruned</span>
                  <strong className="text-slate-800">{gcStats.pruned_versions?.length || 0}</strong>
                </div>
              </div>

              <div className="text-[11px] text-slate-600">
                <strong>Protected Versions (Pinned/Head): </strong>
                <span className="font-mono text-teal-700">{gcStats.protected_versions?.join(', ')}</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 5: TRANSACTION CONFLICT PREDICTION */}
      {activeTab === 'predictor' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-6 shadow-2xs">
          <div>
            <h3 className="text-base font-bold text-slate-900">Transaction Conflict Prediction Engine</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-3xl">
              Extracts behavioral signals (historical client abort ratios, staleness factor, contention, and gradient magnitude) to predict potential OCC write conflicts before validation. Strictly advisory; mandatory OCC validation is never bypassed.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-2xl bg-slate-50 p-4 rounded-xl border border-slate-200 text-xs">
            <div>
              <label className="font-bold text-slate-700 block mb-1">Simulated Client:</label>
              <select
                value={predictClient}
                onChange={(e) => setPredictClient(e.target.value)}
                className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded-lg text-slate-700"
              >
                <option value="bank_a">Bank A (Retail)</option>
                <option value="bank_b">Bank B (E-Comm)</option>
                <option value="bank_c">Bank C (High Volatility)</option>
                <option value="bank_d">Bank D (Credit Union)</option>
                <option value="bank_e">Bank E (High Latency)</option>
              </select>
            </div>

            <div>
              <label className="font-bold text-slate-700 block mb-1">Hypothetical Staleness:</label>
              <input
                type="number"
                min="0"
                max="10"
                value={predictStaleness}
                onChange={(e) => setPredictStaleness(e.target.value)}
                className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded-lg font-mono text-slate-700"
              />
            </div>

            <div>
              <label className="font-bold text-slate-700 block mb-1">Gradient L2 Norm:</label>
              <input
                type="number"
                step="0.05"
                min="0.01"
                max="5.0"
                value={predictNorm}
                onChange={(e) => setPredictNorm(e.target.value)}
                className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded-lg font-mono text-slate-700"
              />
            </div>

            <div className="md:col-span-3 pt-2">
              <button
                onClick={handleTestPrediction}
                className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-bold shadow-xs transition-all"
              >
                Calculate Conflict Risk Score
              </button>
            </div>
          </div>

          {predictionResult && (
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-3 text-xs max-w-2xl">
              <div className="flex items-center justify-between">
                <span className="font-bold text-slate-800">Predictive Assessment Result</span>
                <span className={`px-2.5 py-0.5 rounded font-bold font-mono ${
                  predictionResult.risk_category === 'HIGH' 
                    ? 'bg-red-100 text-red-800' 
                    : predictionResult.risk_category === 'MEDIUM' 
                    ? 'bg-amber-100 text-amber-800' 
                    : 'bg-emerald-100 text-emerald-800'
                }`}>
                  {predictionResult.risk_category} RISK ({predictionResult.risk_score})
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-[11px]">
                <div className="bg-white p-2 rounded border border-slate-200">
                  <span className="text-[10px] text-slate-400 block">Staleness Factor</span>
                  <strong>{predictionResult.feature_breakdown?.staleness_factor}</strong>
                </div>
                <div className="bg-white p-2 rounded border border-slate-200">
                  <span className="text-[10px] text-slate-400 block">Client Abort Rate</span>
                  <strong>{predictionResult.feature_breakdown?.client_abort_ratio}</strong>
                </div>
                <div className="bg-white p-2 rounded border border-slate-200">
                  <span className="text-[10px] text-slate-400 block">Contention</span>
                  <strong>{predictionResult.feature_breakdown?.contention_factor}</strong>
                </div>
                <div className="bg-white p-2 rounded border border-slate-200">
                  <span className="text-[10px] text-slate-400 block">Norm Outlier</span>
                  <strong>{predictionResult.feature_breakdown?.norm_factor}</strong>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 6: DIFFERENTIAL WAL STORAGE */}
      {activeTab === 'differential' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-6 shadow-2xs">
          <div>
            <h3 className="text-base font-bold text-slate-900">Differential WAL Storage vs Full Snapshot Logging</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-3xl">
              Instead of repeatedly persisting full \(D\)-dimensional model parameter arrays for every commit, the differential engine stores sparse parameter changes (\(\Delta W = W_{'\text{new}'} - W_{'\text{base}'}\)). Target model versions are deterministically reconstructed by accumulating deltas from the nearest checkpoint.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200">
              <span className="text-xs text-slate-500 block uppercase font-semibold">Naive Full Snapshot Logging</span>
              <div className="text-2xl font-bold font-mono text-slate-800 mt-1">
                {diffMetrics?.full_model_logging_mb || 0} MB
              </div>
              <span className="text-[11px] text-slate-400 mt-1 block">Full parameters per transaction</span>
            </div>

            <div className="p-4 bg-teal-50 rounded-xl border border-teal-200">
              <span className="text-xs text-teal-800 block uppercase font-semibold">Proposed Differential WAL</span>
              <div className="text-2xl font-bold font-mono text-teal-700 mt-1">
                {diffMetrics?.differential_logging_mb || 0} MB
              </div>
              <span className="text-[11px] text-teal-600 mt-1 block">Sparse delta vector encoding</span>
            </div>

            <div className="p-4 bg-emerald-50 rounded-xl border border-emerald-200">
              <span className="text-xs text-emerald-800 block uppercase font-semibold">Net Disk Savings</span>
              <div className="text-2xl font-bold font-mono text-emerald-700 mt-1">
                {diffMetrics?.storage_reduction_percent || 0}%
              </div>
              <span className="text-[11px] text-emerald-600 mt-1 block">
                {diffMetrics?.storage_saved_mb || 0} MB physically conserved
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
