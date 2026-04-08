import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Edit3, ChevronDown, ChevronRight, Activity, Wind, FileAudio, Clock, SquareActivity, Calendar as CalendarIcon, Star } from 'lucide-react';

// Using actual recharts API
import * as Recharts from 'recharts';
const LineChartComp = Recharts.LineChart || LineChart;
const LineComp = Recharts.Line || Line;
const XAxisComp = Recharts.XAxis || XAxis;
const YAxisComp = Recharts.YAxis || YAxis;
const CartesianGridComp = Recharts.CartesianGrid || CartesianGrid;
const TooltipComp = Recharts.Tooltip || Tooltip;
const LegendComp = Recharts.Legend || Legend;
const ResponsiveContainerComp = Recharts.ResponsiveContainer || ResponsiveContainer;


import { usePopi } from '../context/PopiContext';

export default function ChildProfilePage() {
  const { id } = useParams();
  const { getChildById } = usePopi();
  const child = getChildById(id);
  const [expandedSession, setExpandedSession] = useState(null);
  const [isEditingNotes, setIsEditingNotes] = useState(false);
  const [notes, setNotes] = useState(child?.slp_notes || '');

  if (!child) {
    return (
      <div className="bg-white rounded-[32px] p-10 border-2 border-gray-100">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Child Not Found</h2>
        <p className="text-gray-500 font-bold">Try refreshing the dashboard data and opening this profile again.</p>
      </div>
    );
  }

  return (
    <div className="animate-in fade-in slide-in-from-bottom-2 duration-500 pb-20">
      {/* Profile Header Card */}
      <div className="bg-primary-100 rounded-[40px] p-10 mb-12 relative overflow-hidden flex flex-col md:flex-row gap-8 items-start border-2 border-primary-200">
        <div className="absolute top-0 right-0 w-64 h-64 bg-white rounded-full mix-blend-overlay filter blur-3xl opacity-60 translate-x-10 -translate-y-10"></div>
        <div className="blob blob-yellow absolute bottom-0 left-0 w-48 h-48 opacity-40 -translate-x-10 translate-y-20"></div>
        
        <div className="shrink-0 relative z-10">
          <div className="w-32 h-32 bg-white text-primary-600 flex items-center justify-center rounded-[32px] font-black text-6xl shadow-sm border-4 border-primary-50 transform -rotate-3">
            {child.name[0]}
          </div>
        </div>

        <div className="relative z-10 flex-1">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h1 className="text-5xl font-serif font-black tracking-tight text-primary-900 mb-2">
                {child.name} <span className="text-primary-500 text-3xl font-bold font-sans ml-3">Age {child.age}</span>
              </h1>
              <p className="text-primary-700 font-bold text-lg">{child.disorder_type} · Target: <span className="bg-white text-primary-600 px-3 py-1 rounded-full border border-primary-200">{child.target_phoneme}</span></p>
            </div>
          </div>

          <div className="bg-white rounded-[24px] p-6 mb-6 border-2 border-primary-50 shadow-sm relative">
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-primary-400 text-sm uppercase tracking-wider font-bold">SLP Notes</h3>
              <button 
                className="text-primary-500 hover:text-primary-700 font-bold text-sm bg-primary-50 hover:bg-primary-100 px-3 py-1.5 rounded-full transition-colors flex items-center gap-1.5"
                onClick={() => setIsEditingNotes(!isEditingNotes)}
              >
                <Edit3 size={14} /> {isEditingNotes ? 'Done' : 'Edit'}
              </button>
            </div>
            {isEditingNotes ? (
              <textarea 
                className="w-full bg-primary-50 text-gray-800 border-2 border-primary-200 rounded-[16px] p-4 text-lg font-medium focus:outline-none focus:border-primary-400"
                rows="2"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                autoFocus
              />
            ) : (
              <p className="text-gray-800 font-bold text-lg">{notes}</p>
            )}
          </div>

          <div className="flex flex-wrap gap-4 text-sm font-bold">
            <span className="bg-white text-gray-600 px-5 py-2.5 rounded-full border border-primary-100 flex items-center gap-2">Level: <strong className="text-gray-900 capitalize text-base">{child.current_level.replace('_', ' ')}</strong></span>
            <span className="bg-white text-gray-600 px-5 py-2.5 rounded-full border border-primary-100 flex items-center gap-2">Threshold: <strong className="text-gray-900 text-base">{child.pass_threshold}</strong></span>
            <span className="bg-white text-gray-600 px-5 py-2.5 rounded-full border border-primary-100 flex items-center gap-2">Attempts/word: <strong className="text-gray-900 text-base">{child.max_attempts}</strong></span>
          </div>
        </div>
      </div>

      {/* Sub-score metrics */}
      <h2 className="text-3xl font-serif font-black text-gray-900 mb-6 flex items-center gap-3">
         Acoustic Progress <Star size={24} fill="var(--color-warning-400)" className="text-warning-400" />
      </h2>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
        <MetricCard title="Pitch Placement" value="0.74" trend="up" icon={<Activity size={24} />} color="bg-primary-50 border-primary-100 text-primary-900" iconColor="text-primary-500 bg-white" />
        <MetricCard title="Breath Quality" value="0.61" trend="flat" icon={<Wind size={24} />} color="bg-success-100 border-success-200 text-success-900" iconColor="text-success-600 bg-white" />
        <MetricCard title="Fricative Crispness" value="0.68" trend="up" icon={<FileAudio size={24} />} color="bg-warning-100 border-warning-200 text-warning-900" iconColor="text-warning-600 bg-white" />
        <MetricCard title="Duration" value="0.55" trend="down" icon={<Clock size={24} />} color="bg-pink-100 border-pink-200 text-pink-900" iconColor="text-pink-500 bg-white" />
      </div>

      {/* Graph */}
      <div className="bg-white p-8 rounded-[40px] border-2 border-gray-100 mb-12 relative overflow-hidden">
        <div className="wavy-line top-0 opacity-10 hidden sm:block"></div>
        <h3 className="text-2xl font-serif font-bold text-gray-900 mb-8 relative z-10">Score Trend <span className="text-gray-400 font-sans text-lg font-bold ml-2">(Last 7 Sessions)</span></h3>
        <div className="h-80 w-full relative z-10">
          <ResponsiveContainerComp width="100%" height="100%">
            <LineChartComp data={child.daily_scores}>
              <CartesianGridComp strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
              <XAxisComp dataKey="date" axisLine={false} tickLine={false} tick={{fill: '#94a3b8', fontWeight: 'bold'}} dy={10} />
              <YAxisComp domain={[0, 1]} axisLine={false} tickLine={false} tick={{fill: '#94a3b8', fontWeight: 'bold'}} dx={-10} />
              <TooltipComp contentStyle={{ borderRadius: '24px', border: '2px solid #f1f5f9', boxShadow: 'none', fontWeight: 'bold' }} />
              <LegendComp iconType="circle" wrapperStyle={{ paddingTop: '20px', fontWeight: 'bold', color: '#64748b' }} />
              <LineComp type="monotone" dataKey="avg" name="Overall Avg" stroke="var(--color-primary-500)" strokeWidth={5} dot={{ r: 6, strokeWidth: 3, fill: '#fff' }} activeDot={{ r: 8 }} />
              <LineComp type="monotone" dataKey="pitch" name="Pitch" stroke="var(--color-accent-400)" strokeWidth={3} dot={false} strokeDasharray="5 5" />
              <LineComp type="monotone" dataKey="breath" name="Breath" stroke="var(--color-success-500)" strokeWidth={3} dot={false} strokeDasharray="5 5" />
            </LineChartComp>
          </ResponsiveContainerComp>
        </div>
      </div>

      {/* Word Plan */}
      <div className="bg-accent-50 rounded-[40px] p-8 mb-12 flex flex-col md:flex-row justify-between items-center relative overflow-hidden border-2 border-accent-100">
        <div className="flex-1 relative z-10 w-full mb-6 md:mb-0">
          <p className="text-accent-500 text-sm font-black uppercase tracking-wider mb-4 flex items-center gap-2"><CalendarIcon size={16}/> Week of Mon Apr 07</p>
          <div className="flex flex-wrap gap-3">
            {child.plan.map((w, i) => (
              <span key={i} className="bg-white text-gray-800 px-5 py-2 rounded-full font-bold border border-accent-100 shadow-sm text-lg">{w}</span>
            ))}
          </div>
        </div>
        <Link to={`/dashboard/plan/${child.id}`} className="bg-white border-2 border-accent-200 text-accent-500 hover:bg-accent-500 hover:text-white hover:border-accent-500 px-8 py-4 rounded-full font-bold shadow-sm transition-all text-lg shrink-0 relative z-10 flex items-center gap-2">
          Edit Plan <ChevronRight size={20} />
        </Link>
      </div>

      {/* Session History */}
      <h2 className="text-3xl font-serif font-black text-gray-900 mb-6 flex items-center gap-3">
        Session History <Star size={24} fill="var(--color-success-400)" className="text-success-400" />
      </h2>
      <div className="space-y-4">
        {child.sessions.map((session) => (
          <div key={session.id} className="bg-white border-2 border-gray-100/60 shadow-sm rounded-[32px] overflow-hidden transition-all duration-300">
            <div 
              className="p-6 md:p-8 flex justify-between items-center cursor-pointer hover:bg-gray-50 transition-colors"
              onClick={() => setExpandedSession(expandedSession === session.id ? null : session.id)}
            >
              <div className="flex items-center gap-6">
                <div className="bg-primary-50 p-4 rounded-[20px] text-primary-500">
                  <SquareActivity size={28} />
                </div>
                <div>
                  <h4 className="font-bold text-gray-900 text-2xl font-serif mb-1">{session.date}</h4>
                  <p className="text-base font-bold text-gray-500">{session.attempts} attempts · Reached <span className="text-primary-600 bg-primary-50 px-2 rounded">{session.level_reached}</span></p>
                </div>
              </div>
              <div className="flex items-center gap-8">
                <div className="text-right hidden sm:block">
                  <p className="text-xs text-gray-400 font-bold uppercase tracking-widest mb-1">Avg Score</p>
                  <p className="text-3xl font-black text-gray-800 font-serif">{session.avg_score}</p>
                </div>
                <button className={`w-12 h-12 flex items-center justify-center rounded-full transition-colors ${expandedSession === session.id ? 'bg-primary-100 text-primary-600' : 'bg-gray-50 text-gray-400 border border-gray-200'}`}>
                  {expandedSession === session.id ? <ChevronDown size={24} /> : <ChevronRight size={24} />}
                </button>
              </div>
            </div>
            
            {expandedSession === session.id && (
              <div className="bg-gray-50/50 p-6 pt-0 border-t-2 border-gray-100/50">
                <div className="space-y-3 mt-6">
                  {child.attempts.map(att => (
                    <div key={att.id} className="flex flex-col sm:flex-row sm:items-center justify-between p-4 bg-white rounded-[20px] shadow-sm border border-gray-100 gap-4">
                      <div className="flex items-center gap-4 sm:w-1/3">
                        <span className="text-sm font-black text-gray-400 w-6">#{att.id}</span>
                        <span className="font-bold text-gray-800 text-lg bg-gray-50 px-4 py-1.5 rounded-xl border border-gray-100">{att.word}</span>
                      </div>
                      <div className="sm:w-1/6">
                        <span className={`font-black px-3 py-1.5 rounded-full text-sm border ${att.score >= 0.7 ? 'bg-success-50 text-success-600 border-success-200' : att.score >= 0.45 ? 'bg-alert-50 text-alert-600 border-alert-200' : 'bg-danger-50 text-danger-600 border-danger-200'}`}>
                          {att.score.toFixed(2)}
                        </span>
                      </div>
                      <div className="sm:w-1/2 sm:text-right">
                        <span className="text-sm font-bold text-gray-500 bg-gray-50 px-3 py-2 rounded-xl inline-block border border-gray-100">{att.feedback}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function MetricCard({ title, value, trend, icon, color, iconColor }) {
  return (
    <div className={`${color} border-2 p-6 rounded-[32px] pastel-card flex flex-col justify-between relative`}>
      <div className="flex items-start justify-between mb-4 relative z-10">
        <div className={`${iconColor} p-3 rounded-[16px] shadow-sm`}>
          {icon}
        </div>
      </div>
      <div className="relative z-10">
        <h4 className="text-base font-bold opacity-80 mb-1">{title}</h4>
        <div className="flex items-end gap-3">
          <span className="text-4xl font-black font-serif">{value}</span>
          {trend === 'up' && <span className="bg-white/50 text-current px-2 py-0.5 rounded-md text-xs font-black mb-2 shadow-sm border border-current/10">↑</span>}
          {trend === 'down' && <span className="bg-white/50 text-current px-2 py-0.5 rounded-md text-xs font-black mb-2 shadow-sm border border-current/10">↓ W</span>}
          {trend === 'flat' && <span className="bg-white/50 text-current px-2 py-0.5 rounded-md text-xs font-black mb-2 shadow-sm border border-current/10">→</span>}
        </div>
      </div>
    </div>
  );
}
