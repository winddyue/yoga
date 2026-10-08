import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api';
import Layout from '../components/Layout';

// 训练计划：自动生成 + 教练手动调整
export default function Plans() {
  const { id } = useParams();
  const [plans, setPlans] = useState([]);
  const [editing, setEditing] = useState(null); // 正在编辑的 plan（深拷贝）
  const load = () => api.get(`/api/clients/${id}/plans`).then(setPlans).catch(console.error);
  useEffect(load, [id]);

  const generate = async () => {
    const week = prompt('计划开始日期（YYYY-MM-DD）', new Date().toISOString().slice(0, 10));
    if (!week) return;
    await api.post(`/api/clients/${id}/plans/generate?week_start=${week}`);
    load();
  };
  const save = async () => {
    await api.put(`/api/plans/${editing.id}`, { week_start: editing.week_start, days: editing.days });
    setEditing(null);
    load();
  };
  const updDay = (di, patch) => {
    const days = editing.days.map((d, i) => (i === di ? { ...d, ...patch } : d));
    setEditing({ ...editing, days });
  };
  const addExercise = (di) => {
    const name = prompt('动作名称');
    if (!name) return;
    const days = editing.days.map((d, i) => (i === di ? { ...d, exercises: [...d.exercises, { name, sets: 3, reps: '12' }] } : d));
    setEditing({ ...editing, days });
  };
  const delExercise = (di, ei) => {
    const days = editing.days.map((d, i) => (i === di ? { ...d, exercises: d.exercises.filter((_, j) => j !== ei) } : d));
    setEditing({ ...editing, days });
  };

  const view = editing || plans[0];
  return (
    <Layout>
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-xl font-bold">训练计划</h1>
        <div className="space-x-2">
          <button className="btn-primary" onClick={generate}>自动生成</button>
          {view && !editing && <button className="btn-ghost" onClick={() => setEditing(JSON.parse(JSON.stringify(view)))}>手动调整</button>}
          {editing && (<><button className="btn-primary" onClick={save}>保存</button><button className="btn-ghost" onClick={() => setEditing(null)}>取消</button></>)}
        </div>
      </div>
      {!view && <div className="text-clay text-sm">暂无计划，点“自动生成”</div>}
      {view && (
        <div className="space-y-3">
          {(editing || view).days.map((d, di) => (
            <div key={di} className="card">
              <div className="flex gap-2 items-center mb-2">
                <span className="font-medium">{d.day}</span>
                {editing
                  ? <input className="input !w-32" placeholder="时间" value={d.time || ''} onChange={(e) => updDay(di, { time: e.target.value })} />
                  : d.time && <span className="text-sm text-muted">{d.time}</span>}
                {editing && <button className="btn-ghost !py-1 ml-auto" onClick={() => addExercise(di)}>+ 动作</button>}
              </div>
              {d.exercises.map((ex, ei) => (
                <div key={ei} className="flex justify-between text-sm py-1 border-b last:border-0">
                  <span>{ex.name}</span>
                  <span className="text-muted">{ex.sets}组 × {ex.reps}
                    {editing && <button className="text-[#C07878] ml-2" onClick={() => delExercise(di, ei)}>删</button>}
                  </span>
                </div>
              ))}
            </div>
          ))}
          <div className="text-xs text-clay">开始日期：{(editing || view).week_start} · 状态：{(editing || view).status}</div>
        </div>
      )}
    </Layout>
  );
}
