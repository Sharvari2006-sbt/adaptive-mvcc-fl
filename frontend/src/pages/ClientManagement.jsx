import React, { useEffect, useState } from 'react';
import { 
  Building2, 
  Play, 
  Pause, 
  AlertTriangle, 
  Bug, 
  Clock, 
  FastForward, 
  CheckCircle2, 
  XCircle,
  ShieldAlert,
  Database
} from 'lucide-react';
import api from '../services/api';

export default function ClientManagement({ onStep, isCrashed }) {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchClients = async () => {
    try {
      const res = await api.getClients();
      setClients(res.data);
    } catch (err) {
      console.error("Failed to load clients:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClients();
    const interval = setInterval(fetchClients, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleToggleStatus = async (client) => {
    const newStatus = client.status === 'ACTIVE' ? 'PAUSED' : 'ACTIVE';
    await api.controlClient(client.client_id, { status: newStatus });
    fetchClients();
  };

  const handleDelayChange = async (clientId, delay) => {
    await api.controlClient(clientId, { delay_seconds: parseFloat(delay) });
    fetchClients();
  };

  const handleToggleMalicious = async (client) => {
    await api.controlClient(client.client_id, { is_malicious: !client.is_malicious });
    fetchClients();
  };

  const handleToggleOutdated = async (client) => {
    await api.controlClient(client.client_id, { force_outdated: !client.force_outdated });
    fetchClients();
  };

  if (loading && clients.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-400">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-500 mr-3"></div>
        Loading Simulated Banks...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Federated Bank Clients</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            5 independent simulated financial institutions training private local fraud classification models.
          </p>
        </div>

        <button
          onClick={() => onStep()}
          disabled={isCrashed}
          className="flex items-center space-x-1.5 px-3 py-1.5 bg-teal-600 hover:bg-teal-700 disabled:opacity-40 text-white rounded-lg text-xs font-medium shadow-xs"
        >
          <FastForward className="w-3.5 h-3.5" />
          <span>Step All Active Clients</span>
        </button>
      </div>

      {/* Clients Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {clients.map((c) => {
          const isActive = c.status === 'ACTIVE';
          return (
            <div 
              key={c.client_id}
              className={`bg-white rounded-2xl border transition-all p-5 shadow-2xs ${
                c.is_malicious 
                  ? 'border-red-300 ring-2 ring-red-500/10' 
                  : c.force_outdated 
                  ? 'border-amber-300 ring-2 ring-amber-500/10' 
                  : 'border-slate-200'
              }`}
            >
              {/* Header */}
              <div className="flex items-start justify-between">
                <div className="flex items-center space-x-3">
                  <div className={`p-2.5 rounded-xl ${
                    c.is_malicious 
                      ? 'bg-red-50 text-red-600' 
                      : isActive 
                      ? 'bg-blue-50 text-blue-600' 
                      : 'bg-slate-100 text-slate-400'
                  }`}>
                    <Building2 className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-800">{c.client_name}</h3>
                    <div className="flex items-center space-x-1.5 mt-0.5">
                      <span className="text-[11px] font-mono font-semibold text-slate-400 uppercase">
                        {c.client_id}
                      </span>
                      <span className="text-slate-300">•</span>
                      <span className="text-[11px] text-slate-500 font-medium">
                        {c.client_type}
                      </span>
                    </div>
                  </div>
                </div>

                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                  isActive ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-slate-100 text-slate-600'
                }`}>
                  {c.status}
                </span>
              </div>

              {/* Status Badges */}
              {(c.is_malicious || c.force_outdated) && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {c.is_malicious && (
                    <span className="inline-flex items-center space-x-1 px-2 py-0.5 bg-red-100 text-red-700 text-[10px] font-bold rounded">
                      <ShieldAlert className="w-3 h-3 text-red-600" />
                      <span>Poisoning Active</span>
                    </span>
                  )}
                  {c.force_outdated && (
                    <span className="inline-flex items-center space-x-1 px-2 py-0.5 bg-amber-100 text-amber-800 text-[10px] font-bold rounded">
                      <Clock className="w-3 h-3 text-amber-600" />
                      <span>Stale Snapshot (V0)</span>
                    </span>
                  )}
                </div>
              )}

              {/* Metrics Grid */}
              <div className="grid grid-cols-2 gap-2 mt-4 pt-3 border-t border-slate-100 text-xs">
                <div className="bg-slate-50 p-2 rounded-lg">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">Snapshot Base</span>
                  <div className="font-mono font-bold text-slate-700 mt-0.5">
                    {c.current_snapshot_vid || 'None'}
                  </div>
                </div>

                <div className="bg-slate-50 p-2 rounded-lg">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">Local Accuracy</span>
                  <div className="font-mono font-bold text-emerald-600 mt-0.5">
                    {(c.last_accuracy * 100).toFixed(1)}%
                  </div>
                </div>

                <div className="bg-slate-50 p-2 rounded-lg">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">Commits / Total</span>
                  <div className="font-mono font-bold text-slate-700 mt-0.5">
                    {c.successful_commits} / {c.total_submissions}
                  </div>
                </div>

                <div className="bg-slate-50 p-2 rounded-lg">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">Aborted Txns</span>
                  <div className="font-mono font-bold text-amber-600 mt-0.5">
                    {c.aborted_txns}
                  </div>
                </div>
              </div>

              {/* Latency Slider */}
              <div className="mt-4 pt-3 border-t border-slate-100">
                <div className="flex items-center justify-between text-xs mb-1.5">
                  <span className="text-slate-500 font-medium flex items-center space-x-1">
                    <Clock className="w-3.5 h-3.5 text-slate-400" />
                    <span>Client Delay (Network & Compute):</span>
                  </span>
                  <span className="font-mono font-bold text-slate-700">{c.delay_seconds.toFixed(1)}s</span>
                </div>
                <input
                  type="range"
                  min="0.1"
                  max="3.0"
                  step="0.1"
                  value={c.delay_seconds}
                  onChange={(e) => handleDelayChange(c.client_id, e.target.value)}
                  className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-teal-600"
                />
              </div>

              {/* Action Buttons */}
              <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                <div className="flex items-center space-x-1.5">
                  {/* Step single client */}
                  <button
                    onClick={() => onStep(c.client_id)}
                    disabled={isCrashed || !isActive}
                    className="p-1.5 bg-teal-50 text-teal-700 hover:bg-teal-100 disabled:opacity-40 rounded-lg text-xs font-medium"
                    title="Run 1 training round for this bank only"
                  >
                    <FastForward className="w-3.5 h-3.5" />
                  </button>

                  {/* Pause / Resume */}
                  <button
                    onClick={() => handleToggleStatus(c)}
                    className="p-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-medium"
                    title={isActive ? "Pause client" : "Resume client"}
                  >
                    {isActive ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 fill-current" />}
                  </button>
                </div>

                <div className="flex items-center space-x-1.5">
                  {/* Force Outdated toggle */}
                  <button
                    onClick={() => handleToggleOutdated(c)}
                    className={`px-2 py-1 rounded text-[11px] font-semibold border transition-all ${
                      c.force_outdated 
                        ? 'bg-amber-100 text-amber-800 border-amber-300' 
                        : 'bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100'
                    }`}
                    title="Force this bank to submit against outdated V0 snapshot"
                  >
                    Stale V0
                  </button>

                  {/* Poison update toggle */}
                  <button
                    onClick={() => handleToggleMalicious(c)}
                    className={`px-2 py-1 rounded text-[11px] font-semibold border transition-all ${
                      c.is_malicious 
                        ? 'bg-red-100 text-red-800 border-red-300 animate-pulse' 
                        : 'bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100'
                    }`}
                    title="Inject poisoned adversarial gradients"
                  >
                    Poison
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
