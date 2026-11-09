import axios from 'axios';

const API_BASE = '/api/v1';

const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const api = {
  // FL Clients
  getClients: () => apiClient.get('/fl/clients'),
  controlClient: (clientId, data) => apiClient.post(`/fl/clients/${clientId}/control`, data),
  getSnapshot: (clientId) => apiClient.get(`/fl/snapshot/${clientId}`),
  submitUpdate: (data) => apiClient.post('/fl/submit-update', data),
  stepSimulation: (clientId = null) => apiClient.post(`/fl/simulation/step${clientId ? `?client_id=${clientId}` : ''}`),
  startSimulation: () => apiClient.post('/fl/simulation/start'),
  pauseSimulation: () => apiClient.post('/fl/simulation/pause'),
  getSimulationStatus: () => apiClient.get('/fl/simulation/status'),

  // Transactions
  getTransactions: (params) => apiClient.get('/transactions', { params }),
  getTransactionDetail: (txnId) => apiClient.get(`/transactions/${txnId}`),
  getSchedulerQueue: () => apiClient.get('/transactions/queue'),

  // MVCC
  getVersions: () => apiClient.get('/mvcc/versions'),
  getActiveSnapshots: () => apiClient.get('/mvcc/snapshots'),
  inspectVersion: (versionId) => apiClient.get(`/mvcc/versions/${versionId}`),

  // WAL & Recovery
  getWalRecords: (params) => apiClient.get('/wal/records', { params }),
  getWalIntegrity: () => apiClient.get('/wal/integrity'),
  simulateCrash: () => apiClient.post('/wal/simulate-crash'),
  restartAndRecover: () => apiClient.post('/wal/restart-recover'),
  getRecoveryStats: () => apiClient.get('/wal/recovery-stats'),
  createCheckpoint: () => apiClient.post('/wal/checkpoint'),

  // Optimization Center (6 Novelty Features)
  getStalenessConfig: () => apiClient.get('/optimization/staleness/config'),
  updateStalenessConfig: (data) => apiClient.post('/optimization/staleness/config', data),
  getSchedulerQueueStatus: () => apiClient.get('/optimization/scheduler/queue'),
  triggerSelectiveRollback: (data) => apiClient.post('/optimization/rollback', data),
  runGarbageCollection: (keepLatest = 3) => apiClient.post(`/optimization/gc/run?keep_latest=${keepLatest}`),
  getGcStats: () => apiClient.get('/optimization/gc/stats'),
  testConflictPrediction: (data) => apiClient.post('/optimization/predict', data),
  getDifferentialMetrics: () => apiClient.get('/optimization/differential/metrics'),

  // Analytics
  getOverview: () => apiClient.get('/analytics/overview'),
  getHistory: () => apiClient.get('/analytics/history'),
  getBaselineComparison: () => apiClient.get('/analytics/baseline-comparison'),
  getExportCsvUrl: () => `${API_BASE}/analytics/export-csv`,
};

export default api;
