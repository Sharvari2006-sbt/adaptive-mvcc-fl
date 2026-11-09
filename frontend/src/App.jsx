import React, { lazy, Suspense, useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
const OverviewDashboard = lazy(() => import('./pages/OverviewDashboard'));
const ClientManagement = lazy(() => import('./pages/ClientManagement'));
const TransactionMgmt = lazy(() => import('./pages/TransactionMgmt'));
const MVCCExplorer = lazy(() => import('./pages/MVCCExplorer'));
const WALRecovery = lazy(() => import('./pages/WALRecovery'));
const OptimizationCenter = lazy(() => import('./pages/OptimizationCenter'));
const ReportsAnalytics = lazy(() => import('./pages/ReportsAnalytics'));
import api from './services/api';

export default function App() {
  const [activePage, setActivePage] = useState('overview');
  const [overview, setOverview] = useState(null);
  const [isCrashed, setIsCrashed] = useState(false);
  const [isRunning, setIsRunning] = useState(false);

  const fetchGlobalState = async () => {
    try {
      const [ovRes, simRes] = await Promise.all([
        api.getOverview(),
        api.getSimulationStatus()
      ]);
      setOverview(ovRes.data);
      setIsCrashed(ovRes.data.is_server_crashed);
      setIsRunning(simRes.data.simulation_running);
    } catch (err) {
      console.error("Failed to fetch global state:", err);
    }
  };

  useEffect(() => {
    fetchGlobalState();
    const interval = setInterval(fetchGlobalState, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleStep = async (clientId = null) => {
    try {
      await api.stepSimulation(clientId);
      await fetchGlobalState();
    } catch (err) {
      console.error("Step round failed:", err);
    }
  };

  const handleToggleContinuous = async () => {
    try {
      if (isRunning) {
        await api.pauseSimulation();
      } else {
        await api.startSimulation();
      }
      await fetchGlobalState();
    } catch (err) {
      console.error("Toggle simulation failed:", err);
    }
  };

  const handleSimulateCrash = async () => {
    try {
      await api.simulateCrash();
      await fetchGlobalState();
    } catch (err) {
      console.error("Crash simulation failed:", err);
    }
  };

  const handleRecover = async () => {
    try {
      await api.restartAndRecover();
      await fetchGlobalState();
    } catch (err) {
      console.error("Recovery failed:", err);
    }
  };

  return (
    <div className="flex min-h-screen bg-slate-50 font-sans">
      {/* Dark Navy Sidebar */}
      <Sidebar 
        activePage={activePage} 
        setActivePage={setActivePage}
        isCrashed={isCrashed}
        isRunning={isRunning}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <Header 
          currentVersion={overview?.current_version_id}
          accuracy={overview?.model_accuracy}
          isCrashed={isCrashed}
          isRunning={isRunning}
          onStep={handleStep}
          onToggleContinuous={handleToggleContinuous}
          onSimulateCrash={handleSimulateCrash}
          onRecover={handleRecover}
          onRefresh={fetchGlobalState}
        />

        <main className="flex-1 p-6 overflow-y-auto max-w-7xl w-full mx-auto">
          <Suspense fallback={<div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">Loading dashboard…</div>}>
            {activePage === 'overview' && (
              <OverviewDashboard 
              onStep={handleStep} 
              onToggleContinuous={handleToggleContinuous}
              isRunning={isRunning}
              isCrashed={isCrashed}
              />
            )}
            {activePage === 'clients' && (
              <ClientManagement 
              onStep={handleStep} 
              isCrashed={isCrashed}
              />
            )}
            {activePage === 'transactions' && <TransactionMgmt />}
            {activePage === 'mvcc' && <MVCCExplorer />}
            {activePage === 'wal' && (
              <WALRecovery 
              isCrashed={isCrashed}
              onSimulateCrash={handleSimulateCrash}
              onRecover={handleRecover}
              />
            )}
            {activePage === 'optimization' && <OptimizationCenter />}
            {activePage === 'analytics' && <ReportsAnalytics />}
          </Suspense>
        </main>
      </div>
    </div>
  );
}
