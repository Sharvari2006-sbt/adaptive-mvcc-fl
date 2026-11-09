import React from 'react';
import { 
  LayoutDashboard, 
  Building2, 
  ArrowLeftRight, 
  GitBranch, 
  FileText, 
  Sliders, 
  BarChart3, 
  AlertTriangle,
  DatabaseZap,
  Activity
} from 'lucide-react';

export default function Sidebar({ activePage, setActivePage, isCrashed, isRunning }) {
  const navItems = [
    { id: 'overview', label: 'Overview Dashboard', icon: LayoutDashboard },
    { id: 'clients', label: 'Client Management', icon: Building2 },
    { id: 'transactions', label: 'Transaction Explorer', icon: ArrowLeftRight },
    { id: 'mvcc', label: 'MVCC Version Explorer', icon: GitBranch },
    { id: 'wal', label: 'WAL & Crash Recovery', icon: FileText },
    { id: 'optimization', label: 'Optimization Center', icon: Sliders },
    { id: 'analytics', label: 'Reports & Analytics', icon: BarChart3 },
  ];

  return (
    <aside className="w-64 bg-navy-950 text-slate-300 flex flex-col shrink-0 min-h-screen border-r border-navy-800">
      {/* Brand Header */}
      <div className="p-5 border-b border-navy-800 flex items-center space-x-3">
        <div className="p-2 bg-gradient-to-tr from-teal-600 to-blue-600 rounded-lg text-white shadow-md shadow-teal-900/30">
          <DatabaseZap className="w-6 h-6" />
        </div>
        <div>
          <h1 className="text-base font-bold text-white tracking-wide">Adaptive MVCC</h1>
          <p className="text-xs text-teal-400 font-mono">AFL Coordinator</p>
        </div>
      </div>

      {/* Crash Banner if crashed */}
      {isCrashed && (
        <div className="m-3 p-3 bg-red-950/80 border border-red-800 rounded-lg flex items-center space-x-2 text-red-300 text-xs animate-pulse">
          <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
          <span>Server Crashed! Recovery required.</span>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1">
        <div className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          DBMS Core Modules
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activePage === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActivePage(item.id)}
              className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                isActive
                  ? 'bg-blue-600/20 text-teal-300 border-l-4 border-teal-400 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-navy-900/60'
              }`}
            >
              <Icon className={`w-4 h-4 ${isActive ? 'text-teal-400' : 'text-slate-400'}`} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* System Status Footer */}
      <div className="p-4 border-t border-navy-800 text-xs bg-navy-900/40">
        <div className="flex items-center justify-between mb-2">
          <span className="text-slate-400">FL Engine</span>
          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold ${
            isCrashed
              ? 'bg-red-500/20 text-red-300'
              : isRunning
              ? 'bg-emerald-500/20 text-emerald-300'
              : 'bg-amber-500/20 text-amber-300'
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
              isCrashed ? 'bg-red-400' : isRunning ? 'bg-emerald-400 animate-ping' : 'bg-amber-400'
            }`} />
            {isCrashed ? 'CRASHED' : isRunning ? 'RUNNING' : 'PAUSED'}
          </span>
        </div>
        <div className="text-[11px] text-slate-500 font-mono">
          5 Banks Simulated
        </div>
      </div>
    </aside>
  );
}
