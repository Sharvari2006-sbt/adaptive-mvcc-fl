import React, { useEffect, useState } from 'react';
import { 
  ArrowLeftRight, 
  Search, 
  Filter, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  ShieldAlert, 
  FileText,
  ListOrdered,
  Eye,
  X
} from 'lucide-react';
import api from '../services/api';

export default function TransactionMgmt() {
  const [transactions, setTransactions] = useState([]);
  const [total, setTotal] = useState(0);
  const [queue, setQueue] = useState([]);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [clientFilter, setClientFilter] = useState('ALL');
  const [selectedTxn, setSelectedTxn] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchTransactions = async () => {
    try {
      const res = await api.getTransactions({
        status: statusFilter,
        client_id: clientFilter,
        limit: 50,
        offset: 0
      });
      setTransactions(res.data.transactions);
      setTotal(res.data.total);

      const queueRes = await api.getSchedulerQueue();
      setQueue(queueRes.data);
    } catch (err) {
      console.error("Failed to load transactions:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTransactions();
    const interval = setInterval(fetchTransactions, 3000);
    return () => clearInterval(interval);
  }, [statusFilter, clientFilter]);

  const openInspection = async (txnId) => {
    try {
      const res = await api.getTransactionDetail(txnId);
      setSelectedTxn(res.data);
    } catch (err) {
      console.error("Failed to inspect txn:", err);
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Title & Filter Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Transaction Coordinator & OCC Ledger</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Audit trail of optimistic concurrency control validations, staleness calculations, and commits.
          </p>
        </div>

        {/* Filters */}
        <div className="flex items-center space-x-2">
          {/* Status filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-1.5 bg-white border border-slate-300 rounded-lg text-xs font-medium text-slate-700 shadow-2xs focus:outline-teal-500"
          >
            <option value="ALL">All Statuses</option>
            <option value="COMMITTED">COMMITTED</option>
            <option value="ABORTED">ABORTED</option>
            <option value="PENDING">PENDING</option>
            <option value="VALIDATING">VALIDATING</option>
          </select>

          {/* Client filter */}
          <select
            value={clientFilter}
            onChange={(e) => setClientFilter(e.target.value)}
            className="px-3 py-1.5 bg-white border border-slate-300 rounded-lg text-xs font-medium text-slate-700 shadow-2xs focus:outline-teal-500"
          >
            <option value="ALL">All Banks</option>
            <option value="bank_a">Bank A</option>
            <option value="bank_b">Bank B</option>
            <option value="bank_c">Bank C</option>
            <option value="bank_d">Bank D</option>
            <option value="bank_e">Bank E</option>
          </select>
        </div>
      </div>

      {/* Live Priority Queue Section */}
      {queue.length > 0 && (
        <div className="bg-gradient-to-r from-blue-50 to-teal-50 border border-teal-200 rounded-xl p-4">
          <div className="flex items-center space-x-2 mb-2 text-teal-900 font-bold text-xs uppercase tracking-wider">
            <ListOrdered className="w-4 h-4 text-teal-600" />
            <span>Priority Scheduler Queue ({queue.length} In-Flight / Waiting)</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
            {queue.map((item, idx) => (
              <div key={item.transaction_id} className="bg-white/80 p-2.5 rounded-lg border border-teal-100 text-xs flex justify-between items-center">
                <div>
                  <span className="font-mono font-bold text-slate-800">{item.transaction_id}</span>
                  <div className="text-[11px] text-slate-500">{item.client_id.toUpperCase()} • Staleness: {item.staleness}</div>
                </div>
                <div className="text-right">
                  <span className="px-2 py-0.5 bg-teal-100 text-teal-800 font-mono font-bold rounded text-[11px]">
                    Priority: {item.priority_score}
                  </span>
                  <div className="text-[10px] text-slate-400 mt-0.5">{item.waiting_time_seconds}s waiting</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Transactions Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[10px]">
              <tr>
                <th className="px-4 py-3">Txn ID</th>
                <th className="px-4 py-3">Client</th>
                <th className="px-4 py-3">Base Snapshot</th>
                <th className="px-4 py-3">Committed Version</th>
                <th className="px-4 py-3">Staleness</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">OCC Validation</th>
                <th className="px-4 py-3">Submitted At</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {transactions.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-slate-400">
                    No transactions match the selected filters.
                  </td>
                </tr>
              ) : (
                transactions.map((t) => {
                  const isComm = t.status === 'COMMITTED';
                  const isAbort = t.status === 'ABORTED';
                  return (
                    <tr key={t.transaction_id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="px-4 py-3 font-mono font-bold text-slate-800">{t.transaction_id}</td>
                      <td className="px-4 py-3 font-medium text-slate-700 capitalize">{t.client_id.replace('_', ' ')}</td>
                      <td className="px-4 py-3 font-mono text-slate-600">{t.base_version_id}</td>
                      <td className="px-4 py-3 font-mono font-semibold text-blue-700">
                        {t.committed_version_id || '—'}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded text-[11px] font-mono font-semibold ${
                          t.staleness === 0 
                            ? 'bg-emerald-50 text-emerald-700' 
                            : t.staleness <= 3 
                            ? 'bg-blue-50 text-blue-700' 
                            : 'bg-amber-50 text-amber-800'
                        }`}>
                          Δ {t.staleness}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          isComm
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : isAbort
                            ? 'bg-red-50 text-red-700 border border-red-200'
                            : 'bg-blue-50 text-blue-700 border border-blue-200'
                        }`}>
                          {isComm ? <CheckCircle2 className="w-3 h-3 text-emerald-600" /> : isAbort ? <XCircle className="w-3 h-3 text-red-600" /> : <Clock className="w-3 h-3 text-blue-600" />}
                          <span>{t.status}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-semibold text-slate-700">
                          {t.validation_result || 'PASSED'}
                        </div>
                        {t.failure_reason && (
                          <div className="text-[10px] text-red-500 truncate max-w-xs">{t.failure_reason}</div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-slate-400 font-mono text-[11px]">
                        {t.submitted_at ? new Date(t.submitted_at).toLocaleTimeString() : '—'}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => openInspection(t.transaction_id)}
                          className="p-1 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded"
                          title="Inspect Details"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Transaction Details Drawer / Modal */}
      {selectedTxn && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-lg w-full border border-slate-200 shadow-xl overflow-hidden p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Transaction Inspection</h3>
                <p className="text-xs text-slate-400 font-mono">{selectedTxn.transaction_id}</p>
              </div>
              <button onClick={() => setSelectedTxn(null)} className="p-1 text-slate-400 hover:text-slate-600 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="bg-slate-50 p-2.5 rounded-lg">
                <span className="text-[10px] text-slate-400 uppercase font-semibold">Initiating Client</span>
                <div className="font-bold text-slate-800 capitalize mt-0.5">{selectedTxn.client_id}</div>
              </div>
              <div className="bg-slate-50 p-2.5 rounded-lg">
                <span className="text-[10px] text-slate-400 uppercase font-semibold">Transaction Status</span>
                <div className="font-bold text-slate-800 mt-0.5">{selectedTxn.status}</div>
              </div>
              <div className="bg-slate-50 p-2.5 rounded-lg">
                <span className="text-[10px] text-slate-400 uppercase font-semibold">Base Snapshot</span>
                <div className="font-mono font-bold text-slate-800 mt-0.5">{selectedTxn.base_version_id}</div>
              </div>
              <div className="bg-slate-50 p-2.5 rounded-lg">
                <span className="text-[10px] text-slate-400 uppercase font-semibold">Resulting Version</span>
                <div className="font-mono font-bold text-blue-700 mt-0.5">{selectedTxn.committed_version_id || 'None'}</div>
              </div>
            </div>

            {/* Validation Details */}
            {selectedTxn.validation && (
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 text-xs">
                <div className="font-bold text-slate-800 mb-1">OCC Validation Audit</div>
                <div className="flex justify-between py-1 border-b border-slate-200/60">
                  <span className="text-slate-500">Result:</span>
                  <span className="font-semibold text-slate-800">{selectedTxn.validation.validation_result}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-200/60">
                  <span className="text-slate-500">Conflict Score:</span>
                  <span className="font-mono font-semibold text-slate-800">{selectedTxn.validation.conflict_score}</span>
                </div>
                {selectedTxn.validation.failure_reason && (
                  <div className="pt-1.5 text-red-600 font-medium">
                    Failure Reason: {selectedTxn.validation.failure_reason}
                  </div>
                )}
              </div>
            )}

            {/* WAL Records List */}
            <div>
              <div className="text-xs font-bold text-slate-800 mb-2">WAL Audit Trail</div>
              <div className="space-y-1.5 max-h-36 overflow-y-auto">
                {selectedTxn.wal_records?.map((r) => (
                  <div key={r.log_id} className="p-2 bg-slate-50 rounded border border-slate-200/60 text-[11px] flex justify-between items-center font-mono">
                    <span className="font-bold text-slate-700">LSN {r.lsn} • {r.record_type}</span>
                    <span className="text-slate-400">CRC: {r.checksum}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
