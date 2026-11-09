import React from 'react';
import { 
  Play, 
  Pause, 
  FastForward, 
  Skull, 
  RotateCcw, 
  ShieldCheck, 
  AlertOctagon,
  RefreshCw
} from 'lucide-react';

export default function Header({ 
  currentVersion, 
  accuracy, 
  isCrashed, 
  isRunning, 
  onStep, 
  onToggleContinuous, 
  onSimulateCrash, 
  onRecover,
  onRefresh
}) {
  return (
    <header className="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between shadow-xs">
      {/* Title & Version info */}
      <div className="flex items-center space-x-4">
        <div>
          <div className="flex items-center space-x-2">
            <span className="text-sm font-semibold text-slate-800">Global Model Version:</span>
            <span className="px-2.5 py-0.5 bg-blue-50 text-blue-700 font-mono text-xs font-bold rounded-md border border-blue-200">
              {currentVersion || 'v0'}
            </span>
          </div>
        </div>

        <div className="hidden md:flex items-center space-x-2 pl-4 border-l border-slate-200 text-xs text-slate-500">
          <span>Global Accuracy:</span>
          <span className="font-semibold text-emerald-600 font-mono">
            {accuracy !== undefined ? `${(accuracy * 100).toFixed(1)}%` : '0.0%'}
          </span>
        </div>
      </div>

      {/* Action Controls */}
      <div className="flex items-center space-x-2">
        {/* Refresh button */}
        <button
          onClick={onRefresh}
          className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
          title="Refresh Data"
        >
          <RefreshCw className="w-4 h-4" />
        </button>

        {/* Step FL Round */}
        <button
          disabled={isCrashed}
          onClick={onStep}
          className="flex items-center space-x-1.5 px-3 py-1.5 bg-teal-50 text-teal-700 hover:bg-teal-100 disabled:opacity-40 disabled:cursor-not-allowed border border-teal-200 rounded-lg text-xs font-medium transition-all shadow-xs"
          title="Run 1 asynchronous training step for all active banks"
        >
          <FastForward className="w-3.5 h-3.5 text-teal-600" />
          <span>Step FL Round</span>
        </button>

        {/* Start / Pause Continuous AFL */}
        <button
          disabled={isCrashed}
          onClick={onToggleContinuous}
          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all shadow-xs border disabled:opacity-40 disabled:cursor-not-allowed ${
            isRunning
              ? 'bg-amber-50 text-amber-700 hover:bg-amber-100 border-amber-200'
              : 'bg-blue-600 text-white hover:bg-blue-700 border-blue-600'
          }`}
        >
          {isRunning ? (
            <>
              <Pause className="w-3.5 h-3.5" />
              <span>Pause AFL</span>
            </>
          ) : (
            <>
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Start Continuous</span>
            </>
          )}
        </button>

        {/* Simulate Crash or Restart/Recover */}
        {isCrashed ? (
          <button
            onClick={onRecover}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-emerald-600 text-white hover:bg-emerald-700 rounded-lg text-xs font-medium transition-all shadow-sm animate-bounce"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Restart & Recover</span>
          </button>
        ) : (
          <button
            onClick={onSimulateCrash}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-red-50 text-red-700 hover:bg-red-100 border border-red-200 rounded-lg text-xs font-medium transition-all"
            title="Simulate sudden power failure / coordinator crash"
          >
            <Skull className="w-3.5 h-3.5 text-red-500" />
            <span>Simulate Crash</span>
          </button>
        )}
      </div>
    </header>
  );
}
