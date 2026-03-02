import { useState, useEffect } from 'react';
import axios from 'axios';
import { Activity, TrendingUp, AlertTriangle } from 'lucide-react';
import TradesTable from './components/TradesTable';
import PredictionsTable from './components/PredictionsTable';

const API_BASE = '/api';

function App() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchStatus = async () => {
    try {
      const res = await axios.get(`${API_BASE}/status`);
      setStatus(res.data);
    } catch (err) {
      console.error("Failed to fetch status:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !status) return <div className="flex items-center justify-center min-h-screen bg-gray-900 text-gray-100 text-xl">Loading...</div>;

  const isRunning = status?.status === 'running';

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-8 font-sans">
      <header className="max-w-6xl mx-auto mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-emerald-400 flex items-center gap-3">
            <Activity className="w-8 h-8 text-blue-400" />
            AI Trading Bot
          </h1>
          <p className="text-gray-400 mt-2">Automated cryptocurrency trading powered by LLMs</p>
        </div>

        <div className="flex items-center gap-4 bg-gray-800 p-4 rounded-xl border border-gray-700 shadow-lg">
          <div className="flex flex-col items-end pr-2">
            <span className="text-sm text-gray-400">Status</span>
            <div className="flex items-center gap-2">
              <span className={`w-3 h-3 rounded-full ${isRunning ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`}></span>
              <span className={`font-semibold ${isRunning ? 'text-emerald-400' : 'text-red-400'}`}>
                {isRunning ? 'RUNNING' : 'STOPPED'}
              </span>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-8">

        {/* Info Cards */}
        <div className="lg:col-span-3 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-gray-800 p-6 rounded-2xl border border-gray-700 flex flex-col justify-between">
            <div className="flex items-center gap-3 text-gray-400 mb-2">
              <TrendingUp className="w-5 h-5 text-blue-400" />
              <span>Trading Pair</span>
            </div>
            <span className="text-2xl font-bold text-white">{status?.symbol || 'N/A'}</span>
          </div>
          <div className="bg-gray-800 p-6 rounded-2xl border border-gray-700 flex flex-col justify-between">
            <div className="flex items-center gap-3 text-gray-400 mb-2">
              <Activity className="w-5 h-5 text-purple-400" />
              <span>Timeframe</span>
            </div>
            <span className="text-2xl font-bold text-white">{status?.timeframe || 'N/A'}</span>
          </div>
          <div className="bg-gray-800 p-6 rounded-2xl border border-gray-700 flex flex-col justify-between">
            <div className="flex items-center gap-3 text-gray-400 mb-2">
              <AlertTriangle className="w-5 h-5 text-amber-400" />
              <span>Budget Assigned</span>
            </div>
            <span className="text-2xl font-bold text-white">{status?.budget ? `${status.budget} USDT` : 'N/A'}</span>
          </div>
        </div>

        {/* Tables */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          <PredictionsTable />
        </div>
        <div className="lg:col-span-1 flex flex-col gap-6">
          <TradesTable />
        </div>

      </main>
    </div>
  );
}

export default App;
