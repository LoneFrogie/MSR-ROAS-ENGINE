import { Routes, Route } from 'react-router-dom';
import { DataProvider } from './hooks/useDataContext';
import Layout from './components/Layout';
import SummaryPage from './pages/SummaryPage';
import SEOPage from './pages/SEOPage';
import DetailsPage from './pages/DetailsPage';

export default function App() {
  return (
    <DataProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<SummaryPage />} />
          <Route path="seo" element={<SEOPage />} />
          <Route path="details" element={<DetailsPage />} />
        </Route>
      </Routes>
    </DataProvider>
  );
}
