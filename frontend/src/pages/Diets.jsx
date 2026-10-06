import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api';
import Layout from '../components/Layout';

const MEAL_NAMES = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐', snack: '加餐' };

// 饮食方案：生成 → 教练确认
export default function Diets() {
  const { id } = useParams();
  const [list, setList] = useState([]);
  const load = () => api.get(`/api/clients/${id}/diets`).then(setList).catch(console.error);
  useEffect(load, [id]);
  const generate = async () => {
    const date = prompt('方案日期（YYYY-MM-DD）', new Date().toISOString().slice(0, 10));
    if (!date) return;
    try { await api.post(`/api/clients/${id}/diets/generate`, { date, activity_level: 'moderate' }); }
    catch (e) { alert(e.message); return; }
    load();
  };
  const confirm = async (did) => {
    if (!window.confirm('确认该饮食方案？确认后将作为后续推荐的学习依据。')) return;
    await api.post(`/api/diets/${did}/confirm`);
    load();
  };
  return (
    <Layout>
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-xl font-bold">饮食方案</h1>
        <button className="btn-primary" onClick={generate}>生成方案</button>
      </div>
      <div className="space-y-3">
        {list.map((d) => (
          <div key={d.id} className="card">
            <div className="flex justify-between items-center mb-2">
              <span className="font-medium">{d.date}</span>
              {d.status === 'pending'
                ? <button className="btn-primary !py-1" onClick={() => confirm(d.id)}>教练确认</button>
                : <span className="text-xs text-teal-600 border border-teal-300 rounded px-2 py-0.5">已确认</span>}
            </div>
            <div className="text-sm text-gray-500 mb-2">
              目标 {d.calories_target}千卡 · 蛋白质{d.protein_g}g · 脂肪{d.fat_g}g · 碳水{d.carbs_g}g
            </div>
            <div className="grid md:grid-cols-2 gap-2">
              {Object.entries(d.meals || {}).map(([k, foods]) => (
                <div key={k} className="text-sm bg-gray-50 rounded p-2">
                  <div className="font-medium">{MEAL_NAMES[k] || k}</div>
                  {(foods || []).map((f, i) => <div key={i} className="text-gray-600">• {f}</div>)}
                </div>
              ))}
            </div>
          </div>
        ))}
        {!list.length && <div className="text-gray-400 text-sm">暂无方案，点“生成方案”（需先录入含体重的评估）</div>}
      </div>
    </Layout>
  );
}
