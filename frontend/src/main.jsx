import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'

import Login from './Login.jsx'
import Fleet from './Fleet.jsx'
import Machine from './Machine.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Login />} />
        <Route path="/machines" element={<Fleet />} />
        <Route path="/machines/:machineRef" element={<Machine />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
