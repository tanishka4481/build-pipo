import React from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink, Link, Navigate, Outlet } from 'react-router-dom';
import { Home, User, Bell, PlusCircle, Star } from 'lucide-react';

import { PopiProvider, usePopi } from './context/PopiContext';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import HomePage from './pages/HomePage';
import ChildProfilePage from './pages/ChildProfilePage';
import WeekPlannerPage from './pages/WeekPlannerPage';
import AlertsPage from './pages/AlertsPage';
import AddChildPage from './pages/AddChildPage';

// Protected Route Wrapper
const ProtectedRoute = ({ children }) => {
  const { isAuthenticated } = usePopi();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return children ? children : <Outlet />;
};

// Internal Clinical Dashboard Layout
const DashboardLayout = () => {
  return (
    <div className="flex h-screen bg-cream font-sans overflow-hidden">
      {/* Sidebar Layout */}
      <nav className="w-72 bg-white m-6 rounded-[40px] flex flex-col p-8 border-2 border-primary-50 shadow-sm relative z-20">
        <div className="flex items-center gap-3 mb-10">
          <span className="text-3xl">Ⓜ️</span>
          <span className="font-sans font-black text-primary-900 text-2xl tracking-tight">Mia</span>
        </div>

        <div className="flex flex-col gap-4 flex-1">
          <NavLink end to="/dashboard" className={({isActive}) => `flex items-center gap-4 p-4 rounded-[24px] font-bold transition-all duration-300 ${isActive ? 'bg-primary-100 text-primary-900' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-900'}`}>
            <Home size={22} /> Overview
          </NavLink>
          {/* We'll use a placeholder for "My Kids" since it's just routing to the homepage conceptually */}
          <NavLink to="/dashboard" className={({isActive}) => `flex items-center gap-4 p-4 rounded-[24px] font-bold transition-all duration-300 text-gray-500 hover:bg-gray-50 hover:text-gray-900`}>
            <User size={22} /> My Kids
          </NavLink>
          <NavLink to="/dashboard/alerts" className={({isActive}) => `flex items-center gap-4 p-4 rounded-[24px] font-bold transition-all duration-300 ${isActive ? 'bg-pink-100 text-pink-700' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-900'}`}>
            <Bell size={22} /> Alerts
          </NavLink>
        </div>

        <Link to="/dashboard/add-child" className="flex items-center justify-center gap-2 mt-auto p-5 rounded-[24px] bg-accent-500 text-white font-bold hover:-translate-y-1 hover:shadow-lg transition-all duration-300">
          <PlusCircle size={20} /> Add New Child
        </Link>
      </nav>

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto p-6 pl-0 relative z-10 custom-scrollbar">
        <div className="max-w-[1400px] mx-auto h-full pt-4">
           {/* Outlet renders the nested dashboard routes */}
           <Outlet />
        </div>
      </main>
    </div>
  );
};

export default function App() {
  return (
    <PopiProvider>
      <Router>
        <Routes>
          {/* Public Routes */}
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />

          {/* Protected Main Dashboard */}
          <Route element={<ProtectedRoute />}>
             <Route path="/dashboard" element={<DashboardLayout />}>
                <Route index element={<HomePage />} />
                <Route path="child/:id" element={<ChildProfilePage />} />
                <Route path="plan/:id" element={<WeekPlannerPage />} />
                <Route path="alerts" element={<AlertsPage />} />
                <Route path="add-child" element={<AddChildPage />} />
             </Route>
          </Route>
        </Routes>
      </Router>
    </PopiProvider>
  );
}
