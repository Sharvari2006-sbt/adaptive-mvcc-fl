import React, { useEffect, useState } from 'react';
import { 
  BarChart3, 
  Download, 
  HardDrive, 
  TrendingUp, 
  CheckCircle2, 
  Clock, 
  Layers, 
  Activity,
  FileSpreadsheet
} from 'lucide-react';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  Legend
} from 'recharts';
import api from '../services/api';

export default function ReportsAnalytics() {
  const [overview, setOverview] = useState(null);
  const [history, setHistory] = useState({ accuracy_loss_series: [], client_stats: [] });
  const [diffMetrics, setDiffMetrics] = useState(null);
  const [baselineComparison, setBaselineComparison] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      const [ovRes, histRes, diffRes, baselineRes] = await Promise.all([
        api.getOverview(),
        api.getHistory(),
        api.getDifferentialMetrics(),
        api.getBaselineComparison()
      ]);
      setOverview(ovRes.data);
      setHistory(histRes.data);
      setDiffMetrics(diffRes.data);
      setBaselineComparison(baselineRes.data);
    } catch (err) {
      console.error("Failed to load analytics:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 4000);
    return () => clearInterval(interval);
  }, []);

  const pieData = overview ? [
    { name: 'Committed', value: overview.committed_transactions || 0, color: '#10B981' },
    { name: 'Aborted / Conflicts', value: overview.aborted_transactions || 0, color: '#F59E0B' },
  ] : [];

  const storageCompareData = diffMetrics ? [
    { name: 'Full Model Logging', mb: diffMetrics.full_model_logging_mb },
    { name: 'Proposed Differential WAL', mb: diffMetrics.differential_logging_mb },
  ] : [];

  return (
    <div className="space-y-6">
      {/* Title & Download CSV */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Academic Reports & Quantitative Analytics</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Runtime metrics, convergence curves, storage estimates, and CSV experiment log export.
          </p>
        </div>

        <a
          href={api.getExportCsvUrl()}
          download="mvcc_fl_experiment_results.csv"
          className="inline-flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold transition-all shadow-xs"
        >
          <Download className="w-4 h-4" />
          <span>Download Experiment Results (CSV)</span>
        </a>
      </div>

      {/* Summary KPI Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs">
          <span className="text-xs text-slate-400 font-semibold uppercase">Total Transactions</span>
          <div className="text-2xl font-bold font-mono text-slate-900 mt-1">{overview?.total_transactions || 0}</div>
          <span className="text-[11px] text-slate-500 mt-0.5 block">{overview?.commit_rate_percent || 100}% Success Rate</span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs">
          <span className="text-xs text-slate-400 font-semibold uppercase">Global Model Accuracy</span>
          <div className="text-2xl font-bold font-mono text-emerald-600 mt-1">
            {((overview?.model_accuracy || 0) * 100).toFixed(1)}%
          </div>
          <span className="text-[11px] text-slate-500 mt-0.5 block">Loss: {overview?.model_loss || 0}</span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs">
          <span className="text-xs text-slate-400 font-semibold uppercase">Disk Space Conserved</span>
          <div className="text-2xl font-bold font-mono text-teal-600 mt-1">
            {overview?.storage_reduction_percent || 0}%
          </div>
          <span className="text-[11px] text-slate-500 mt-0.5 block">{overview?.storage_saved_mb || 0} MB Reclaimed</span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs">
          <span className="text-xs text-slate-400 font-semibold uppercase">MVCC Version Depth</span>
          <div className="text-2xl font-bold font-mono text-blue-600 mt-1">
            {overview?.current_version_id || 'v0'}
          </div>
          <span className="text-[11px] text-slate-500 mt-0.5 block">Lineage Tree Intact</span>
        </div>
      </div>

      {/* Charts Grid */}
      <section className="bg-white p-5 rounded-xl border border-slate-200 shadow-2xs">
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-slate-800">MVCC vs Last-Writer-Wins Replay</h3>
            <p className="text-xs text-slate-500 mt-1">
              Deterministic replay of recorded deltas against each client’s original snapshot.
              This compares aggregation behavior and excludes local training and database I/O.
            </p>
          </div>
          <span className="text-[11px] text-slate-500 whitespace-nowrap">
            {baselineComparison?.replayed_contributions || 0} updates replayed
          </span>
        </div>
        {baselineComparison?.status === 'COMPARISON_READY' ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
            <div className="rounded-lg bg-slate-50 p-4">
              <div className="text-xs font-semibold uppercase text-slate-500">Last-Writer-Wins</div>
              <div className="mt-2 text-sm text-slate-700">Accuracy <b>{(baselineComparison.baseline_accuracy * 100).toFixed(2)}%</b></div>
              <div className="text-sm text-slate-700">Loss <b>{baselineComparison.baseline_loss.toFixed(4)}</b></div>
              <div className="text-xs text-slate-500 mt-1">Replay time {baselineComparison.baseline_replay_ms} ms</div>
            </div>
            <div className="rounded-lg bg-blue-50 p-4">
              <div className="text-xs font-semibold uppercase text-blue-700">Validated MVCC</div>
              <div className="mt-2 text-sm text-slate-700">Accuracy <b>{(baselineComparison.engine_accuracy * 100).toFixed(2)}%</b></div>
              <div className="text-sm text-slate-700">Loss <b>{baselineComparison.engine_loss.toFixed(4)}</b></div>
              <div className="text-xs text-slate-500 mt-1">Weight difference L2 {baselineComparison.weight_difference_l2}</div>
            </div>
          </div>
        ) : (
          <p className="mt-4 text-xs text-slate-500">No replayable committed updates are available yet.</p>
        )}
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Model Accuracy Over Versions */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-2xs">
          <h3 className="text-sm font-bold text-slate-800 mb-1">Convergence Curve (Accuracy & Loss)</h3>
          <p className="text-xs text-slate-500 mb-4">Tracking model generalization as transactions commit to MVCC</p>

          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history.accuracy_loss_series}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="version" stroke="#94a3b8" fontSize={11} />
                <YAxis yAxisId="left" domain={[0, 100]} stroke="#94a3b8" fontSize={11} unit="%" />
                <YAxis yAxisId="right" orientation="right" stroke="#94a3b8" fontSize={11} domain={[0, 1.5]} />
                <Tooltip contentStyle={{ backgroundColor: '#0B132B', borderColor: '#141E33', borderRadius: '8px', color: '#fff', fontSize: '12px' }} />
                <Legend />
                <Line yAxisId="left" type="monotone" dataKey="accuracy" name="Accuracy (%)" stroke="#10B981" strokeWidth={2.5} dot={{ r: 3 }} />
                <Line yAxisId="right" type="monotone" dataKey="loss" name="Cross-Entropy Loss" stroke="#EF4444" strokeWidth={2} dot={false} strokeDasharray="3 3" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Storage Comparison Chart: Full vs Differential */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-2xs">
          <h3 className="text-sm font-bold text-slate-800 mb-1">Storage Efficiency Comparison</h3>
          <p className="text-xs text-slate-500 mb-4">Naive Full Snapshot Storage vs Proposed Differential Delta WAL</p>

          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={storageCompareData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} />
                <YAxis stroke="#94a3b8" fontSize={11} unit=" MB" />
                <Tooltip contentStyle={{ backgroundColor: '#0B132B', borderColor: '#141E33', borderRadius: '8px', color: '#fff', fontSize: '12px' }} />
                <Bar dataKey="mb" name="Storage Size (MB)" fill="#0D9488" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
