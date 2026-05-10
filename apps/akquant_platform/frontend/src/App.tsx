import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { colors } from './theme/variables';
import PositionListPage from './pages/PositionListPage';
import PositionDetailPage from './pages/PositionDetailPage';
import './theme/global.css';

const navStyle: React.CSSProperties = {
  background: colors.dark,
  borderBottom: `1px solid #333`,
  padding: '0 32px',
  display: 'flex',
  alignItems: 'center',
  height: 56,
  gap: 32,
};

const linkStyle = ({ isActive }: { isActive: boolean }): React.CSSProperties => ({
  color: isActive ? colors.yellow : colors.slate,
  fontWeight: 600,
  fontSize: 14,
  textDecoration: 'none',
  padding: '16px 0',
  borderBottom: isActive ? `2px solid ${colors.yellow}` : '2px solid transparent',
  transition: 'color 0.2s',
});

export default function App() {
  return (
    <BrowserRouter>
      <nav style={navStyle}>
        <span style={{ color: colors.yellow, fontWeight: 700, fontSize: 18, marginRight: 24 }}>
          AKQuant
        </span>
        <NavLink to="/" end style={linkStyle}>持仓管理</NavLink>
        <NavLink to="/data" style={linkStyle}>数据更新</NavLink>
      </nav>
      <main style={{ flex: 1, background: colors.snow }}>
        <Routes>
          <Route path="/" element={<PositionListPage />} />
          <Route path="/positions/:positionId" element={<PositionDetailPage />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
