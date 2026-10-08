import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api';
import Layout from '../components/Layout';

const MEAL_NAMES = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐', snack: '加餐' };

// 饮食方案：公式生成 / AI 生成初版 → 教练确认（双轨制）
export default function Diets() {
  const { id } = useParams();
  const [list, setList] = useState([]);
  const [editing, setEditing] = useState(null);  // 正在微调的方案 id
  const [editText, setEditText] = useState('');
  const load = () => api.get(`/api/clients/${id}/diets`).then(setList).catch(console.error);
  useEffect(load, [id]);
  const generate = async () => {
    const date = prompt('方案日期（YYYY-MM-DD）', new Date().toISOString().slice(0, 10));
    if (!date) return;
    try { await api.post(`/api/clients/${id}/diets/generate`, { date, activity_level: 'moderate' }); }
    catch (e) { alert(e.message); return; }
    load();
  };
  const aiGenerate = async () => {
    if (!window.confirm('用 AI 生成饮食初版？将消耗一次 AI 调用额度，生成后待教练确认。')) return;
    try { await api.post(`/api/clients/${id}/diets/ai-generate`, {}); }
    catch (e) { alert(e.message); return; }
    load();
  };
  const confirm = async (did, meals) => {
    if (!window.confirm('确认该饮食方案？确认后将作为后续推荐的学习依据，并通知客户。')) return;
    try { await api.post(`/api/diets/${did}/confirm`, meals ? { meals } : {}); }
    catch (e) { alert(e.message); return; }
    setEditing(null);
    load();
  };
  const startEdit = (d) => {
    setEditing(d.id);
    setEditText(JSON.stringify(d.meals || {}, null, 2));
  };
  const confirmEdited = (did) => {
    let meals = null;
    try {
      meals = JSON.parse(editText);
      if (typeof meals !== 'object' || Array.isArray(meals)) throw new Error('bad');
    } catch (e) { alert('餐单 JSON 格式不正确'); return; }
    confirm(did, meals);
  };
  const statusBadge = (d) => {
    if (d.status === 'confirmed') return <span className="text-xs text-brand-600 border border-brand-200 rounded px-2 py-0.5">已确认</span>;
    if (d.status === 'ai_draft') return <span className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-0.5">AI 生成·待教练确认</span>;
    return <span className="text-xs text-muted border border-sand rounded px-2 py-0.5">待确认</span>;
  };
  return (
    <Layout>
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-xl font-bold">饮食方案</h1>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={aiGenerate}>AI 生成初版</button>
          <button className="btn-primary" onClick={generate}>生成方案</button>
        </div>
      </div>
      <div className="space-y-3">
        {list.map((d) => (
          <div key={d.id} className="card">
            <div className="flex justify-between items-center mb-2">
              <span className="font-medium">{d.date}</span>
              <div className="flex items-center gap-2">
                {statusBadge(d)}
                {d.status !== 'confirmed' && (
                  <>
                    <button className="btn-secondary !py-1 !text-xs" onClick={() => startEdit(d)}>微调</button>
                    <button className="btn-primary !py-1" onClick={() => confirm(d.id)}>一键确认</button>
                  </>
                )}
              </div>
            </div>
            {d.status === 'ai_draft' && (
              <div className="text-xs text-clay mb-2">AI 生成内容仅供参考，不构成医疗建议，请遵医嘱</div>
            )}
            {editing === d.id ? (
              <div className="mb-2">
                <textarea className="input font-mono !text-xs" rows={8} value={editText}
                          onChange={(e) => setEditText(e.target.value)} />
                <div className="flex gap-2 mt-2">
                  <button className="btn-primary !py-1" onClick={() => confirmEdited(d.id)}>确认（用调整后）</button>
                  <button className="btn-secondary !py-1" onClick={() => setEditing(null)}>取消</button>
                </div>
              </div>
            ) : (
              <>
                <div className="text-sm text-muted mb-2">
                  目标 {d.calories_target}千卡 · 蛋白质{d.protein_g}g · 脂肪{d.fat_g}g · 碳水{d.carbs_g}g
                </div>
                <div className="grid md:grid-cols-2 gap-2">
                  {Object.entries(d.meals || {}).map(([k, foods]) => (
                    <div key={k} className="text-sm bg-cream rounded p-2">
                      <div className="font-medium">{MEAL_NAMES[k] || k}</div>
                      {(foods || []).map((f, i) => <div key={i} className="text-muted">• {f}</div>)}
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        ))}
        {!list.length && <div className="text-clay text-sm">暂无方案，点"生成方案"（需先录入含体重的评估）或"AI 生成初版"</div>}
      </div>
    </Layout>
  );
}
