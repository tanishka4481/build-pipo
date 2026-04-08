import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { BellElectric, User, Check, ShieldAlert, CheckCircle2, ChevronRight, AlertCircle, Heart } from 'lucide-react';

import { usePopi } from '../context/PopiContext';

export default function AlertsPage() {
  const { alerts, dismissAlert } = usePopi();
  const [filter, setFilter] = useState('All');

  const dismissAlertHandler = async (id) => {
    await dismissAlert(id);
  };

  const filteredAlerts = alerts.filter(a => {
    if (filter === 'All') return !a.dismissed;
    if (filter === 'Dismissed') return a.dismissed;
    return a.type === filter && !a.dismissed;
  });

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 pb-20">
      <header className="mb-10 text-center relative pt-8">
        <div className="absolute right-10 top-0 w-32 h-32 blob blob-yellow opacity-40"></div>
        <div className="inline-block relative">
          <div className="absolute -inset-1 bg-pink-100 rounded-[32px] blur-xl opacity-60"></div>
          <div className="bg-white border-2 border-pink-100 p-8 rounded-[40px] relative z-10 shadow-sm flex flex-col items-center">
            <div className="bg-pink-100 p-5 rounded-full mb-4 text-pink-500">
               <AlertCircle size={36} />
            </div>
            <h1 className="text-4xl font-black font-serif text-gray-900 mb-2">Alerts Panel</h1>
            <p className="text-gray-500 font-bold text-lg">Review clinical flags and parent engagement.</p>
          </div>
        </div>
      </header>

      {/* Filter Tabs */}
      <div className="flex justify-center gap-3 mb-12">
        {['All', 'SLP', 'Parent', 'Dismissed'].map(tab => (
          <button
            key={tab}
            onClick={() => setFilter(tab)}
            className={`px-8 py-3 rounded-full font-bold transition-all border-2 ${filter === tab ? 'bg-primary-500 border-primary-500 text-white shadow-md' : 'bg-white border-gray-100 text-gray-500 hover:bg-gray-50 hover:border-gray-200'}`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Alerts List */}
      <div className="space-y-6 max-w-4xl mx-auto">
        {filteredAlerts.length === 0 ? (
          <div className="bg-white border-2 border-dashed border-gray-200 rounded-[40px] p-20 flex flex-col items-center justify-center text-center">
             <div className="bg-success-100 text-success-500 p-8 rounded-full mb-6">
               <CheckCircle2 size={64} />
             </div>
             <h3 className="text-3xl font-serif font-black text-gray-800 mb-3">All Caught Up!</h3>
             <p className="text-gray-500 font-bold text-lg">No {filter !== 'All' ? filter.toLowerCase() : ''} alerts requiring your attention.</p>
          </div>
        ) : (
          filteredAlerts.map(alert => (
            <AlertCard key={alert.id} alert={alert} onDismiss={dismissAlertHandler} />
          ))
        )}
      </div>
    </div>
  );
}

function AlertCard({ alert, onDismiss }) {
  const isSLP = alert.type === 'SLP';
  const isDismissed = alert.dismissed;

  const getCardStyle = () => {
    if (isDismissed) return 'bg-gray-50 border-gray-200 opacity-60';
    if (isSLP) return 'bg-pink-50 border-pink-200';
    return 'bg-white border-primary-100';
  };

  return (
    <div className={`rounded-[32px] border-2 p-8 transition-all duration-300 relative overflow-hidden group ${getCardStyle()}`}>
      {isSLP && !isDismissed && (
        <div className="absolute top-6 right-6 w-4 h-4 bg-danger-500 rounded-full animate-pulse shadow-[0_0_15px_rgba(239,68,68,0.6)]"></div>
      )}

      <div className="relative z-10 flex flex-col md:flex-row gap-8 items-start md:items-center">
        {/* Icon */}
        <div className={`p-5 rounded-[24px] shrink-0 ${isDismissed ? 'bg-gray-200 text-gray-500' : isSLP ? 'bg-white text-danger-500 shadow-sm' : 'bg-primary-100 text-primary-600'}`}>
          {isSLP ? <ShieldAlert size={32} /> : <Heart size={32} fill="currentColor" className={!isDismissed ? 'text-accent-400' : ''}/>}
        </div>

        {/* Content */}
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <h3 className={`text-2xl font-serif font-bold ${isSLP && !isDismissed ? 'text-gray-900' : 'text-gray-900'}`}>
              {alert.child_name} <span className="font-sans text-gray-400 font-bold text-[0.9rem] ml-2">· {alert.category.replace('_', ' ')}</span>
            </h3>
            <span className={`px-3 py-1 rounded-full text-xs font-bold border ${isSLP ? 'bg-white border-pink-200 text-pink-600' : 'bg-white border-gray-200 text-gray-600'}`}>
              {alert.type}
            </span>
          </div>
          <p className={`font-bold text-lg mt-3 ${isDismissed ? 'text-gray-500' : 'text-gray-700'}`}>{alert.message}</p>
          <p className="text-sm font-bold text-gray-400 mt-4 uppercase tracking-wider">{alert.created_at}</p>
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-3 shrink-0 mt-4 md:mt-0 pt-4 md:pt-0 border-t md:border-t-0 md:border-l border-gray-200/50 md:pl-8">
          <Link to={`/dashboard/child/${alert.child_id}`} className="flex justify-center items-center gap-2 text-sm font-bold bg-white text-gray-700 border-2 border-gray-100 hover:border-gray-200 px-6 py-3 rounded-full transition-all text-center">
            View Profile <ChevronRight size={16} className="text-gray-400" />
          </Link>
          {!isDismissed && (
             <button 
               onClick={() => onDismiss(alert.id)}
               className={`flex justify-center items-center gap-2 text-sm font-bold px-6 py-3 rounded-full transition-all border-2 ${isSLP ? 'bg-white border-pink-300 hover:bg-pink-100 text-pink-600' : 'bg-white border-primary-200 hover:bg-primary-100 text-primary-600'}`}
             >
               <Check size={16} /> Mark Resolved
             </button>
          )}
        </div>
      </div>
    </div>
  );
}
