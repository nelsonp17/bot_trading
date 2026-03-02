import { useState, useEffect } from 'react';
import axios from 'axios';
import { History, ArrowUpRight, ArrowDownRight } from 'lucide-react';

const API_BASE = 'http://localhost:8000/api';

export default function TradesTable() {
    const [trades, setTrades] = useState([]);

    useEffect(() => {
        const fetchTrades = async () => {
            try {
                const res = await axios.get(`${API_BASE}/trades`);
                setTrades(res.data);
            } catch (err) {
                console.error("Failed to fetch trades:", err);
            }
        };
        fetchTrades();
        const interval = setInterval(fetchTrades, 5000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="bg-gray-800 rounded-2xl border border-gray-700 overflow-hidden shadow-lg h-full flex flex-col">
            <div className="p-5 border-b border-gray-700 flex justify-between items-center bg-gray-800/50">
                <h2 className="text-lg font-semibold flex items-center gap-2">
                    <History className="w-5 h-5 text-blue-400" />
                    Recent Trades
                </h2>
                <span className="text-xs font-medium px-2.5 py-1 bg-blue-500/10 text-blue-400 rounded-full">
                    {trades.length} entries
                </span>
            </div>

            <div className="overflow-y-auto flex-1 p-2">
                {trades.length === 0 ? (
                    <div className="text-center text-gray-500 py-10">No recent trades found.</div>
                ) : (
                    <div className="flex flex-col gap-2">
                        {trades.map((trade, i) => {
                            const isBuy = trade.side === 'COMPRA';
                            return (
                                <div key={i} className="flex justify-between items-center p-3 rounded-lg hover:bg-gray-700/50 transition-colors border border-transparent hover:border-gray-600">
                                    <div className="flex items-center gap-3">
                                        <div className={`p-2 rounded-full ${isBuy ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                                            {isBuy ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
                                        </div>
                                        <div>
                                            <div className="font-semibold text-sm">{trade.side}</div>
                                            <div className="text-xs text-gray-400">{new Date(trade.timestamp).toLocaleString()}</div>
                                        </div>
                                    </div>
                                    <div className="text-right">
                                        <div className="text-sm font-bold text-gray-200">${trade.price?.toFixed(2)}</div>
                                        <div className="text-xs text-gray-400">Qty: {trade.amount?.toFixed(6)}</div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
}
