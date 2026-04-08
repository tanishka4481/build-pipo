import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { UserPlus, Sparkles, CheckCircle2 } from 'lucide-react';
import { usePopi } from '../context/PopiContext';

export default function AddChildPage() {
  const navigate = useNavigate();
  const { addChild } = usePopi();
  const [formData, setFormData] = useState({
    name: '',
    age: '',
    disorder_type: 'Articulation disorder',
    target_phoneme: '/s/',
    slp_notes: ''
  });
  const [toast, setToast] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError('');
    try {
      const newId = await addChild(formData);
      setToast(true);
      setTimeout(() => {
        setToast(false);
        navigate(`/dashboard/plan/${newId}`);
      }, 1200);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create child');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (e) => setFormData({...formData, [e.target.name]: e.target.value});

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 pb-20 max-w-3xl mx-auto">
      <header className="mb-10 pt-8 text-center relative">
        <div className="blob blob-purple absolute top-0 right-10 w-32 h-32 opacity-20 bg-primary-300"></div>
        <div className="bg-primary-50 p-6 rounded-full inline-block mb-4 text-primary-500">
           <UserPlus size={48} />
        </div>
        <h1 className="text-5xl font-black font-serif text-gray-900 mb-2">New Patient Profile</h1>
        <p className="text-gray-500 font-bold text-lg">Onboard a new child to start generating acoustic models.</p>
      </header>

      <div className="bg-white rounded-[40px] p-10 border-2 border-primary-100 shadow-sm relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-primary-50 rounded-bl-full -mr-10 -mt-10 z-0"></div>
        <form onSubmit={handleSubmit} className="relative z-10 space-y-6">
          <div className="grid grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-black text-primary-400 tracking-widest uppercase mb-2">Child's Name</label>
              <input 
                autoFocus required type="text" name="name" value={formData.name} onChange={handleChange}
                className="w-full bg-gray-50 border-2 border-gray-100 rounded-2xl px-5 py-3 font-bold text-gray-800 focus:outline-none focus:border-primary-400 transition-colors"
                placeholder="e.g. Maya"
              />
            </div>
            <div>
              <label className="block text-sm font-black text-primary-400 tracking-widest uppercase mb-2">Age</label>
              <input 
                required type="number" min="3" max="10" name="age" value={formData.age} onChange={handleChange}
                className="w-full bg-gray-50 border-2 border-gray-100 rounded-2xl px-5 py-3 font-bold text-gray-800 focus:outline-none focus:border-primary-400 transition-colors"
                placeholder="Years old"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-black text-primary-400 tracking-widest uppercase mb-2">Primary Diagnosis</label>
              <select 
                name="disorder_type" value={formData.disorder_type} onChange={handleChange}
                className="w-full bg-gray-50 border-2 border-gray-100 rounded-2xl px-5 py-3 font-bold text-gray-800 focus:outline-none focus:border-primary-400 transition-colors appearance-none cursor-pointer"
              >
                <option value="Articulation disorder">Articulation disorder</option>
                <option value="Phonological disorder">Phonological disorder</option>
                <option value="Childhood Apraxia">Childhood Apraxia of Speech</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-black text-primary-400 tracking-widest uppercase mb-2">Target Phoneme</label>
              <select 
                name="target_phoneme" value={formData.target_phoneme} onChange={handleChange}
                className="w-full bg-gray-50 border-2 border-gray-100 rounded-2xl px-5 py-3 font-bold text-gray-800 focus:outline-none focus:border-primary-400 transition-colors appearance-none cursor-pointer"
              >
                <option value="/s/">/s/ (sibilant fricative)</option>
                <option value="/r/">/r/ (liquid)</option>
                <option value="/l/">/l/ (lateral liquid)</option>
                <option value="/sh/">/sh/ (palatal fricative)</option>
              </select>
            </div>
          </div>

          <div>
             <label className="block text-sm font-black text-primary-400 tracking-widest uppercase mb-2">Initial Clinical Notes</label>
             <textarea 
               name="slp_notes" rows="4" value={formData.slp_notes} onChange={handleChange}
               className="w-full bg-gray-50 border-2 border-gray-100 rounded-[20px] px-5 py-4 font-medium text-gray-800 focus:outline-none focus:border-primary-400 transition-colors"
               placeholder="Enter observed substitutions, compliance, or session notes here..."
             ></textarea>
          </div>

          <div className="pt-4 flex justify-end gap-4 border-t-2 border-gray-50 mt-8">
            {error && <p className="text-danger-500 font-bold mr-auto self-center">{error}</p>}
            <button type="button" onClick={() => navigate(-1)} className="px-8 py-4 rounded-full font-bold text-gray-500 hover:bg-gray-50 transition-colors border-2 border-transparent">
              Cancel
            </button>
            <button type="submit" disabled={isSubmitting} className="px-8 py-4 rounded-full font-bold text-white bg-primary-500 hover:bg-primary-600 disabled:bg-primary-300 shadow-md hover:-translate-y-1 transition-all border-2 border-primary-600 flex items-center gap-2">
              <Sparkles size={20} /> {isSubmitting ? 'Creating...' : 'Create Profile'}
            </button>
          </div>
        </form>
      </div>

      {toast && (
        <div className="fixed bottom-10 right-10 bg-gray-900 border-2 border-gray-700 text-white px-8 py-5 rounded-[24px] shadow-2xl animate-in slide-in-from-right-10 flex items-center gap-4 z-50">
          <CheckCircle2 className="text-success-400" size={28} />
          <p className="font-bold text-lg">Profile Created! Routing to Week Planner...</p>
        </div>
      )}
    </div>
  );
}
