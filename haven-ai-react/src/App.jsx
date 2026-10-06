import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import Home from './pages/Home';
import TwoDDesign from './pages/TwoDDesign';
import ThreeDDesign from './pages/ThreeDDesign';
import InteriorDesign from './pages/InteriorDesign';
import CostEstimation from './pages/CostEstimation';
import Properties from './pages/Properties';
import PropertyDetail from './pages/PropertyDetail';
import Signup from './pages/Signup';
import DealerDashboard from './pages/DealerDashboard';
import AdminDashboard from './pages/AdminDashboard';
import Chat from './pages/Chat';
import AIChatBot from './components/AIChatBot';
import RecommendationSidebar from './components/RecommendationSidebar';

function AppContent() {
  const location = useLocation();
  const isAdmin = location.pathname.startsWith('/admin');
  const isAuthPage = location.pathname.startsWith('/signup');
  const showSidebar = !isAdmin && !isAuthPage;

  return (
    <>
      <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg)' }}>
        <div className={`app-main${showSidebar ? ' has-sidebar' : ''}`} style={{ flex: 1, minWidth: 0 }}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/2d-design" element={<TwoDDesign />} />
            <Route path="/3d-design" element={<ThreeDDesign />} />
            <Route path="/interior-design" element={<InteriorDesign />} />
            <Route path="/cost-estimation" element={<CostEstimation />} />
            <Route path="/properties" element={<Properties />} />
            <Route path="/property-detail" element={<PropertyDetail />} />
            <Route path="/property/:id" element={<PropertyDetail />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/dealer-dashboard" element={<DealerDashboard />} />
            <Route path="/admin" element={<AdminDashboard />} />
            <Route path="/chat/:chatId" element={<Chat />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="*" element={<Home />} />
          </Routes>
        </div>
        {showSidebar && <RecommendationSidebar />}
      </div>
      {!isAdmin && <AIChatBot />}
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}

