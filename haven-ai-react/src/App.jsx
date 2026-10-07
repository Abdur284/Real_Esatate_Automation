import { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { AuthProvider } from './auth/AuthContext';
import ProtectedRoute from './auth/ProtectedRoute';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';
import { ToastProvider } from './components/Toast';
import AIChatBot from './components/AIChatBot';
import RecommendationSidebar from './components/RecommendationSidebar';

// Pages load on demand so the first visit downloads only what it shows.
const Home = lazy(() => import('./pages/Home'));
const TwoDDesign = lazy(() => import('./pages/TwoDDesign'));
const ThreeDDesign = lazy(() => import('./pages/ThreeDDesign'));
const InteriorDesign = lazy(() => import('./pages/InteriorDesign'));
const CostEstimation = lazy(() => import('./pages/CostEstimation'));
const Properties = lazy(() => import('./pages/Properties'));
const PropertyDetail = lazy(() => import('./pages/PropertyDetail'));
const Signup = lazy(() => import('./pages/Signup'));
const DealerDashboard = lazy(() => import('./pages/DealerDashboard'));
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'));
const Chat = lazy(() => import('./pages/Chat'));
const NotFound = lazy(() => import('./pages/NotFound'));

function AppContent() {
    const location = useLocation();
    const isAdmin = location.pathname.startsWith('/admin');
    const isAuthPage = location.pathname.startsWith('/signup');
    const showSidebar = !isAdmin && !isAuthPage;

    return (
        <>
            <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg)' }}>
                <div className={`app-main${showSidebar ? ' has-sidebar' : ''}`} style={{ flex: 1, minWidth: 0 }}>
                    <ErrorBoundary resetKey={location.pathname}>
                        <Suspense fallback={<div className="loading-screen">Loading…</div>}>
                            <Routes>
                                <Route path="/signup" element={<Signup />} />
                                <Route element={<Layout />}>
                                    <Route path="/" element={<Home />} />
                                    <Route path="/2d-design" element={<TwoDDesign />} />
                                    <Route path="/3d-design" element={<ThreeDDesign />} />
                                    <Route path="/interior-design" element={<InteriorDesign />} />
                                    <Route path="/cost-estimation" element={<CostEstimation />} />
                                    <Route path="/properties" element={<Properties />} />
                                    <Route path="/property/:id" element={<PropertyDetail />} />
                                    <Route path="/property-detail" element={<Navigate to="/properties" replace />} />
                                    <Route path="/dealer-dashboard" element={<ProtectedRoute role="seller"><DealerDashboard /></ProtectedRoute>} />
                                    <Route path="/admin" element={<ProtectedRoute admin><AdminDashboard /></ProtectedRoute>} />
                                    <Route path="*" element={<NotFound />} />
                                </Route>
                                <Route element={<Layout footer={false} />}>
                                    <Route path="/chat" element={<ProtectedRoute><Chat /></ProtectedRoute>} />
                                    <Route path="/chat/:chatId" element={<ProtectedRoute><Chat /></ProtectedRoute>} />
                                </Route>
                            </Routes>
                        </Suspense>
                    </ErrorBoundary>
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
            <AuthProvider>
                <ToastProvider>
                    <AppContent />
                </ToastProvider>
            </AuthProvider>
        </BrowserRouter>
    );
}
