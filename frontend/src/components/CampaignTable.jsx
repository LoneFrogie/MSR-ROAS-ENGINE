import { Target } from 'lucide-react';

export default function CampaignTable({ campaigns }) {
  if (!campaigns || campaigns.length === 0) return null;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
      <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <Target size={18} /> Top Campaigns by ROAS
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b">
              <th className="pb-3 font-medium">Campaign</th>
              <th className="pb-3 font-medium">Platform</th>
              <th className="pb-3 font-medium text-right">Spend</th>
              <th className="pb-3 font-medium text-right">Revenue</th>
              <th className="pb-3 font-medium text-right">ROAS</th>
              <th className="pb-3 font-medium text-right">Conv.</th>
              <th className="pb-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {campaigns.slice(0, 15).map((c, i) => (
              <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="py-3 font-medium text-gray-900 max-w-48 truncate">{c.name}</td>
                <td className="py-3">
                  <span className={`px-2 py-1 rounded text-xs ${
                    c.platform === 'google_ads' ? 'bg-blue-50 text-blue-600' : 'bg-indigo-50 text-indigo-600'
                  }`}>
                    {c.platform === 'google_ads' ? 'Google' : 'Meta'}
                  </span>
                </td>
                <td className="py-3 text-right">${c.spend?.toFixed(2)}</td>
                <td className="py-3 text-right text-emerald-600">${c.revenue?.toFixed(2)}</td>
                <td className="py-3 text-right font-semibold">
                  <span className={c.roas >= 4 ? 'text-emerald-600' : c.roas >= 1.5 ? 'text-amber-600' : 'text-red-500'}>
                    {c.roas?.toFixed(2)}x
                  </span>
                </td>
                <td className="py-3 text-right">{c.conversions}</td>
                <td className="py-3">
                  <span className={`px-2 py-1 rounded text-xs ${
                    c.status === 'active' ? 'bg-emerald-50 text-emerald-600' : 'bg-gray-100 text-gray-500'
                  }`}>
                    {c.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
