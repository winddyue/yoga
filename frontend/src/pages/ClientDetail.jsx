import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api';
import Layout from '../components/Layout';
import TrendChart from '../components/TrendChart';

// 客户详情：档案 + 健康提示 + 评估记录 + 趋势曲线
export default function ClientDetail() {
  const { id } = useParams();
  const [client, setClient] = useState(null);
  const [list, setList] = useState([]);
  const [trends, setTrends] = useState({ dates: [], weight: [], body_fat: [] });
  const [warnings, setWarnings] = useState([]);
  const load = () => {
    api.get(`/api/clients/${id}`).then(setClient).catch(console.error);
    api.get(`/api/clients/${id}/assessments`).then(setList).catch(console.error);
    api.get(`/api/clients/${id}/trends`).then(setTrends).catch(console.error);
    api.get(`/api/clients/${id}/warnings`).then((r) => setWarnings(r.warnings)).catch(console.error);
  };
  useEffect(load, [id]);
  if (!client) return <Layout><div>加载中…</div></Layout>;
  return (
    <Layout>
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-xl font-bold">{client.name} <span className="text-sm font-normal text-gray-500">{client.gender} {client.age}岁 · 目标{client.goal} · 出勤{Math.round((client.attendance_rate || 0) * 100)}%</span></h1>
        <div className="space-x-2">
          <Link to={`/clients/${id}/assess`} className="btn-primary inline-block">新增评估</Link>
          <Link to={`/clients/${id}/plans`} className="btn-ghost inline-block">训练计划</Link>
          <Link to={`/clients/${id}/diets`} className="btn-ghost inline-block">饮食方案</Link>
        </div>
      </div>
      {warnings.length > 0 && (
        <div className="card mb-4 border-l-4 border-l-amber-400">
          <div className="font-medium text-amber-700 mb-1">健康提示</div>
          {warnings.map((w, i) => <div key={i} className="text-sm text-amber-700">• {w}</div>)}
        </div>
      )}
      <div className="grid md:grid-cols-2 gap-4 mb-4">
        <div className="card">
          <div className="font-medium mb-2">体重趋势（kg）</div>
          <TrendChart dates={trends.dates} series={trends.weight} unit="kg" />
        </div>
        <div className="card">
          <div className="font-medium mb-2">体脂率趋势（%）</div>
          <TrendChart dates={trends.dates} series={trends.body_fat} unit="%" color="#f59e0b" />
        </div>
      </div>
      <h2 className="font-medium mb-2">评估记录</h2>
      <div className="space-y-2">
        {list.map((a) => (
          <div key={a.id} className="card text-sm">
            <span className="font-medium">{a.date || '未填日期'}</span>
            <span className="text-gray-500 ml-3">体重{a.weight_kg}kg · 体脂{a.body_fat_pct}% · 腰围{a.waist_cm}cm</span>
            {a.blood_pressure && <span className="text-gray-500 ml-3">血压{a.blood_pressure}</span>}
            {a.injuries && <div className="text-amber-600 mt-1">注意：{a.injuries}</div>}
          </div>
        ))}
        {!list.length && <div className="text-gray-400 text-sm">暂无评估记录</div>}
      </div>
    </Layout>
  );
}
