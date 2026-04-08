import React, { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Settings, Save, Send, Trash2, X, GripVertical, CheckCircle, Plus } from 'lucide-react';
import { usePopi } from '../context/PopiContext';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export default function WeekPlannerPage() {
  const { id } = useParams();
  const { getChildById, pushPlan } = usePopi();
  const child = getChildById(id);
  const [wordBank, setWordBank] = useState([]);
  const [plan, setPlan] = useState([]);
  const [threshold, setThreshold] = useState(0.70);
  const [maxAttempts, setMaxAttempts] = useState(5);
  const [startLevel] = useState('word_init');
  const [toast, setToast] = useState(false);
  const [isPushing, setIsPushing] = useState(false);

  useEffect(() => {
    const loadWordBank = async () => {
      const res = await fetch(`${API_BASE}/word-bank`);
      const payload = await res.json();
      const bank = payload.word_bank || {};
      const flattened = Object.entries(bank).flatMap(([level, rows], idx) =>
        (rows || []).map((entry, i) => ({
          id: `${level}-${idx}-${i}`,
          word: typeof entry === 'string' ? entry : entry.word,
          position: level.includes('final') ? 'final' : 'initial',
          level,
        })),
      );
      setWordBank(flattened);
    };
    loadWordBank();
  }, []);

  useEffect(() => {
    if (!child?.plan?.length || !wordBank.length) return;
    const preselected = child.plan
      .map((w) => wordBank.find((x) => x.word === w))
      .filter(Boolean);
    if (preselected.length) setPlan(preselected);
  }, [child, wordBank]);

  const initialWords = useMemo(
    () => wordBank.filter((w) => w.position === 'initial'),
    [wordBank],
  );
  const finalWords = useMemo(
    () => wordBank.filter((w) => w.position === 'final'),
    [wordBank],
  );

  const addToPlan = (word) => {
    if (!plan.find(w => w.id === word.id)) setPlan([...plan, word]);
  };
  const removeFromPlan = (id) => setPlan(plan.filter(w => w.id !== id));

  const syncPlan = async () => {
    if (!id || plan.length === 0) return;
    setIsPushing(true);
    await pushPlan({
      childId: id,
      words: plan,
      passThreshold: threshold,
      maxAttempts,
      startLevel,
    });
    setToast(true);
    setTimeout(() => setToast(false), 3000);
    setIsPushing(false);
  };

  return (
    <div className="animate-in fade-in slide-in-from-bottom-2 duration-500 pb-20">
      <header className="mb-10 pt-4 flex flex-col md:flex-row justify-between md:items-end gap-6 relative">
      <div className="wavy-line top-0 opacity-30 z-0" style={{ width: '300px', left: '10%'}}></div>
        <div className="relative z-10">
          <h1 className="text-5xl font-black font-serif text-gray-900 mb-2">
            <span className="heading-flair">Week Planner</span>
          </h1>
          <p className="text-gray-500 font-bold mt-4 text-lg">Prescribe target words for this week's practice.</p>
        </div>
        <div className="bg-white px-6 py-3 rounded-full shadow-sm border-2 border-primary-100 font-bold text-gray-700 relative z-10 flex items-center gap-2">
          Start level: <span className="bg-primary-50 text-primary-600 px-3 py-1 rounded-full">{startLevel.replace('_', ' ')}</span>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
        {/* Word Bank Panel */}
        <div className="bg-primary-50 rounded-[40px] p-8 md:p-10 border-2 border-primary-200 relative flex flex-col h-[750px]">
          <div className="blob blob-blue absolute top-0 right-0 w-32 h-32 opacity-10"></div>
          <h2 className="text-3xl font-serif font-black mb-6 text-primary-900 relative z-10">Word Bank</h2>
          
          <div className="relative z-10 mb-8 flex gap-3">
            <span className="bg-white text-primary-700 px-5 py-2 rounded-full text-sm font-bold border border-primary-200 shadow-sm cursor-pointer hover:bg-primary-100 transition-colors">Filter: initial position</span>
            <span className="bg-white text-primary-700 px-5 py-2 rounded-full text-sm font-bold border border-primary-200 shadow-sm cursor-pointer hover:bg-primary-100 transition-colors">/s/ phoneme</span>
          </div>

          <div className="relative z-10 flex-1 overflow-auto pr-4 custom-scrollbar">
            <div className="mb-8">
              <h3 className="text-xs font-black text-primary-400 tracking-widest uppercase mb-5">Initial Position</h3>
              <div className="flex flex-wrap gap-4">
                {initialWords.map(word => {
                  const isAdded = plan.some(p => p.id === word.id);
                  return (
                    <button 
                      key={word.id} disabled={isAdded} onClick={() => addToPlan(word)}
                      className={`text-lg font-bold py-3 px-6 rounded-full border-2 transition-all flex items-center gap-2
                        ${isAdded ? 'bg-primary-100 border-primary-200 text-primary-400 cursor-not-allowed opacity-50' : 'bg-white border-primary-200 text-primary-700 hover:bg-primary-500 hover:border-primary-500 hover:text-white shadow-sm hover:shadow-md hover:-translate-y-1'}`}
                    >
                      {word.word} {isAdded ? <CheckCircle size={18} /> : <Plus size={18} />}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <h3 className="text-xs font-black text-primary-400 tracking-widest uppercase mb-5">Final Position</h3>
              <div className="flex flex-wrap gap-4">
                {finalWords.map(word => {
                  const isAdded = plan.some(p => p.id === word.id);
                  return (
                    <button 
                      key={word.id} disabled={isAdded} onClick={() => addToPlan(word)}
                      className={`text-lg font-bold py-3 px-6 rounded-full border-2 transition-all flex items-center gap-2
                        ${isAdded ? 'bg-primary-100 border-primary-200 text-primary-400 cursor-not-allowed opacity-50' : 'bg-white border-primary-200 text-primary-700 hover:bg-primary-500 hover:border-primary-500 hover:text-white shadow-sm hover:shadow-md hover:-translate-y-1'}`}
                    >
                      {word.word} {isAdded ? <CheckCircle size={18} /> : <Plus size={18} />}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* Selected Plan Panel */}
        <div className="bg-white rounded-[40px] p-8 md:p-10 border-2 border-gray-100 shadow-sm flex flex-col h-[750px] relative">
          <h2 className="text-3xl font-serif font-black mb-8 text-gray-900 pb-6 border-b-2 border-gray-50 flex justify-between items-center">
            This Week's Plan <span className="text-base font-sans font-bold bg-gray-100 text-gray-500 px-4 py-1.5 rounded-full">{plan.length} words</span>
          </h2>

          <div className="flex-1 overflow-auto pr-4 custom-scrollbar space-y-4 mb-8">
            {plan.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-gray-400">
                <div className="bg-gray-50 p-8 rounded-full inline-block border-2 border-dashed border-gray-200 mb-6">
                  <Save size={48} className="opacity-40" />
                </div>
                <p className="font-bold text-xl text-gray-500 mb-2">No words selected</p>
                <p className="text-base">Tap words from the bank to add them here.</p>
              </div>
            ) : (
              plan.map((word, index) => (
                <div key={word.id} className="group bg-white border-2 border-gray-100 hover:border-accent-200 p-5 rounded-[24px] flex items-center justify-between transition-all shadow-sm hover:shadow-md">
                  <div className="flex items-center gap-5">
                    <div className="cursor-grab active:cursor-grabbing hover:bg-gray-50 p-2 rounded-lg transition-colors">
                      <GripVertical size={24} className="text-gray-300 group-hover:text-accent-400" />
                    </div>
                    <div>
                      <span className="font-black font-serif text-2xl text-gray-800 mr-4">{word.word}</span>
                      <span className="text-sm font-bold text-gray-500 bg-gray-50 px-3 py-1 rounded-md border border-gray-100">{word.position}</span>
                    </div>
                  </div>
                  <button 
                    onClick={() => removeFromPlan(word.id)}
                    className="text-gray-300 hover:text-danger-500 hover:bg-danger-50 p-3 rounded-xl transition-colors sm:opacity-0 group-hover:opacity-100 border border-transparent hover:border-danger-100"
                  >
                    <X size={24} />
                  </button>
                </div>
              ))
            )}
          </div>

          <div className="bg-gray-50 p-8 rounded-[32px] border-2 border-gray-100 mb-8 mt-auto">
            <h3 className="text-sm font-black uppercase tracking-widest text-gray-500 mb-6 flex items-center gap-3">
              <Settings size={18} /> Device Settings
            </h3>
            <div className="grid grid-cols-2 gap-10">
              <div>
                <label className="flex justify-between text-base font-bold text-gray-700 mb-4">
                  Pass Threshold <span className="text-primary-600 bg-white px-2 rounded border border-gray-200 shadow-sm">{threshold.toFixed(2)}</span>
                </label>
                <input 
                  type="range" min="0.45" max="0.90" step="0.05" 
                  value={threshold} 
                  onChange={(e) => setThreshold(parseFloat(e.target.value))}
                  className="w-full accent-primary-500 bg-gray-200 rounded-full h-3 appearance-none cursor-pointer" 
                />
              </div>
              <div>
                <label className="flex justify-between text-base font-bold text-gray-700 mb-4">
                  Max Attempts <span className="text-accent-500 bg-white px-2 rounded border border-gray-200 shadow-sm">{maxAttempts}</span>
                </label>
                <input 
                  type="range" min="3" max="8" step="1" 
                  value={maxAttempts} 
                  onChange={(e) => setMaxAttempts(parseInt(e.target.value))}
                  className="w-full accent-accent-500 bg-gray-200 rounded-full h-3 appearance-none cursor-pointer" 
                />
              </div>
            </div>
          </div>

          <button 
            onClick={syncPlan}
            disabled={plan.length === 0}
            className={`w-full py-5 rounded-[24px] font-black text-xl transition-all flex justify-center items-center gap-3 border-2 ${plan.length === 0 ? 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed' : 'bg-primary-500 border-primary-600 hover:bg-primary-600 text-white shadow-lg hover:shadow-xl hover:-translate-y-1'}`}
          >
            <Send size={24} /> {isPushing ? 'Pushing...' : 'Push to Device'}
          </button>
        </div>
      </div>

      {toast && (
        <div className="fixed bottom-10 right-10 bg-gray-900 border-2 border-gray-700 text-white px-8 py-5 rounded-[24px] shadow-2xl animate-in slide-in-from-right-10 flex items-center gap-4 z-50">
          <CheckCircle className="text-success-400" size={28} />
          <p className="font-bold text-lg">Synced! Device target list updated.</p>
        </div>
      )}
    </div>
  );
}
