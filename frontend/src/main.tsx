import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import App from './App'
import SubmitPage from './pages/portal/SubmitPage'
import ReviewPage from './pages/portal/ReviewPage'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <BrowserRouter>
            <Routes>
                {/* Portal pages — no auth, no sidebar, secured by magic-link token */}
                <Route path="/portal/submit" element={<SubmitPage />} />
                <Route path="/portal/review" element={<ReviewPage />} />
                {/* Admin App — existing authenticated shell */}
                <Route path="/*" element={<App />} />
            </Routes>
        </BrowserRouter>
    </React.StrictMode>
)
