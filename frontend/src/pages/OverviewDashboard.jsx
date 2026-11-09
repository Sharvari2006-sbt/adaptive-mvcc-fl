import React, { useEffect, useState } from 'react';
import { 
  Building2, 
  GitCommit, 
  AlertCircle, 
  HardDrive, 
  TrendingUp, 
  Cpu, 
  CheckCircle2, 
  XCircle,
  Clock,
  Sparkles
} from 'lucide-react';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar
} from 'recharts';
import api from '../services/api';

export default function OverviewDashboard({ onStep, onToggleContinuous, isRunning, isCrashed }) {
  const [overview, setOverview] = useState(null);
  const [history, setHistory] = useState({ accuracy_loss_series: [], client_stats: [] });
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      const [ovRes, histRes] = await Promise.all([
        api.getOverview(),
        api.getHistory()
      ]);
      setOverview(ovRes.data);
      setHistory(histRes.data);
    } catch (err) {
      console.error("Failed to load overview data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !overview) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-400">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-500 mr-3"></div>
        Loading DBMS Overview...
      </div>
    );
  }

  const kpis = [
    {
      title: 'Current Head Version',
      value: overview?.current_version_id || 'v0',
      subtitle: `Version #${overview?.current_version_number || 0}`,
      icon: GitCommit,
      color: 'blue'
    },
    {
      title: 'Active Bank Clients',
      value: `${overview?.active_clients || 0} / ${overview?.total_clients || 5}`,
      subtitle: 'Simulated AFL Nodes',
      icon: Building2,
      color: 'teal'
    },
    {
      title: 'Committed Transactions',
      value: overview?.committed_transactions || 0,
      subtitle: `${overview?.commit_rate_percent || 100}% commit rate`,
      icon: CheckCircle2,
      color: 'emerald'
    },
    {
      title: 'Aborted / Conflicts',
      value: overview?.aborted_transactions || 0,
      subtitle: 'OCC & Stale rejections',
      icon: XCircle,
      color: 'amber'
    },
    {
      title: 'Storage Optimization',
      value: `${overview?.storage_reduction_percent || 0}%`,
      subtitle: `${overview?.storage_saved_mb || 0} MB saved via Diff WAL`,
      icon: HardDrive,
      color: 'cyan'
    },
    {
      title: 'Global Accuracy',
      value: `${((overview?.model_accuracy || 0) * 100).toFixed(1)}%`,
      subtitle: `Loss: ${overview?.model_loss || 0}`,
      icon: TrendingUp,
      color: 'emerald'
    }
  ];

  return (
    <div className="space-y-6">
      {/* Page Title & Intro */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900">DBMS Transaction Coordinator Overview</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Real-time multi-version concurrency control, validation telemetry, and federated learning aggregation.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => onStep()}
            disabled={isCrashed}
            className="px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 text-xs font-medium rounded-lg shadow-2xs"
          >
            Step Bank Round
          </button>
          <button
            onClick={onToggleContinuous}
            disabled={isCrashed}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg shadow-xs text-white ${
              isRunning ? 'bg-amber-600 hover:bg-amber-700' : 'bg-teal-600 hover:bg-teal-700'
            }`}
          >
            {isRunning ? 'Pause Engine' : 'Resume Continuous Engine'}
          </button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {kpis.map((kpi, idx) => {
          const Icon = kpi.icon;
          return (
            <div key={idx} className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-[11px] font-medium uppercase tracking-wider">{kpi.title}</span>
                <Icon className="w-4 h-4 text-slate-400" />
              </div>
              <div className="text-xl font-bold text-slate-900 font-mono">{kpi.value}</div>
              <div className="text-[11px] text-slate-500 mt-1 truncate">{kpi.subtitle}</div>
            </div>
          );
        })}
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Model Accuracy & Loss Convergence Curve */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-2xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-slate-800">Model Accuracy Convergence</h3>
              <p className="text-xs text-slate-500">Global fraud classification accuracy over committed MVCC versions</p>
            </div>
            <span className="px-2 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-bold rounded">
              MVCC Lineage
            </span>
          </div>

          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={history.accuracy_loss_series}>
                <defs>
                  <linearGradient id="colorAcc" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0D9488" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#0D9488" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="version" stroke="#94a3b8" fontSize={11} />
                <YAxis domain={[0, 100]} stroke="#94a3b8" fontSize={11} unit="%" />
                <Tooltip 
                  formatter={(val) => [`${val}%`, 'Accuracy']}
                  contentStyle={{ backgroundColor: '#0B132B', borderColor: '#141E33', borderRadius: '8px', color: '#fff', fontSize: '12px' }}
                />
                <Area type="monotone" dataKey="accuracy" stroke="#0D9488" strokeWidth={2} fillOpacity={1} fill="url(#colorAcc)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Client Submissions & Commits Distribution */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-2xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-slate-800">Client Throughput Breakdown</h3>
              <p className="text-xs text-slate-500">Commits vs Aborts per independent simulated bank client</p>
            </div>
            <span className="px-2 py-0.5 bg-blue-50 text-blue-700 border border-blue-200 text-[10px] font-bold rounded">
              5 Banks
            </span>
          </div>

          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={history.client_stats}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="client_id" stroke="#94a3b8" fontSize={11} tickFormatter={(val) => val.toUpperCase().replace('_', ' ')} />
                <YAxis stroke="#94a3b8" fontSize={11} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0B132B', borderColor: '#141E33', borderRadius: '8px', color: '#fff', fontSize: '12px' }}
                />
                <Bar dataKey="successful_commits" name="Committed" fill="#1E40AF" radius={[4, 4, 0, 0]} />
                <Bar dataKey="aborted_txns" name="Aborted" fill="#F59E0B" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Quick Interactive DBMS Demo Cards */}
      <div className="bg-gradient-to-r from-navy-900 to-navy-950 text-white p-6 rounded-2xl shadow-md border border-navy-800">
        <div className="flex items-center space-x-2 text-teal-400 text-xs font-bold uppercase tracking-wider mb-2">
          <Sparkles className="w-4 h-4" />
          <span>Interactive Demonstration Presets</span>
        </div>
        <h3 className="text-base font-bold text-white mb-1">Simulate Anomaly Scenarios for Live Evaluation</h3>
        <p className="text-xs text-slate-400 mb-4 max-w-2xl">
          Trigger real backend conditions including delayed high-latency updates, outdated snapshot rejections, and poisoned model updates.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
          <button
            onClick={async () => {
              await api.controlClient("bank_e", { delay_seconds: 3.0 });
              await onStep("bank_e");
            }}
            className="p-3 bg-navy-800/80 hover:bg-navy-800 border border-navy-700 rounded-xl text-left transition-all"
          >
            <div className="text-xs font-bold text-teal-300">Simulate Delayed Client</div>
            <div className="text-[11px] text-slate-400 mt-1">Bank E introduces 3.0s network latency to test staleness.</div>
          </button>

          <button
            onClick={async () => {
              await api.controlClient("bank_d", { force_outdated: true });
              await onStep("bank_d");
            }}
            className="p-3 bg-navy-800/80 hover:bg-navy-800 border border-navy-700 rounded-xl text-left transition-all"
          >
            <div className="text-xs font-bold text-amber-300">Submit Outdated Update</div>
            <div className="text-[11px] text-slate-400 mt-1">Bank D submits against V0 to trigger staleness rejection.</div>
          </button>

          <button
            onClick={async () => {
              await api.controlClient("bank_c", { is_malicious: true });
              await onStep("bank_c");
            }}
            className="p-3 bg-navy-800/80 hover:bg-navy-800 border border-navy-700 rounded-xl text-left transition-all"
          >
            <div className="text-xs font-bold text-red-300">Inject Poisoned Update</div>
            <div className="text-[11px] text-slate-400 mt-1">Bank C injects malicious weights for Selective Rollback.</div>
          </button>

          <button
            onClick={async () => {
              await api.runGarbageCollection(2);
              fetchData();
            }}
            className="p-3 bg-navy-800/80 hover:bg-navy-800 border border-navy-700 rounded-xl text-left transition-all"
          >
            <div className="text-xs font-bold text-blue-300">Run Vacuum / GC</div>
            <div className="text-[11px] text-slate-400 mt-1">Prunes unpinned versions while preserving active snapshots.</div>
          </button>
        </div>
      </div>
    </div>
  );
}
