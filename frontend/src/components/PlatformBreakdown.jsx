import { BarChart3 } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

export default function PlatformBreakdown({ data }) {
  if (!data) return null;
  const chartData = Object.entries(data).map(([name, d]) => ({
    name: name.replace('_', ' ').toUpperCase(),
    spend: d.spend || d.total_spend || 0,
    revenue: d.revenue || d.total_revenue || 0,
    roas: d.roas || 0,
  }));

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
      <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <BarChart3 size={18} /> Platform Performance
      </h3>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="name" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip formatter={(val) => `$${val.toFixed(2)}`} />
          <Legend />
          <Bar dataKey="spend" fill="#6366f1" name="Spend" radius={[4,4,0,0]} />
          <Bar dataKey="revenue" fill="#10b981" name="Revenue" radius={[4,4,0,0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
