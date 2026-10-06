import { useEffect, useState } from 'react';
import { api } from '../api';
import Layout from '../components/Layout';

// 总览页：极简经营指标
export default function Dashboard() {
  const [d, setD] = useState(null);
  useEffect(() => { api.get('/api/dashboard').then(setD).catch(console.error); }, []);
  if (!d) return <Layout><div>加载中…</div></Layout>;
  const cards = [
    ['客户数', d.client_count],
    ['教练数', d.coach_count],
    ['近7天评估', d.week_assessments],
    ['待确认饮食方案', d.pending_diets],
  ];
  return (
    <Layout>
      <h1 className="text-xl font-bold mb-4">总览</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {cards.map(([k, v]) => (
          <div key={k} className="card text-center">
            <div className="text-3xl font-bold text-teal-700">{v}</div>
            <div className="text-sm text-gray-500 mt-1">{k}</div>
          </div>
        ))}
      </div>
    </Layout>
  );
}
