import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Volume2, Shield, Calendar, Mic, Sparkles, Stethoscope, ChevronRight, CheckCircle2, SquareActivity } from 'lucide-react';

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-cream font-sans overflow-x-hidden">
      
      {/* Decorative Background Elements */}
      <div className="blob blob-yellow absolute top-[-5%] right-[-5%] w-[500px] h-[500px] opacity-40 mix-blend-multiply z-0"></div>
      <div className="blob blob-blue absolute top-[60vh] left-[-15%] w-[600px] h-[600px] opacity-30 mix-blend-multiply z-0"></div>
      <div className="blob blob-purple absolute top-[180vh] right-[10%] w-[400px] h-[400px] opacity-20 mix-blend-multiply z-0"></div>

      {/* Navigation */}
      <nav className="container mx-auto px-6 py-8 flex justify-between items-center relative z-20">
        <div className="flex items-center gap-4">
          <div className="bg-primary-500 rounded-[12px] px-4 py-2 shadow-sm transform -rotate-2">
            <span className="font-sans font-black text-white text-3xl tracking-[0.1em] leading-none">POPI</span>
          </div>
        </div>
        <div className="flex items-center gap-6">
           <a href="#how-it-works" className="hidden md:block font-bold text-gray-500 hover:text-gray-900 transition-colors">How it Works</a>
           <a href="#features" className="hidden md:block font-bold text-gray-500 hover:text-gray-900 transition-colors">Features</a>
           <Link to="/login" className="bg-white hover:bg-primary-50 text-primary-600 border-2 border-primary-200 px-6 py-3 rounded-full font-bold transition-all shadow-sm flex items-center gap-2">
            <Stethoscope size={18} /> Therapist Login
           </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <header className="container mx-auto px-6 mt-12 md:mt-20 pb-24 relative z-20">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          <div className="animate-in slide-in-from-left duration-700">
            <div className="bg-white text-primary-600 px-5 py-2.5 rounded-full inline-block font-black text-sm uppercase tracking-widest mb-8 border-2 border-primary-100 shadow-sm shadow-primary-100/50">
               Childhood Speech Companion
            </div>
            <h1 className="font-serif font-black text-6xl md:text-7xl lg:text-[5.5rem] text-gray-900 leading-[1.05] mb-8">
              Therapy <br /> doesn't have to feel like <span className="text-transparent bg-clip-text bg-gradient-to-r from-pink-400 to-accent-400 relative">work.<Sparkles className="absolute -top-6 -right-8 text-yellow-400" size={32} /></span>
            </h1>
            <p className="text-gray-600 text-xl md:text-2xl font-bold mb-10 leading-relaxed max-w-lg">
              Meet POPI. The intelligent, screen-free companion that bridges the gap between weekly SLP sessions while tracking acoustic progress automatically.
            </p>
            <div className="flex flex-col sm:flex-row gap-4">
              <a href="#how-it-works" className="bg-primary-500 hover:bg-primary-600 text-white px-8 py-5 rounded-full font-black text-lg shadow-xl shadow-primary-500/20 hover:-translate-y-1 transition-all flex items-center justify-center gap-3">
                See How It Works <ArrowRight size={22} />
              </a>
            </div>
            
            <div className="mt-12 flex items-center gap-6 text-sm font-bold text-gray-400">
               <span className="flex items-center gap-2"><CheckCircle2 className="text-success-400" size={20} /> Zero Screen Time</span>
               <span className="flex items-center gap-2"><CheckCircle2 className="text-success-400" size={20} /> Clinician Linked</span>
            </div>
          </div>

          {/* Toy Image Showcase */}
          <div className="relative animate-in slide-in-from-right duration-700 delay-100">
             <div className="relative rounded-[64px] bg-white border-4 border-white shadow-2xl p-2 z-10 overflow-hidden transform rotate-2 hover:rotate-0 transition-transform duration-500">
                <div className="absolute inset-0 bg-gradient-to-tr from-accent-200 to-pink-100 opacity-20"></div>
                <img 
                   src="/popi-toy.jpg" 
                   alt="POPI Smart Companion Toy" 
                   className="w-full object-cover rounded-[56px] relative z-10 aspect-[4/5] md:aspect-square"
                />
             </div>
             
             {/* Floating Spec Cards */}
             <div className="hidden md:flex absolute -bottom-8 -left-12 bg-white px-8 py-5 rounded-[32px] border-2 border-gray-100 shadow-xl z-20 items-center gap-4">
                <div className="bg-warning-100 text-warning-500 p-4 rounded-[20px]">
                   <Mic size={28} />
                </div>
                <div>
                   <p className="text-xs font-black text-gray-400 uppercase tracking-widest leading-none mb-1">Listens &</p>
                   <p className="font-black font-serif text-2xl text-gray-900 leading-none">Analyzes</p>
                </div>
             </div>
          </div>
        </div>
      </header>

      {/* The Problem Section */}
      <section className="bg-white py-24 md:py-32 relative z-10 border-y-2 border-gray-100" id="how-it-works">
         <div className="container mx-auto px-6">
            <div className="max-w-4xl mx-auto text-center mb-20">
               <h2 className="font-serif font-black text-4xl md:text-5xl text-gray-900 mb-6">The "6-Day Gap" Problem</h2>
               <p className="text-xl font-bold text-gray-500 leading-relaxed">
                  Most children see their Speech-Language Pathologist once a week for 45 minutes. The challenge isn't the session—it's maintaining deliberate practice during the 6 days at home.
               </p>
            </div>

            {/* Zig Zag Flow */}
            <div className="space-y-12 md:space-y-0 relative">
               {/* Connecting Line (Desktop) */}
               <div className="hidden md:block absolute left-1/2 top-10 bottom-10 w-2 bg-gray-50 -translate-x-1/2 z-0 rounded-full"></div>

               <div className="flex flex-col md:flex-row items-center gap-12 relative z-10 md:-translate-y-8">
                  <div className="flex-1 md:text-right md:pr-12">
                     <div className="bg-primary-50 text-primary-500 p-5 rounded-[24px] inline-block mb-4 shadow-sm border-2 border-primary-100">
                        <Calendar size={32} />
                     </div>
                     <h3 className="font-serif font-black text-3xl text-gray-900 mb-3">1. The SLP Prescribes</h3>
                     <p className="font-bold text-gray-500 text-lg">Using the clinical dashboard, the therapist pushes a targeted word list (e.g., initial /s/ words) and sets custom acoustic thresholds tailored to the child's treatment plan.</p>
                  </div>
                  <div className="hidden md:flex w-16 h-16 bg-white border-4 border-primary-100 rounded-full items-center justify-center font-black text-primary-400 shrink-0 z-10 text-xl shadow-sm">1</div>
                  <div className="flex-1 hidden md:block"></div>
               </div>

               <div className="flex flex-col md:flex-row items-center gap-12 relative z-10 md:-translate-y-4">
                  <div className="flex-1 hidden md:block"></div>
                  <div className="hidden md:flex w-16 h-16 bg-white border-4 border-accent-100 rounded-full items-center justify-center font-black text-accent-400 shrink-0 z-10 text-xl shadow-sm">2</div>
                  <div className="flex-1 md:pl-12">
                     <div className="bg-accent-50 text-accent-500 p-5 rounded-[24px] inline-block mb-4 shadow-sm border-2 border-accent-100">
                        <Volume2 size={32} />
                     </div>
                     <h3 className="font-serif font-black text-3xl text-gray-900 mb-3">2. Passive Proximity Wake</h3>
                     <p className="font-bold text-gray-500 text-lg">POPI sits beautifully on a shelf. When the child plays near it, a proximity sensor triggers a brief, 90-second micro-interaction. "Hey Maya! Can you teach me how to say 'sun'?"</p>
                  </div>
               </div>

               <div className="flex flex-col md:flex-row items-center gap-12 relative z-10">
                  <div className="flex-1 md:text-right md:pr-12">
                     <div className="bg-pink-50 text-pink-500 p-5 rounded-[24px] inline-block mb-4 shadow-sm border-2 border-pink-100">
                        <SquareActivity size={32} />
                     </div>
                     <h3 className="font-serif font-black text-3xl text-gray-900 mb-3">3. Cloud Scoring</h3>
                     <p className="font-bold text-gray-500 text-lg">The child replies. POPI's onboard edge AI processes the audio, gives real-time visual encouragement, and securely syncs the exact spectral metrics back to the therapist's portal.</p>
                  </div>
                  <div className="hidden md:flex w-16 h-16 bg-white border-4 border-pink-100 rounded-full items-center justify-center font-black text-pink-400 shrink-0 z-10 text-xl shadow-sm">3</div>
                  <div className="flex-1 hidden md:block"></div>
               </div>
            </div>
         </div>
      </section>

      {/* Features / USPs */}
      <section className="py-24 md:py-32 relative z-20" id="features">
         <div className="container mx-auto px-6">
            <h2 className="font-serif font-black text-4xl md:text-5xl text-center text-gray-900 mb-4">Why Clinics Love POPI</h2>
            <p className="text-xl font-bold text-gray-500 text-center mb-16 max-w-2xl mx-auto">Designed using organic shapes and soft technology, making it feel like a friend, not a medical device.</p>

            <div className="grid md:grid-cols-3 gap-8">
               <FeatureCard 
                  color="bg-primary-50" border="border-primary-100" iconColor="text-primary-500" iconBg="bg-white"
                  title="Zero Screen Time"
                  desc="Unlike iPad apps, POPI keeps children anchored in the physical world, reducing overstimulation while engaging them in vocal play."
                  icon={<Shield size={28} />}
               />
               <FeatureCard 
                  color="bg-accent-50" border="border-accent-100" iconColor="text-accent-500" iconBg="bg-white"
                  title="Acoustic Data Analytics"
                  desc="Tracks fricative crispness, pitch trajectory, and voice duration, plotting exact measurements so SLPs don't have to rely on parent memory."
                  icon={<Mic size={28} />}
               />
               <FeatureCard 
                  color="bg-warning-50" border="border-warning-100" iconColor="text-warning-500" iconBg="bg-white"
                  title="Multi-Tenant Dashboard"
                  desc="A clinical interface allowing SLPs to manage their entire roster, triage parent alerts, and push distinct word banks to dozens of POPIs instantly."
                  icon={<Stethoscope size={28} />}
               />
            </div>
         </div>
      </section>

      {/* Footer / CTA Section */}
      <section className="bg-gray-900 py-24 relative overflow-hidden text-center rounded-t-[64px] border-t-8 border-primary-500">
         <div className="absolute inset-0 bg-gradient-to-b from-primary-900/20 to-transparent"></div>
         <div className="container mx-auto px-6 relative z-10">
            <h2 className="font-serif font-black text-4xl md:text-[3.5rem] text-white mb-6">Ready to empower your practice?</h2>
            <p className="text-xl font-bold text-gray-400 mb-10 max-w-2xl mx-auto">Join the waitlist for clinical trials, or log in to access your existing patient rosters and configure POPI devices.</p>
            
            <div className="flex flex-col sm:flex-row justify-center gap-4">
               <Link to="/login" className="bg-primary-500 hover:bg-primary-400 text-white border-2 border-primary-400 px-10 py-5 rounded-full font-black text-xl transition-all hover:scale-105 flex justify-center items-center gap-3">
                  Open Therapist Portal <ChevronRight size={24} />
               </Link>
            </div>
         </div>
      </section>

    </div>
  );
}

function FeatureCard({ title, desc, icon, color, border, iconColor, iconBg }) {
   return (
      <div className={`p-8 md:p-10 rounded-[40px] border-2 ${color} ${border} transition-transform duration-300 hover:-translate-y-2`}>
         <div className={`w-16 h-16 rounded-[24px] shadow-sm flex items-center justify-center mb-6 ${iconBg} ${iconColor} border ${border}`}>
            {icon}
         </div>
         <h4 className="font-serif font-black text-2xl text-gray-900 mb-4">{title}</h4>
         <p className="font-bold text-gray-600 text-lg leading-relaxed">{desc}</p>
      </div>
   );
}
