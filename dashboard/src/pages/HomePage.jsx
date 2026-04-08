import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Users, Activity, AlertTriangle, TrendingUp, ChevronRight, SquareActivity, Smile, Star, Heart } from 'lucide-react';

import { usePopi } from '../context/PopiContext';

export default function HomePage() {
  const { childrenList, alerts, dismissAlert } = usePopi();

  const totalChildren = childrenList.length;
  const practicedToday = childrenList.filter(c => c.last_active === 'Today').length;
  const pendingAlerts = alerts.length;
  const avgScore = (childrenList.reduce((acc, c) => acc + c.avg_score, 0) / (totalChildren || 1)).toFixed(2);

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-700">
      <header className="mb-10 pt-4 flex justify-between items-center relative">
        <div className="wavy-line top-0 opacity-20 hidden md:block" style={{ width: '200px', left: '-50px', transform: 'rotate(-10deg)' }}></div>
        <div>
          <h1 className="text-5xl font-black text-primary-900 mb-2 relative z-10"><span className="heading-flair">Overview</span></h1>
          <p className="text-gray-500 font-bold mt-3 text-lg">Welcome back! Let's see how our kids are doing.</p>
        </div>
        <div className="hidden md:flex bg-white px-6 py-3 rounded-full shadow-sm items-center gap-3 border border-gray-100 font-bold text-primary-900">
          <Smile className="text-accent-500" /> Have a great day!
        </div>
      </header>

      {/* Summary Strip */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-16">
        <StatCard title="Active Kids" value={totalChildren} icon={<Users size={28} />} color="bg-primary-100 text-primary-900 border-primary-200" iconColor="bg-white text-primary-500" />
        <StatCard title="Practiced Today" value={`${practicedToday} / ${totalChildren}`} icon={<Activity size={28} />} color="bg-success-100 text-success-900 border-success-400" iconColor="bg-white text-success-500" />
        <StatCard title="Alerts" value={pendingAlerts} icon={<AlertTriangle size={28} />} color="bg-alert-100 text-alert-600 border-alert-500" iconColor="bg-white text-alert-500" />
        <StatCard title="Avg Score" value={avgScore} icon={<TrendingUp size={28} />} color="bg-warning-100 text-warning-600 border-warning-400" iconColor="bg-white text-warning-500" />
      </div>

      {/* Alerts Preview */}
      {alerts.length > 0 && (
        <div className="mb-16 bg-white p-8 rounded-[32px] border-2 border-pink-100 shadow-sm relative overflow-hidden">
          <div className="wavy-line top-0 opacity-30"></div>
          <h2 className="text-3xl font-bold text-gray-900 mb-6 flex items-center gap-3 relative z-10">
            <Heart size={28} fill="var(--color-pink-400)" className="text-pink-400" /> Action Required
          </h2>
          <div className="space-y-4 relative z-10">
            {alerts.map(alert => (
              <div key={alert.id} className="flex items-center justify-between p-5 bg-pink-50 rounded-[20px] border border-pink-100 hover:bg-pink-100 transition-colors">
                <div className="flex items-center gap-4">
                  <div className={`w-3 h-3 rounded-full ${alert.type === 'SLP' ? 'bg-danger-500' : 'bg-pink-400'}`}></div>
                  <p className="text-gray-800 font-bold text-lg">{alert.message}</p>
                </div>
                <button
                  onClick={() => dismissAlert(alert.id)}
                  className="text-sm font-bold bg-white text-pink-600 hover:bg-pink-50 border border-pink-200 px-5 py-2.5 rounded-full transition-colors shadow-sm"
                >
                  Dismiss
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Child Cards Grid */}
      <div className="mb-8 flex justify-between items-end">
        <h2 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
           Patient Progress <Star size={24} fill="var(--color-warning-400)" className="text-warning-400" />
        </h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {childrenList.map(child => (
          <ChildCard key={child.id} child={child} />
        ))}
      </div>
    </div>
  );
}

function StatCard({ title, value, icon, color, iconColor }) {
  return (
    <div className={`${color} p-6 pastel-card flex flex-col justify-between`}>
      <div className="flex items-start justify-between mb-2">
        <div className={`${iconColor} p-3 rounded-[16px] shadow-sm`}>
          {icon}
        </div>
      </div>
      <div>
        <h3 className="font-bold text-lg opacity-80 mb-1 font-sans">{title}</h3>
        <p className="text-4xl font-black font-serif">{value}</p>
      </div>
    </div>
  );
}

function ChildCard({ child }) {
  const getBadge = (status) => {
    switch(status) {
      case 'on_track': return <span className="bg-success-100 text-success-600 px-4 py-1.5 rounded-full text-sm font-bold border border-success-400 shadow-sm">On Track</span>;
      case 'no_practice': return <span className="bg-alert-100 text-alert-600 px-4 py-1.5 rounded-full text-sm font-bold border border-alert-500 shadow-sm">No Practice</span>;
      case 'clinical_flag': return <span className="bg-danger-100 text-danger-500 px-4 py-1.5 rounded-full text-sm font-bold border border-danger-500 shadow-sm">Clinical Flag</span>;
      default: return null;
    }
  };

  return (
    <Link to={`/dashboard/child/${child.id}`} className="block group">
      <div className="bg-white pastel-card p-6 h-full flex flex-col justify-between overflow-hidden relative">
        <div className="absolute top-0 right-0 w-32 h-32 bg-primary-50 rounded-bl-full -mr-8 -mt-8 z-0 transition-transform group-hover:scale-110"></div>
        
        <div className="relative z-10 flex-1">
          <div className="flex justify-between items-start mb-6">
            <div className="flex justify-center items-center gap-4">
              <div className={`w-16 h-16 ${child.avatarBg} ${child.avatarText} flex items-center justify-center rounded-[20px] font-black text-2xl`}>
                {child.name[0]}
              </div>
              <div className="mt-1">
                <h3 className="text-2xl font-bold text-gray-900 font-serif leading-tight">{child.name}, {child.age}</h3>
                <p className="text-gray-500 text-sm font-bold mt-1">Target: <strong className="text-primary-600 bg-primary-50 px-2 py-0.5 rounded-md border border-primary-100">{child.target_phoneme}</strong></p>
              </div>
            </div>
          </div>
          
          <div className="mb-4">
             {getBadge(child.status)}
          </div>

          <div className="bg-gray-50 rounded-[20px] p-4 mt-6 flex justify-between items-center border border-gray-100">
            <div>
              <p className="text-xs text-gray-400 font-bold mb-1 uppercase tracking-wider">Level</p>
              <p className="text-gray-800 font-bold capitalize text-lg">{child.current_level.replace('_', ' ')}</p>
            </div>
            <div className="text-right">
              <p className="text-xs text-gray-400 font-bold mb-1 uppercase tracking-wider">Score</p>
              <p className="text-gray-800 font-bold text-lg flex items-center gap-1">
                {child.avg_score} <TrendingUp size={18} className="text-accent-500 inline" />
              </p>
            </div>
          </div>
        </div>

        <div className="relative z-10 flex justify-between items-center text-sm font-bold text-gray-400 pt-5 mt-4 border-t border-gray-100">
          <span>{child.sessions_this_week} sessions this wk</span>
          <span className="flex items-center gap-1 group-hover:text-primary-600 transition-colors bg-primary-50 text-primary-500 px-3 py-1 rounded-full">
            View <ChevronRight size={16} />
          </span>
        </div>
      </div>
    </Link>
  );
}
