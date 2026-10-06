import { useEffect, useState } from 'react';
import { api } from '../api';
import { useAuth } from '../auth';
import Layout from '../components/Layout';

// 约课签到：工作人员可建课/看名单/签到确认；客户可预约/取消/扫码签到
export default function Courses() {
  const { user } = useAuth();
  const staff = user.role !== 'client';
  const [courses, setCourses] = useState([]);
  const [mine, setMine] = useState([]);
  const [form, setForm] = useState({ title: '', course_type: '瑜伽', start_time: '', end_time: '', location: '', capacity: 20 });
  const [roster, setRoster] = useState(null);

  const load = () => {
    api.get('/api/courses').then(setCourses).catch(console.error);
    if (!staff) api.get('/api/bookings/mine').then(setMine).catch(console.error);
  };
  useEffect(load, []);

  const create = async (e) => {
    e.preventDefault();
    await api.post('/api/courses', form);
    setForm({ title: '', course_type: '瑜伽', start_time: '', end_time: '', location: '', capacity: 20 });
    load();
  };
  const book = async (id) => { await api.post(`/api/courses/${id}/book`, {}); load(); };
  const cancel = async (id) => { await api.post(`/api/courses/${id}/cancel`, {}); load(); };
  const openRoster = async (id) => {
    const r = await api.get(`/api/courses/${id}/roster`);
    setRoster({ id, list: r });
  };
  const manualCheckin = async (courseId, clientId) => {
    await api.post(`/api/courses/${courseId}/checkin`, { client_id: clientId });
    openRoster(courseId); load();
  };
  const markNoshow = async (id) => {
    if (!confirm('将未签到的预约记为爽约？')) return;
    await api.post(`/api/courses/${id}/mark-noshow`, {});
    openRoster(id); load();
  };
  const qrCheckin = async (id) => {
    const code = prompt('请输入签到码（教练出示的二维码内容）');
    if (!code) return;
    try { await api.post(`/api/courses/${id}/checkin`, { code }); alert('签到成功'); load(); }
    catch (e) { alert(e.message); }
  };

  const myBooked = new Set(mine.filter((b) => ['booked', 'waitlist'].includes(b.status)).map((b) => b.course_id));
  const statusName = { booked: '已预约', waitlist: '候补中', cancelled: '已取消', checked_in: '已签到', no_show: '爽约' };

  return (
    <Layout>
      <h1 className="text-xl font-bold mb-4">约课签到</h1>

      {staff && (
        <form onSubmit={create} className="card mb-4 grid grid-cols-2 md:grid-cols-3 gap-3">
          <input className="input" placeholder="课程标题*" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
          <input className="input" placeholder="类型（瑜伽/私教…）" value={form.course_type} onChange={(e) => setForm({ ...form, course_type: e.target.value })} />
          <input className="input" placeholder="开始 YYYY-MM-DD HH:MM" value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} />
          <input className="input" placeholder="结束 YYYY-MM-DD HH:MM" value={form.end_time} onChange={(e) => setForm({ ...form, end_time: e.target.value })} />
          <input className="input" placeholder="地点" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
          <input className="input" type="number" placeholder="人数上限" value={form.capacity} onChange={(e) => setForm({ ...form, capacity: +e.target.value })} />
          <button className="btn-primary md:col-span-3">新建课程</button>
        </form>
      )}

      <div className="space-y-3">
        {courses.map((c) => (
          <div key={c.id} className="card">
            <div className="flex justify-between items-start">
              <div>
                <div className="font-bold">{c.title} <span className="text-xs text-gray-400">{c.course_type}</span></div>
                <div className="text-sm text-gray-500">{c.start_time} ~ {c.end_time} · {c.location} · 已约 {c.booked_count}/{c.capacity}</div>
                {staff && <div className="text-xs text-gray-400 mt-1">签到码：{c.checkin_code}（出示给学员扫码）</div>}
              </div>
              <div className="space-x-2 shrink-0">
                {!staff && !myBooked.has(c.id) && <button className="btn-primary text-sm" onClick={() => book(c.id)}>预约</button>}
                {!staff && myBooked.has(c.id) && (
                  <>
                    <button className="btn text-sm" onClick={() => qrCheckin(c.id)}>扫码签到</button>
                    <button className="text-sm text-red-600" onClick={() => cancel(c.id)}>取消</button>
                  </>
                )}
                {staff && (
                  <>
                    <button className="btn text-sm" onClick={() => openRoster(c.id)}>名单</button>
                    <button className="text-sm text-gray-500" onClick={() => markNoshow(c.id)}>标记爽约</button>
                  </>
                )}
              </div>
            </div>
            {roster && roster.id === c.id && (
              <div className="mt-3 border-t pt-2 text-sm">
                {roster.list.map((b) => (
                  <div key={b.id} className="flex justify-between py-1">
                    <span>{b.client_name} <span className="text-gray-400">（{statusName[b.status] || b.status}）</span></span>
                    {(b.status === 'booked' || b.status === 'waitlist') && (
                      <button className="text-teal-600" onClick={() => manualCheckin(c.id, b.client_id)}>手动签到</button>
                    )}
                  </div>
                ))}
                {roster.list.length === 0 && <div className="text-gray-400">暂无预约</div>}
              </div>
            )}
          </div>
        ))}
        {courses.length === 0 && <div className="text-gray-400">暂无课程</div>}
      </div>

      {!staff && mine.length > 0 && (
        <div className="mt-6">
          <h2 className="font-bold mb-2">我的约课记录</h2>
          <div className="card text-sm space-y-1">
            {mine.map((b) => <div key={b.id}>课程 #{b.course_id} · {statusName[b.status] || b.status}</div>)}
          </div>
        </div>
      )}
    </Layout>
  );
}
