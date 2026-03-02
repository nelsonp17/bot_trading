import { useState, useEffect } from 'react';
import axios from 'axios';
import { BrainCircuit, CheckCircle2, XCircle, MinusCircle } from 'lucide-react';

const API_BASE = 'http://localhost:8000/api';

export default function PredictionsTable() {
    const [predictions, setPredictions] = useState([]);

    useEffect(() => {
        const fetchPredictions = async () => {
            try {
                const res = await axios.get(`${API_BASE}/predictions`);
                setPredictions(res.data);
            } catch (err) {
                console.error("Failed to fetch predictions:", err);
            }
        };
        fetchPredictions();
        const interval = setInterval(fetchPredictions, 5000);
        return () => clearInterval(interval);
    }, []);

    const getSignalBadge = (signal) => {
        switch (signal?.toUpperCase()) {
            case 'COMPRA':
                return <span className="flex items-center gap-1 text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-md text-xs font-bold border border-emerald-500/20"><CheckCircle2 className="w-3.5 h-3.5" /> BUY</span>;
            case 'VENTA':
                return <span className="flex items-center gap-1 text-red-400 bg-red-500/10 px-2.5 py-1 rounded-md text-xs font-bold border border-red-500/20"><XCircle className="w-3.5 h-3.5" /> SELL</span>;
            default:
                return <span className="flex items-center gap-1 text-gray-400 bg-gray-500/10 px-2.5 py-1 rounded-md text-xs font-bold border border-gray-500/20"><MinusCircle className="w-3.5 h-3.5" /> HOLD</span>;
        }
    };

    return (
        <div className="bg-gray-800 rounded-2xl border border-gray-700 overflow-hidden shadow-lg h-full flex flex-col">
            <div className="p-5 border-b border-gray-700 flex justify-between items-center bg-gray-800/50">
                <h2 className="text-lg font-semibold flex items-center gap-2">
                    <BrainCircuit className="w-5 h-5 text-purple-400" />
                    AI Predictions Log
                </h2>
                <span className="text-xs font-medium px-2.5 py-1 bg-purple-500/10 text-purple-400 rounded-full">
                    {predictions.length} entries
                </span>
            </div>

            <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="border-b border-gray-700 text-xs uppercase text-gray-400 font-semibold bg-gray-800/80">
                            <th className="py-3 px-4">Time</th>
                            <th className="py-3 px-4">Signal</th>
                            <th className="py-3 px-4">Confidence</th>
                            <th className="py-3 px-4">Reasoning</th>
                        </tr>
                    </thead>
                    <tbody className="text-sm">
                        {predictions.length === 0 && (
                            <tr>
                                <td colSpan="4" className="text-center text-gray-500 py-10">
                                    No recent predictions available.
                                </td>
                            </tr>
                        )}
                        {predictions.map((pred, i) => (
                            <tr key={i} className="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors">
                                <td className="py-3 px-4 text-gray-300 whitespace-nowrap">
                                    {new Date(pred.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </td>
                                <td className="py-3 px-4">
                                    {getSignalBadge(pred.prediction)}
                                </td>
                                <td className="py-3 px-4">
                                    <div className="flex items-center gap-2">
                                        <div className="w-16 h-2 bg-gray-700 rounded-full overflow-hidden">
                                            <div
                                                className={`h-full rounded-full ${pred.confidence > 0.6 ? 'bg-emerald-500' : pred.confidence > 0.4 ? 'bg-amber-500' : 'bg-red-500'}`}
                                                style={{ width: `${Math.min(100, (pred.confidence || 0) * 100)}%` }}
                                            ></div>
                                        </div>
                                        <span className="text-xs font-medium text-gray-300">
                                            {((pred.confidence || 0) * 100).toFixed(0)}%
                                        </span>
                                    </div>
                                </td>
                                <td className="py-3 px-4 text-gray-400 max-w-xs truncate" title={pred.reasoning}>
                                    {pred.reasoning}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
