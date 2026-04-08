import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePopi } from '../context/PopiContext';
import { Stethoscope, Lock, Mail, ArrowRight } from 'lucide-react';

export default function LoginPage() {
  const { login } = usePopi();
  const navigate = useNavigate();
  const [name, setName] = useState('Mia');
  const [username, setUsername] = useState('Mia@2000');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError('');
    try {
      await login({ name, username, password });
      navigate('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-cream flex items-center justify-center p-6 relative overflow-hidden">
      
      {/* Background blobs */}
      <div className="blob blob-purple absolute top-10 left-10 w-96 h-96 opacity-30 z-0"></div>
      <div className="blob blob-yellow absolute bottom-[-100px] right-10 w-80 h-80 opacity-40 z-0"></div>

      <div className="w-full max-w-md relative z-10 animate-in zoom-in-95 duration-500">
        
        <div className="text-center mb-8">
          <div className="w-20 h-20 bg-white border-2 border-primary-100 rounded-[24px] flex items-center justify-center shadow-sm mx-auto mb-6 transform rotate-3">
             <span className="font-serif font-black text-primary-500 text-6xl leading-none">P</span>
          </div>
          <h1 className="text-4xl font-black font-serif text-gray-900">Therapist Portal</h1>
          <p className="text-gray-500 font-bold mt-2">Manage your patients and insights.</p>
        </div>

        <form onSubmit={handleLogin} className="bg-white p-8 md:p-10 rounded-[40px] border-2 border-gray-100 shadow-xl space-y-6">
          
          <div>
            <label className="block text-xs font-black text-gray-400 tracking-widest uppercase mb-2">Provider Name</label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                <Stethoscope className="text-gray-400" size={20} />
              </div>
              <input 
                type="text" required
                value={name} onChange={(e) => setName(e.target.value)}
                className="w-full bg-gray-50 border-2 border-gray-100 rounded-[20px] pl-12 pr-5 py-4 font-bold text-gray-800 focus:outline-none focus:border-primary-400 transition-colors"
                placeholder="Dr. Smith"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-black text-gray-400 tracking-widest uppercase mb-2">Username</label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                <Mail className="text-gray-400" size={20} />
              </div>
              <input 
                type="text" required
                value={username} onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-gray-50 border-2 border-gray-100 rounded-[20px] pl-12 pr-5 py-4 font-bold text-gray-800 focus:outline-none focus:border-primary-400 transition-colors"
                placeholder="Therapist Username"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-black text-gray-400 tracking-widest uppercase mb-2">Password</label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                <Lock className="text-gray-400" size={20} />
              </div>
              <input 
                type="password" required
                value={password} onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-gray-50 border-2 border-gray-100 rounded-[20px] pl-12 pr-5 py-4 font-bold text-gray-800 focus:outline-none focus:border-primary-400 transition-colors"
                placeholder="••••••••"
              />
            </div>
          </div>

           {error && (
            <p className="text-danger-500 text-sm font-bold">{error}</p>
           )}

           <button type="submit" disabled={isSubmitting} className="w-full bg-primary-500 hover:bg-primary-600 disabled:bg-primary-300 text-white font-black text-lg py-4 rounded-[20px] shadow-md hover:-translate-y-1 transition-all flex items-center justify-center gap-2 mt-4">
             {isSubmitting ? 'Loading...' : 'Log In Securely'} <ArrowRight size={20} />
          </button>
        </form>
        
      </div>
    </div>
  );
}
