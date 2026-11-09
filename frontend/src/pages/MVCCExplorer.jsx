import React, { useEffect, useState } from 'react';
import { 
  GitBranch, 
  GitCommit, 
  Check, 
  Clock, 
  Eye, 
  ShieldCheck, 
  UserCheck,
  TrendingUp,
  Cpu,
  Layers
} from 'lucide-react';
import api from '../services/api';

export default function MVCCExplorer() {
  const [versions, setVersions] = useState([]);
  const [snapshots, setSnapshots] = useState({});
  const [selectedVersion, setSelectedVersion] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchVersions = async () => {
    try {
      const [vRes, sRes] = await Promise.all([
        api.getVersions(),
        api.getActiveSnapshots()
      ]);
      setVersions(vRes.data);
      setSnapshots(sRes.data);
    } catch (err) {
      console.error("Failed to load versions:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVersions();
    const interval = setInterval(fetchVersions, 3000);
    return () => clearInterval(interval);
  }, []);

  const openVersionDetails = async (vid) => {
    try {
      const res = await api.inspectVersion(vid);
      setSelectedVersion(res.data);
    } catch (err) {
      console.error("Failed to inspect version:", err);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900">MVCC Multi-Version Explorer</h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Lineage directed acyclic graph (DAG) of global model versions and active reader snapshot pins.
        </p>
      </div>

      {/* Active Pinned Snapshots Banner */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs">
        <div className="flex items-center space-x-2 text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
          <UserCheck className="w-4 h-4 text-teal-600" />
          <span>Active Client Snapshot Pins (Snapshot Isolation Protection)</span>
        </div>

        <div className="flex flex-wrap gap-2">
          {Object.entries(snapshots).length === 0 ? (
            <span className="text-xs text-slate-400 italic">No clients currently holding snapshot pins.</span>
          ) : (
            Object.entries(snapshots).map(([clientId, vid]) => (
              <span key={clientId} className="inline-flex items-center space-x-1.5 px-3 py-1 bg-teal-50 border border-teal-200 text-teal-800 rounded-lg text-xs font-medium">
                <span className="font-bold capitalize">{clientId.replace('_', ' ')}:</span>
                <span className="font-mono bg-teal-200/60 px-1.5 py-0.2 rounded font-bold">{vid}</span>
              </span>
            ))
          )}
        </div>
      </div>

      {/* Version Lineage Tree / List */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <GitBranch className="w-4 h-4 text-blue-600" />
            <h3 className="text-sm font-bold text-slate-800">Version Lineage Chain</h3>
          </div>
          <span className="text-xs text-slate-400 font-mono">Total Versions: {versions.length}</span>
        </div>

        <div className="divide-y divide-slate-100">
          {versions.map((v, idx) => {
            const isHead = v.is_current;
            const hasReaders = v.active_readers > 0;
            return (
              <div 
                key={v.version_id}
                className={`p-4 flex items-center justify-between hover:bg-slate-50/80 transition-colors ${
                  isHead ? 'bg-blue-50/30' : ''
                }`}
              >
                <div className="flex items-center space-x-4">
                  {/* Version Badge */}
                  <div className={`p-2.5 rounded-xl flex items-center justify-center font-mono font-bold text-sm ${
                    isHead 
                      ? 'bg-blue-600 text-white shadow-sm' 
                      : 'bg-slate-100 text-slate-700'
                  }`}>
                    {v.version_id}
                  </div>

                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-sm font-bold text-slate-900">
                        Model Version #{v.version_number}
                      </span>
                      {isHead && (
                        <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-[10px] font-bold rounded">
                          HEAD / CURRENT
                        </span>
                      )}
                      {hasReaders && (
                        <span className="px-2 py-0.5 bg-teal-100 text-teal-800 text-[10px] font-bold rounded">
                          {v.active_readers} Active Readers
                        </span>
                      )}
                    </div>

                    <div className="flex items-center space-x-3 text-xs text-slate-500 mt-1 font-mono">
                      <span>Parent: <strong className="text-slate-700">{v.parent_version_id || 'ROOT'}</strong></span>
                      <span>•</span>
                      <span>Accuracy: <strong className="text-emerald-600">{(v.accuracy * 100).toFixed(1)}%</strong></span>
                      <span>•</span>
                      <span>Loss: <strong className="text-slate-700">{v.loss}</strong></span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center space-x-3">
                  <span className="text-xs text-slate-400 font-mono hidden sm:inline">
                    {new Date(v.created_at).toLocaleTimeString()}
                  </span>
                  <button
                    onClick={() => openVersionDetails(v.version_id)}
                    className="flex items-center space-x-1 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-medium transition-colors"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    <span>Inspect</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Version Inspection Modal */}
      {selectedVersion && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-lg w-full border border-slate-200 shadow-xl overflow-hidden p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center space-x-2">
                <Layers className="w-4 h-4 text-blue-600" />
                <h3 className="text-sm font-bold text-slate-900">
                  Version {selectedVersion.version_id} Metadata & Weights
                </h3>
              </div>
              <button 
                onClick={() => setSelectedVersion(null)} 
                className="px-2 py-1 text-slate-400 hover:text-slate-600 rounded text-xs font-semibold"
              >
                Close
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="bg-slate-50 p-2.5 rounded-lg">
                <span className="text-[10px] text-slate-400 uppercase font-semibold">Checkpoint Path</span>
                <div className="font-mono text-[11px] text-slate-700 truncate mt-0.5">
                  {selectedVersion.checkpoint_path}
                </div>
              </div>
              <div className="bg-slate-50 p-2.5 rounded-lg">
                <span className="text-[10px] text-slate-400 uppercase font-semibold">Active Reader Pins</span>
                <div className="font-bold text-slate-800 mt-0.5">{selectedVersion.active_readers}</div>
              </div>
            </div>

            {/* Weights Summary */}
            <div className="p-3 bg-blue-50/50 rounded-xl border border-blue-100 text-xs">
              <div className="font-bold text-slate-800 mb-2">Weight Vector Statistics</div>
              <div className="grid grid-cols-3 gap-2 font-mono text-[11px]">
                <div>
                  <span className="text-slate-400 block text-[10px]">L2 Norm</span>
                  <strong>{selectedVersion.weights_summary?.l2_norm}</strong>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px]">Mean</span>
                  <strong>{selectedVersion.weights_summary?.mean}</strong>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px]">Std Dev</span>
                  <strong>{selectedVersion.weights_summary?.std}</strong>
                </div>
              </div>
            </div>

            {/* Historical Contributions */}
            <div>
              <div className="text-xs font-bold text-slate-800 mb-2">Applied Model Contributions</div>
              <div className="space-y-1.5 max-h-40 overflow-y-auto">
                {selectedVersion.contributions?.length === 0 ? (
                  <div className="text-xs text-slate-400 italic">Genesis baseline weights (no prior contributions).</div>
                ) : (
                  selectedVersion.contributions?.map((c) => (
                    <div key={c.contribution_id} className="p-2 bg-slate-50 rounded border border-slate-200/60 text-[11px] flex justify-between items-center">
                      <div>
                        <span className="font-bold text-slate-700 capitalize">{c.client_id}</span>
                        <div className="text-slate-400 font-mono text-[10px]">{c.transaction_id}</div>
                      </div>
                      <div className="text-right">
                        <span className={`px-2 py-0.5 text-[10px] font-bold rounded ${
                          c.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'
                        }`}>
                          {c.is_active ? 'Active' : 'Rolled Back'}
                        </span>
                        <div className="text-[10px] text-slate-400 font-mono mt-0.5">Norm: {c.weight_norm}</div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
